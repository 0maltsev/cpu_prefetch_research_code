"""S180 original-artifact and private-cleanup contract; custody is not science."""
from __future__ import annotations
from dataclasses import asdict
from stage17_formal_archive_v1 import ArchiveError, RoleProfile, canonical, sha, uint

SCHEMA = "cpu-prefetch-stage17-s180-capture-checkpoint/1"
CUSTODY_SCHEMA = "cpu-prefetch-stage17-s180-archive-custody/1"
CUSTODY_FIELDS = frozenset(("schema_version program_scope_sha256 plan_sha256 execution_ordinal checkpoint "
    "ledger_tip artifacts status storage_extension scientific_validity execution_authority phase18_authority").split())
APPROVAL_SHA256 = "3673f215a10cac54577acb5fa85b5adabc4262eb63bcf260c6ec15143e822ab7"
BLUEPRINT_SHA256 = "e95183365023a06b9da0d6cdff042bce556b9eb60c701dfb0f9e6df6ca22685c"
FIELDS = frozenset(("schema_version session_id plan_sha256 program_scope_sha256 execution_ordinal "
    "native_complete native_result_after_private_cleanup artifacts shared_data_still_family_owned "
    "scientific_validity execution_authority phase18_authority").split())
NATIVE_FIELDS = frozenset(("stop session clock_origin core_mapping monitor_mapping controller_stack "
    "worker_mappings worker_stacks cleanup_scope publication_attempted publication_succeeded").split())
REFERENCE_FIELDS = frozenset("role schema_identity media_type file_name size_bytes sha256".split())


def capture_names(ordinal):
    uint(ordinal, "S180 execution ordinal")
    if ordinal >= 180:
        raise ArchiveError("S180 execution ordinal outside fixed family")
    base = f"s180-e{ordinal}"
    return tuple([f"{base}-{phase}-{worker}.bin" for phase in ("warmup", "measurement")
                  for worker in ("producer", "consumer")] + [base + "-node-order.bin"] +
                 [f"{base}-{phase}-schedule.bin" for phase in ("warmup", "measurement")] + [base + "-control.json"])


def artifact_identity(ordinal, name):
    if name not in capture_names(ordinal):
        raise ArchiveError("foreign S180 artifact")
    if name.endswith("-control.json"):
        return "S180_CAPTURE_CONTROL", "cpu-prefetch-stage17-s180-capture-control/1", "application/json"
    if name.endswith("-node-order.bin"):
        return "S180_NODE_ORDER", "NODEORDER-U64LE-v1", "application/octet-stream"
    if name.endswith("-schedule.bin"):
        return "S180_PREPARED_SCHEDULE", "SCHEDULE-DEADLINES-U64LE-v1", "application/octet-stream"
    return "S180_PRIMARY_RAW", "RAW-OBS-U64LE-LP-RUNID-v1", "application/octet-stream"


def role_profile(ordinal, name):
    role, fmt, _ = artifact_identity(ordinal, name)
    layout = ("bytes" if name.endswith("-control.json") else
              "u64" if name.endswith(("-node-order.bin", "-schedule.bin")) else
              "producer" if name.endswith("-producer.bin") else "consumer")
    return RoleProfile(role, fmt, layout)


def original_references(document):
    entries = document.get("artifacts")
    if type(entries) is not list:
        raise ArchiveError("S180 artifact list missing")
    ordinal = uint(document.get("execution_ordinal"), "S180 ordinal")
    names = capture_names(ordinal)
    if len(entries) > len(names):
        raise ArchiveError("S180 artifact count exceeds complete set")
    out = []
    for index, entry in enumerate(entries):
        if type(entry) is not dict or set(entry) != REFERENCE_FIELDS or entry["file_name"] != names[index]:
            raise ArchiveError("S180 source is not an exact publication prefix")
        role, fmt, media = artifact_identity(ordinal, entry["file_name"])
        if (entry["role"], entry["schema_identity"], entry["media_type"]) != (role, fmt, media):
            raise ArchiveError("S180 original role/format/media differs")
        uint(entry["size_bytes"], "S180 source bytes")
        sha(entry["sha256"], "S180 original hash")
        out.append({k: entry[k] for k in ("file_name", "size_bytes", "sha256")})
    return out


