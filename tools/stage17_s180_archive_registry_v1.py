"""Read-only S180 custody verification; no inverse or scientific validity claim.

The qualified parent must independently authenticate its request/admission and
prove actual broker/codec cleanup before acknowledging a parked native worker.
"""
from dataclasses import asdict
import hashlib

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
from stage17_formal_archive_registry_v1 import ARTIFACT_FIELDS, _bound, _ledger, _physical_metadata, same
import stage17_s180_checkpoint_v1 as contract


def verify_capture_metadata(*, store, capture, checkpoint_binding, receipt_binding,
                            decoder_profile, decoder_limits):
    return _verify_capture_metadata(store=store,capture=capture,checkpoint_binding=checkpoint_binding,
        receipt_binding=receipt_binding,decoder_profile=decoder_profile,decoder_limits=decoder_limits,
        physical_metadata=_physical_metadata)


def _verify_capture_metadata(*,store,capture,checkpoint_binding,receipt_binding,
                             decoder_profile,decoder_limits,physical_metadata):
    store._check()
    ordinal = archive.uint(capture["execution_ordinal"], "S180 execution ordinal")
    contract.capture_names(ordinal)
    if (store.family_id not in store._families
            or checkpoint_binding["file_name"] != f"s180-e{ordinal}-checkpoint.json"
            or receipt_binding["file_name"] != f"s180-e{ordinal}-archive-custody.json"):
        raise custody.CustodyError("S180 family or original receipt identity differs")
    family = store._families[store.family_id]
    observed = store.working.stat(follow_symlinks=False)
    same([observed.st_dev, observed.st_ino], [family["device"], family["inode"]], "S180 output root")
    final = _bound(store, store.working, checkpoint_binding, store.limits.max_checkpoint_bytes)
    receipt = _bound(store, store.working, receipt_binding, store.limits.max_record_bytes)
    if set(receipt) != contract.CUSTODY_FIELDS:
        raise custody.CustodyError("S180 custody field set differs")
    for key, expected in dict(schema_version=contract.CUSTODY_SCHEMA,
            program_scope_sha256=store.scope_sha256, plan_sha256=store.family_id,
            execution_ordinal=ordinal, checkpoint=checkpoint_binding,
            storage_extension=store._family_scope_fields()["storage_extension"],
            scientific_validity="NOT_ASSESSED", execution_authority=False, phase18_authority=False).items():
        same(receipt[key], expected, "S180 custody " + key)
    tip = _ledger(store, receipt["ledger_tip"])
    references = contract.original_references(final)
    rows = receipt["artifacts"]
    if type(rows) is not list or len(rows) != len(references):
        raise custody.CustodyError("S180 custody omits original publication prefix")
    sources, inventory = [], []
    for expected, row in zip(references, rows, strict=True):
        if type(row) is not dict or set(row) != ARTIFACT_FIELDS:
            raise custody.CustodyError("S180 custody artifact field set differs")
        name = expected["file_name"]
        artifact_id = store.family_id + ":" + name
        same(row["artifact_id"], artifact_id, "S180 artifact identity")
        same(row["expected_logical"], expected, "S180 original binding")
        logical = custody.BoundFile(**row["logical"])
        logical.binding()
        same(logical.file_name, name, "S180 logical file name")
        failure = custody.BoundFile(**row["failure_receipt"]) if row["failure_receipt"] is not None else None
        source = custody.SourceBinding(artifact_id, custody.BoundFile(**expected), logical.binding(), failure)
        if source.actual != source.expected.binding():
            if failure is None:
                raise custody.CustodyError("S180 discrepancy lacks retained evidence")
            discrepancy = _bound(store, store.root / "metadata", asdict(failure), store.limits.max_checkpoint_bytes)
            same(discrepancy, dict(schema_version="cpu-prefetch-stage17-source-discrepancy/1",
                artifact_id=artifact_id, plan_sha256=store.family_id, capture_ordinal=ordinal,
                expected=expected, observed=asdict(source.actual),
                scientific_validity="NOT_ASSESSED", execution_authority=False), "S180 discrepancy")
        elif failure is not None:
            raise custody.CustodyError("S180 matching bytes have an unexpected discrepancy")
        sources.append(source)
        released = _ledger(store, row["released_record"])
        if released["sequence"] > tip["sequence"]:
            raise custody.CustodyError("S180 release follows custody ledger tip")
        same(released["kind"], "RELEASED", "S180 release transition")
        same(released["artifact_id"], artifact_id, "S180 release identity")
        same(store._states.get(artifact_id), released, "S180 current durable state")
        payload = released["payload"]
        same(payload["source"], asdict(source), "S180 released source")
        same(payload["checkpoint_sha256"], checkpoint_binding["sha256"], "S180 release checkpoint")
        same(payload["storage_domain_id"], store.scope["storage_domain_id"], "S180 storage domain")
        archive_name = hashlib.sha256(artifact_id.encode()).hexdigest() + ".cpfa"
        same(row["archive_name"], archive_name, "S180 physical path")
        same(payload["archive_name"], archive_name, "S180 release physical path")
        same(payload["physical"], row["physical"], "S180 physical binding")
        role = contract.role_profile(ordinal, name)
        same(payload["role"], asdict(role), "S180 canonical role")
        header = payload["header"]
        for key, value in dict(artifact_id=artifact_id, canonical_size_bytes=logical.size_bytes,
                              canonical_sha256=logical.sha256).items():
            same(header[key], value, "S180 header " + key)
        phase = next((p for p in ("warmup", "measurement") if f"-{p}-" in name), None)
        run_id = capture["warmup_run_id" if phase == "warmup" else "run_id"] if phase else None
        same(header["phase"], phase, "S180 archive phase")
        same(header["run_id"], run_id, "S180 archive run")
        worker = next((w for w in ("producer", "consumer") if f"-{w}" in name), None)
        same(header["worker"], worker, "S180 archive worker")
        physical = physical_metadata(store.root / "archives" / archive_name,
            expected_header=header, role=role, physical=archive.PhysicalBinding(**row["physical"]),
            profile=decoder_profile, limits=decoder_limits)
        inventory.append(dict(artifact_id=artifact_id, logical=asdict(logical), archive_name=archive_name,
            physical=asdict(physical), header=header, role=asdict(role), released_record=row["released_record"]))
    contract.validate_checkpoint(final, plan_sha256=store.family_id, program_scope_sha256=store.scope_sha256,
        session_id=capture["session_id"], ordinal=ordinal, sources=tuple(sources))
    contract.require_private_cleanup_for_codec(final["native_result_after_private_cleanup"])
    successful = final["native_complete"] and all(s.actual == s.expected.binding() for s in sources)
    same(receipt["status"], "ARCHIVED_AND_RELEASED" if successful else "ARCHIVED_FAILED_EVIDENCE", "S180 custody status")
    store._read_bound(store.root / "metadata" / ("checkpoint-" + checkpoint_binding["sha256"] + ".json"),
        custody.BoundFile(**checkpoint_binding).binding(), store.limits.max_checkpoint_bytes)
    following = tip["sequence"] + 1
    if following >= len(store._record_bindings):
        raise custody.CustodyError("S180 custody registration is missing")
    registration = store.read_verified_record(store._record_bindings[following])
    same(registration["kind"], "CUSTODY_RECEIPT", "S180 custody registration kind")
    same(registration["payload"], dict(family_id=store.family_id,
        checkpoint_sha256=checkpoint_binding["sha256"], receipt=receipt_binding), "S180 custody registration")
    store._check()
    return dict(execution_ordinal=ordinal, checkpoint=checkpoint_binding, custody_receipt=receipt_binding,
        artifacts=inventory, continuation_allowed=successful, inverse_readback_performed=False,
        scientific_validity="NOT_ASSESSED", execution_authority=False, phase18_authority=False)
