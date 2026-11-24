"""D288 cold sealed94-setting source preparation and private archived-worker adapter.

No action authority by import or by a successful pin. Caller must authenticate
accepted-generator provenance, namespace ownership, calibration compatibility,
qualified release and ordinary signed phase authority before execution.
"""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import time
import types

import stage17_formal_archive_v1 as archive
import stage17_formal_scheduled_continuation_v1 as contract
import stage17_q16c_source_execution_v1 as historical
import stage17_service_daycap_execution_v1 as previous
from stage17_discovery_contract_v2 import ContractError

SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL


def _before(deadline):
    if type(deadline) is not int or time.monotonic_ns() >= deadline:
        raise ContractError('original source preparation deadline expired')


@contextlib.contextmanager
def pin_original_sources(plan, original_bindings, *, deadline_ns):
    """Pin exactly188 previously authenticated originals, release all on exit.

    Bindings are in capture/phase order and contain artifact_id,path,size_bytes,
    sha256. This verifies immutable byte custody; it does not authenticate the
    generator or registry author and cannot replace prospective provenance.
    """
    contract.validate_plan(plan)
    _before(deadline_ns)
    deadline_ns = min(deadline_ns, time.monotonic_ns() + plan['budget']['setup_ns'])
    if type(original_bindings) is not list or len(original_bindings) != 188:
        raise ContractError('exact complete source bindings required')
    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    existing = len(os.listdir('/proc/self/fd'))
    if soft != resource.RLIM_INFINITY and existing + 188 + 8 > soft:
        raise ContractError('actual FD limit cannot hold complete original sources and control reserve')
    readers, bound = [], []
    try:
        for index, original in enumerate(original_bindings):
            _before(deadline_ns)
            source = plan['captures'][index // 2]['capture']['schedules'][index % 2]
            artifact = source['source_artifact']
            size = source['offered_count'] * 8
            if (type(original) is not dict or set(original) != {'artifact_id', 'path', 'size_bytes', 'sha256'}
                    or type(original['size_bytes']) is not int or original['size_bytes'] != size
                    or original['artifact_id'] != artifact['artifact_id'] or original['sha256'] != artifact['sha256']):
                raise ContractError('original source binding differs from the prospective plan')
            path = Path(original['path'])
            if not path.is_absolute(): raise ContractError('original source path must be absolute')
            writer = reader = None
            try:
                with archive.open_regular(path) as stream:
                    before = archive.file_stamp(os.fstat(stream.fileno()))
                    if before[2] != size: raise ContractError('original source size differs')
                    writer = os.memfd_create('stage17-original-schedule', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
                    digest = hashlib.sha256()
                    remaining = size
                    while remaining:
                        _before(deadline_ns)
                        block = stream.read(min(65536, remaining))
                        if not block: raise ContractError('original source truncated')
                        digest.update(block)
                        view = memoryview(block)
                        while view:
                            _before(deadline_ns)
                            written = os.write(writer, view)
                            if written <= 0: raise ContractError('original source memfd write failed')
                            view = view[written:]
                        remaining -= len(block)
                    if (stream.read(1) or digest.hexdigest() != original['sha256']
                            or before != archive.file_stamp(os.fstat(stream.fileno()))
                            or before != archive.file_stamp(path.lstat())):
                        raise ContractError('original source bytes or physical identity changed')
                fcntl.fcntl(writer, fcntl.F_ADD_SEALS, SEALS)
                reader = os.open('/proc/self/fd/' + str(writer), os.O_RDONLY | os.O_CLOEXEC)
                readers.append(reader)
                bound.append(dict(artifact_id=artifact['artifact_id'], sha256=artifact['sha256'],
                                  size_bytes=size, descriptor=reader))
                reader = None
            finally:
                if reader is not None: os.close(reader)
                if writer is not None: os.close(writer)
        _before(deadline_ns)
        yield dict(schema_version='cpu-prefetch-stage17-schedule-source-context/1',
                   bindings=bound, deadline_monotonic_ns=deadline_ns), tuple(readers)
    finally:
        for reader in reversed(readers): os.close(reader)


@contextlib.contextmanager
def sealed_worker_inputs(argv, pass_fds, *, plan, original_bindings, deadline_ns):
    """Bind real sealed source/context FDs for the existing archived-worker seam."""
    import stage17_fixed_action_executor_v10 as executor
    with pin_original_sources(plan, original_bindings, deadline_ns=deadline_ns) as (source_context, sources):
        index = argv.index('--context-fd') + 1
        original_fd = int(argv[index])
        if original_fd not in pass_fds or len(pass_fds) != len(set(pass_fds)):
            raise ContractError('original sealed context FD is absent or aliased')
        raw = os.pread(original_fd, 1024**2 + 1, 0)
        if len(raw) > 1024**2: raise ContractError('original context exceeds bound')
        if not raw.endswith(b'\n'):
            raise ContractError('original worker context lacks its canonical final newline')
        context = archive.parse_json(raw[:-1])
        if context['schema_version'] != 'cpu-prefetch-stage17-fixed-action-context/6':
            raise ContractError('unexpected original context version')
        context.update(schema_version='cpu-prefetch-stage17-fixed-action-context/7',
                       schedule_source_context=source_context)
        pinned = executor.predecessor._pin_generated(
            executor.canonical(context), 'Q16C_ORIGINAL_SOURCE_CONTEXT_V7')
        try:
            args = list(argv); args[index] = str(pinned.descriptor)
            fds = tuple(fd for fd in pass_fds if fd != original_fd) + (pinned.descriptor,) + sources
            yield args, fds
        finally: pinned.close()


def make_contract():
    old = historical.make_contract()
    def validate_plan(action, document):
        if action == 'Q16c' and isinstance(document, dict) and document.get('schema_version') == contract.VERSION:
            return contract.validate_plan(document)
        return old.validate_plan(action, document)
    def is_archived_plan(action, document):
        return (action == 'Q16c' and isinstance(document, dict) and document.get('schema_version') == contract.VERSION
                or old.is_archived_plan(action, document))
    return types.SimpleNamespace(**{**vars(old), 'validate_plan': validate_plan, 'is_archived_plan': is_archived_plan})


def make_executor():
    """Return an isolated adapter; historical executors are never patched."""
    base = previous.make_executor()
    scope = dict(base.execute_fixed_action.__globals__)
    plans = make_contract()
    registry = previous._make_output_registry(plans, base.custody)
    scope.update(plans=plans, is_archived=registry.is_archived, output_registry=registry)
    execute = previous.metadata._clone(base.execute_fixed_action, scope)

    def execute_fixed_action(*, q16c_source_bindings=None, **arguments):
        request = arguments['request']
        plan = request['action_inputs'].get('plan', {})
        if request['action_id'] != 'Q16c' or plan.get('schema_version') != contract.VERSION:
            return historical.make_executor().execute_fixed_action(q16c_source_bindings=q16c_source_bindings, **arguments)
        contract.validate_plan(plan)
        def run_archived_worker(argv, pass_fds, **values):
            deadline = min(values['global_deadline_ns'], values['monotonic_expiry_ns'],
                           time.monotonic_ns() + plan['budget']['setup_ns'])
            with sealed_worker_inputs(argv, pass_fds, plan=plan,
                    original_bindings=q16c_source_bindings, deadline_ns=deadline) as (args, fds):
                return base.run_archived_worker(args, fds, **values)

        local = {**scope, 'run_archived_worker': run_archived_worker}
        return previous.metadata._clone(execute, local)(**arguments)

    return types.SimpleNamespace(**{**vars(base), 'plans': plans, 'output_registry': registry,
        'is_archived': registry.is_archived, 'execute_fixed_action': execute_fixed_action})