def validate_checkpoint(document, *, plan_sha256, program_scope_sha256, session_id, ordinal, sources):
    if (type(document) is not dict or set(document) != FIELDS or document["schema_version"] != SCHEMA
            or document["plan_sha256"] != sha(plan_sha256, "S180 plan")
            or document["program_scope_sha256"] != sha(program_scope_sha256, "S180 program")
            or document["session_id"] != session_id or type(session_id) is not str or not session_id
            or type(document["execution_ordinal"]) is not int or document["execution_ordinal"] != ordinal
            or type(document["native_complete"]) is not bool
            or document["shared_data_still_family_owned"] is not True
            or document["scientific_validity"] != "NOT_ASSESSED"
            or document["execution_authority"] is not False or document["phase18_authority"] is not False):
        raise ArchiveError("S180 checkpoint scope/authority differs")
    refs = original_references(document)
    if canonical(refs) != canonical([asdict(s.expected) for s in sources]):
        raise ArchiveError("S180 checkpoint original source bindings differ")
    final = document["native_result_after_private_cleanup"]
    if (type(final) is not dict or set(final) != NATIVE_FIELDS
            or final["cleanup_scope"] != "PRIVATE_CAPTURE_ONLY_SHARED_DATA_REMAINS_FAMILY_OWNED"
            or any(type(final[k]) is not bool for k in ("publication_attempted", "publication_succeeded"))):
        raise ArchiveError("S180 returned native result shape/scope differs")
    stop = uint(final["stop"], "S180 native stop")
    if stop > 14:
        raise ArchiveError("S180 native stop outside registry")
    complete = (stop == 14 and final["publication_attempted"] and final["publication_succeeded"]
                and len(refs) == len(capture_names(ordinal)))
    if document["native_complete"] is not complete:
        raise ArchiveError("S180 native-completion claim differs")
    if complete:
        maps, stacks = final["worker_mappings"], final["worker_stacks"]
        if type(maps) is not list or len(maps) != 3 or type(stacks) is not list or len(stacks) != 2:
            raise ArchiveError("S180 completed checkpoint omits private mappings/stacks")
        for value in [*maps, *stacks, final["core_mapping"], final["monitor_mapping"], final["controller_stack"]]:
            if type(value) is not dict or value.get("cleanup_attempted") is not True:
                raise ArchiveError("S180 completed checkpoint lacks private cleanup")
            for field in ("unlock", "unmap"):
                if canonical(value.get(field)) != canonical(dict(return_value=0, error_number=0)):
                    raise ArchiveError("S180 completed checkpoint reports failed cleanup")
        for value in [*stacks, final["controller_stack"]]:
            thread = value.get("thread")
            if (type(thread) is not dict or type(thread.get("create")) is not int or thread["create"] != 0
                    or type(thread.get("join")) is not int or thread["join"] != 0):
                raise ArchiveError("S180 completed checkpoint lacks actual joins")


def require_private_cleanup_for_codec(final):
    """Shared family maps may remain; an unreleased private map may not."""
    values = [final["core_mapping"], final["monitor_mapping"], final["controller_stack"]]
    for field, length in (("worker_mappings", 3), ("worker_stacks", 2)):
        group = final[field]
        if group is not None:
            if type(group) is not list or len(group) != length:
                raise ArchiveError("S180 private cleanup group is malformed")
            values.extend(group)
    for value in values:
        if type(value) is not dict or "mapping" not in value:
            raise ArchiveError("S180 lacks original private mapping presence evidence")
        mapping = value["mapping"]
        if mapping is None:
            continue
        if type(mapping) is not dict or set(mapping) != {"address", "error_number"}:
            raise ArchiveError("S180 original private mapping result is malformed")
        if mapping["address"] is not None:
            if (value.get("cleanup_attempted") is not True
                    or canonical(value.get("unmap")) != canonical(dict(return_value=0, error_number=0))):
                raise ArchiveError("S180 private mapping remains live; no codec is permitted")
