"""D233 native checkpoint transport with an isolated, bounded cold broker.

The original one-attempt/signature/recovery boundaries remain v10. Only the
explicit /2 storage path uses this transport. No automatic retry is provided.
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
import types

import stage17_fixed_action_executor_v10 as previous
import stage17_fixed_action_executor_v5 as transport_base
import stage17_formal_plan_v2 as plans
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_archive_channel_v1 as channel
from stage17_formal_checkpoint_v1 import PinnedWorker

FixedActionExecutionError = previous.FixedActionExecutionError
CLEANUP_NS = 2_000_000_000
MAX_CONTROL_BYTES = 128 * 1024**2
MAX_LEDGER_RECORDS = 1_000_000
MAX_PROGRAM_FILES = 1_000_000


def custody_limits(storage, deadline_ns):
    return custody.CustodyLimits(max(131072, storage["checkpoint_bytes"]), MAX_LEDGER_RECORDS,
        MAX_PROGRAM_FILES, storage["checkpoint_bytes"], deadline_ns)


def open_store(request, deadline_ns):
    plan = request["action_inputs"]["plan"]
    storage = plan["storage"]
    family = previous.sha256(archive.canonical(plan))
    working = Path(request["evidence_root_binding"]["absolute_path"])
    if working.name != family or working.parent.name != "working":
        raise FixedActionExecutionError("ARCHIVE_ROOT", "phase root is not the original plan's program family")
    return custody.ProgramStore(working.parent.parent, scope_sha256=storage["program_scope_sha256"],
        family_id=family, limits=custody_limits(storage, deadline_ns))


def live_resources(directory_fd, extent, *, request, deadline_ns, ordinal=0):
    """Read shared physical usage; no family resets the six-terabyte quota."""
    plan = request["action_inputs"]["plan"]
    storage = plan["storage"]
    with open_store(request, deadline_ns) as store:
        family = store._families.get(store.family_id)
        st = os.fstat(directory_fd)
        if (family is None or (st.st_dev, st.st_ino) != (family["device"], family["inode"])
                or store.scope["program_id"] != storage["program_id"]):
            raise FixedActionExecutionError("ARCHIVE_ROOT", "phase root lacks its original family ledger binding")
        observed = os.fstatvfs(directory_fd)
        used = store.physical_usage()
        remaining = custody.PROGRAM_QUOTA - used
        if remaining < 0:
            raise FixedActionExecutionError("ARCHIVE_QUOTA", "shared archive quota is exhausted")
        # Keep v10's actual MemAvailable and pinned-filesystem observation. The
        # remaining quota replaces only its initial full-quota disk declaration.
        from dataclasses import replace
        needed = remaining + custody.WORKSPACE + custody.SCRATCH + custody.RESERVE
        adjusted = replace(extent, declared=replace(extent.declared, required_free_disk_bytes=needed))
        result = previous.live_resources(directory_fd, adjusted)
        capture = extent.captures[min(ordinal, len(extent.captures) - 1)]
        custody.check_capacity(custody.CapacitySnapshot(
            observed.f_bavail * observed.f_frsize, observed.f_favail, used, store.reserved_bytes(), 0, 0),
            custody.SpacePlan(capture.declared.max_output_bytes, 0,
                storage["capture_workspace_overhead_bytes"], storage["archive_staging_bytes"],
                2 * storage["checkpoint_bytes"], storage["analysis_capture_workspace_bytes"], 128))
        result.update(program_scope_sha256=store.scope_sha256, retained_program_bytes=used,
                      remaining_program_quota_bytes=remaining, capture_ordinal=ordinal)
        return result


def _broker_receipt(request, pending, outcome, deadline_ns):
    """Authenticate durable publication after the actual broker was reaped."""
    proof = outcome.cleanup
    if (not proof.leader_reaped or not proof.process_group_gone
            or proof.returncode != 0 or proof.cleanup_deadline_overrun
            or proof.descendants_detected_after_leader_exit):
        raise FixedActionExecutionError("ARCHIVE_CLEANUP", "broker did not complete with proven child cleanup")
    if outcome.status != "ARCHIVED_AND_RELEASED":
        raise FixedActionExecutionError("ARCHIVE_FAILED_EVIDENCE", "source discrepancy stops the family")
    with open_store(request, deadline_ns) as store:
        record = store.read_verified_record(outcome.receipt_ledger_record)
        expected = dict(family_id=store.family_id, checkpoint_sha256=pending.binding["sha256"],
                        receipt=asdict(outcome.receipt))
        if (record["kind"] != "CUSTODY_RECEIPT"
                or archive.canonical(record["payload"]) != archive.canonical(expected)):
            raise FixedActionExecutionError("ARCHIVE_CUSTODY", "broker result is not in the durable program ledger")
        raw = store._read_bound(store.working / outcome.receipt.file_name,
                               outcome.receipt.binding(), store.limits.max_record_bytes)
        document = archive.parse_json(raw)
        if (document["status"] != outcome.status or document["checkpoint"] != pending.binding
                or document["capture_ordinal"] != pending.ordinal):
            raise FixedActionExecutionError("ARCHIVE_CUSTODY", "durable broker receipt differs")
    return asdict(outcome.receipt)


def _finish_archived_capture(request, pending, outcome, deadline_ns, *, directory_fd, extent):
    """Run original receipt/resource checks in one fresh exclusive transaction."""
    with open_store(request, deadline_ns) as store:
        active = True

        def held_store(candidate_request, candidate_deadline_ns):
            if (not active or candidate_request is not request
                    or type(candidate_deadline_ns) is not type(deadline_ns)
                    or candidate_deadline_ns != deadline_ns):
                raise FixedActionExecutionError("ARCHIVE_STORE_REUSE", "held store request/deadline differs or transaction ended")
            return contextlib.nullcontext(store)

        def callback(original):
            namespace = dict(original.__globals__)
            namespace["open_store"] = held_store
            result = types.FunctionType(original.__code__, namespace, original.__name__,
                                        original.__defaults__, original.__closure__)
            result.__kwdefaults__ = original.__kwdefaults__
            return result

        try:
            receipt = callback(_broker_receipt)(request, pending, outcome, deadline_ns)
            if pending.document.get("native_complete") is not True:
                raise FixedActionExecutionError("NATIVE_FAILURE", "archived native failure stops the family")
            if pending.ordinal + 1 < len(extent.captures):
                callback(live_resources)(directory_fd, extent, request=request, deadline_ns=deadline_ns,
                                         ordinal=pending.ordinal + 1)
            return receipt
        finally:
            active = False


def run_archived_worker(argv, pass_fds, *, global_deadline_ns, monotonic_expiry_ns,
                        authority_guard, request, profile, extent):
    from stage17_formal_archive_broker_v1 import ArchiveBrokerClient
    deadline = min(global_deadline_ns, monotonic_expiry_ns)
    storage = request["action_inputs"]["plan"]["storage"]
    parent, child = channel.create_channel()
    selector = selectors.DefaultSelector()
    lease = transport_base.process_supervisor.SupervisorLease()
    process = pinned = context_snapshot = cleanup = None
    primary = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    context_index = argv.index("--context-fd") + 1
    old_context_fd = int(argv[context_index])
    directory_fd = int(argv[argv.index("--output-dir-fd") + 1])
    try:
        context_raw = os.pread(old_context_fd, MAX_CONTROL_BYTES + 1, 0)
        if len(context_raw) > MAX_CONTROL_BYTES:
            raise FixedActionExecutionError("ARCHIVE_CONTEXT", "sealed context exceeds input bound")
        context = json.loads(context_raw)
        context["archive_channel"] = dict(descriptor=child.fileno(), controller_pid=os.getpid(),
                                          program_scope_sha256=storage["program_scope_sha256"])
        context_snapshot = previous.predecessor._pin_generated(previous.canonical(context), "FORMAL_ARCHIVE_CONTEXT_V6")
        arguments = list(argv)
        arguments[context_index] = str(context_snapshot.descriptor)
        descriptors = tuple(fd for fd in pass_fds if fd != old_context_fd) + (context_snapshot.descriptor, child.fileno())
        lease.enter()
        try:
            authority_guard()
            process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, close_fds=True, pass_fds=descriptors, shell=False,
                start_new_session=True, env=transport_base.FIXED_ENVIRONMENT)
            child.close()
            pinned = PinnedWorker(process.pid)
            handoff = channel.ArchiveChannel(parent, worker=pinned, directory_fd=directory_fd,
                request_sha256=previous.sha256(previous.canonical(request)),
                program_scope_sha256=storage["program_scope_sha256"], captures=len(extent.captures),
                maximum_checkpoint_bytes=storage["checkpoint_bytes"],
                maximum_custody_receipt_bytes=storage["checkpoint_bytes"],
                maximum_archive_ns=storage["per_capture_archive_ns"])
            for name in ("stdout", "stderr"):
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            selector.register(parent, selectors.EVENT_READ, "archive")
            while selector.get_map():
                if time.monotonic_ns() + CLEANUP_NS >= deadline:
                    raise FixedActionExecutionError("WORKER_TIMEOUT", "formal authority or family deadline reached")
                # Hold the leader unreaped until the existing supervisor proves
                # its whole process family gone. No subprocess.poll()/wait().
                exited = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if exited is not None:
                    break
                for key, _ in selector.select(0.05):
                    if key.data != "archive":
                        data = os.read(key.fd, 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        if sum(map(len, output.values())) + len(data) > previous.predecessor.MAX_OUTPUT_BYTES:
                            raise FixedActionExecutionError("WORKER_OUTPUT_LIMIT", "formal console output exceeded bound")
                        output[key.data].extend(data)
                        continue
                    pending = handoff.receive(deadline_ns=deadline)
                    cold_deadline = min(pending.deadline_ns, deadline - CLEANUP_NS)
                    limits = runtime.RuntimeLimits(storage["broker_address_space_bytes"],
                        storage["codec_address_space_bytes"], MAX_CONTROL_BYTES,
                        max(131072, storage["checkpoint_bytes"]), previous.predecessor.MAX_OUTPUT_BYTES,
                        CLEANUP_NS, cold_deadline, monotonic_expiry_ns,
                        max(1, 3 * len(pending.document["artifacts"])))
                    store = open_store(request, cold_deadline)
                    root, scope, family = store.root, store.scope_sha256, store.family_id
                    with ArchiveBrokerClient(profile=profile, limits=limits,
                            identity_model=lease.identity_model, native_worker=pinned) as broker:
                        outcome = broker.archive_capture(program_root=root, scope_sha256=scope, family_id=family,
                            custody_limits=custody_limits(storage, cold_deadline), request_document=request,
                            capture_ordinal=pending.ordinal, checkpoint=custody.BoundFile(**pending.binding))
                    receipt = _finish_archived_capture(request, pending, outcome, cold_deadline,
                                                       directory_fd=directory_fd, extent=extent)
                    handoff.acknowledge(receipt, deadline_ns=cold_deadline)
                    if handoff.ordinal == len(extent.captures):
                        # The finite handshake is complete. Keep the endpoint
                        # open until native exit so its final ACK read cannot
                        # race a parent HUP; stdout/held-leader checks continue.
                        selector.unregister(parent)
        except BaseException as error:
            primary = error
        finally:
            selector.close()
            if process is not None:
                try:
                    cleanup = transport_base.process_supervisor.cleanup_process_group(process,
                        force_stop=primary is not None,
                        leader_wait_deadline_ns=min(time.monotonic_ns() + CLEANUP_NS, deadline),
                        global_deadline_ns=deadline, identity_model=lease.identity_model)
                except BaseException as error:
                    primary = primary or error
                    cleanup = transport_base._fallback_reap(process)
                if cleanup.leader_reaped and cleanup.process_group_gone:
                    for name in ("stdout", "stderr"):
                        stream = getattr(process, name)
                        while True:
                            data = os.read(stream.fileno(), 65536)
                            if not data:
                                break
                            if sum(map(len, output.values())) + len(data) > previous.predecessor.MAX_OUTPUT_BYTES:
                                raise FixedActionExecutionError("WORKER_OUTPUT_LIMIT", "final console output exceeded bound")
                            output[name].extend(data)
    except BaseException as error:
        if primary is None:
            primary = error
    finally:
        parent.close()
        child.close()
        if pinned is not None: pinned.close()
        if context_snapshot is not None: context_snapshot.close()
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None: stream.close()
        selector.close()
        lease.close(suppress=primary is not None)
    if process is None:
        failure = FixedActionExecutionError("WORKER_START", str(primary))
        failure.cleanup_proof = previous.predecessor.TransportOutcome(-1, b"", b"", True, True, "NO_PROCESS_CREATED")
        raise failure from primary
    if (primary is not None or cleanup is None or not cleanup.leader_reaped
            or not cleanup.process_group_gone or cleanup.cleanup_deadline_overrun
            or cleanup.descendants_detected_after_leader_exit):
        failure = FixedActionExecutionError("ARCHIVE_WORKER_FAILURE", str(primary or "cleanup not proven"))
        if cleanup is not None: failure.cleanup_proof = cleanup
        raise failure from primary
    return previous.predecessor.TransportOutcome(cleanup.returncode, bytes(output["stdout"]), bytes(output["stderr"]),
        cleanup.leader_reaped, cleanup.process_group_gone, cleanup.terminal_cleanup_outcome)


def execute_fixed_action(*, archive_runtime_profile, **arguments):
    from stage17_phase_controller_v26 import is_archived
    import stage17_output_registry_v12 as registry
    request = arguments["request"]
    if not is_archived(request):
        return previous.execute_fixed_action(**arguments)
    plan = request["action_inputs"]["plan"]
    extent = plans.validate_plan(request["action_id"], plan)
    if archive_runtime_profile.decoder.implementation_profile_sha256 != plan["storage"]["implementation_profile_sha256"]:
        raise FixedActionExecutionError("ARCHIVE_PROFILE", "qualified runtime differs from signed storage plan")
    deadline = time.monotonic_ns() + extent.declared.watchdog_ns

    def resources(directory_fd, declared):
        return live_resources(directory_fd, declared, request=request, deadline_ns=deadline)

    def worker(argv, pass_fds, **values):
        return run_archived_worker(argv, pass_fds, request=request, profile=archive_runtime_profile,
                                   extent=extent, **values)

    def validate_result(**values):
        return registry.verify_archived_formal_metadata(repository_root=arguments["repository_root"],
            archive_runtime_profile=archive_runtime_profile, deadline_ns=deadline, **values)

    namespace = dict(previous.execute_fixed_action.__globals__)
    namespace.update(contract=plans, live_resources=resources, _run_formal_worker=worker,
        output_registry=types.SimpleNamespace(**{**vars(registry), "validate_worker_result": validate_result}))
    execute = types.FunctionType(previous.execute_fixed_action.__code__, namespace,
                                 argdefs=previous.execute_fixed_action.__defaults__)
    execute.__kwdefaults__ = previous.execute_fixed_action.__kwdefaults__
    return execute(**arguments)
