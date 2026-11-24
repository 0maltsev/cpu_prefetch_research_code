"""D233 prospective physical-storage arithmetic, without execution authority.

Logical output remains the sum of all original canonical capture bounds. The
physical quota is shared by the complete future formal program, not reset for
each family. Fresh availability and ledger usage are separate runtime checks.
"""
from __future__ import annotations

from dataclasses import dataclass

from stage17_discovery_contract_v2 import ContractError, _constant, _object, _text, _uint, _sum, _product

POLICY = "EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1"
VERSION = "cpu-prefetch-stage17-formal-storage-plan/1"
QUOTA = 6_000_000_000_000
WORKSPACE = 512 * 1024**3
SCRATCH = 256 * 1024**3
RESERVE = 16 * 1024**3
CODEC_MEMORY = 2 * 1024**3
MAX_I64 = (1 << 63) - 1
FIELDS = ("schema_version program_id policy_id implementation_profile_sha256 program_scope_sha256 "
          "archive_quota_bytes workspace_bytes analysis_scratch_bytes disk_reserve_bytes "
          "codec_address_space_bytes broker_address_space_bytes codec_processes per_capture_archive_ns "
          "archive_staging_bytes capture_workspace_overhead_bytes checkpoint_bytes "
          "analysis_capture_workspace_bytes")


@dataclass(frozen=True)
class StorageExtent:
    program_id: str
    required_initial_free_bytes: int
    peak_capture_workspace_bytes: int
    minimum_family_watchdog_ns: int
    minimum_family_memory_bytes: int
    logical_output_bound_bytes: int
    archive_quota_bytes: int = QUOTA
    completion_guaranteed: bool = False
    execution_authority: bool = False


def _require(condition, message):
    if not condition:
        raise ContractError("formal storage: " + message)


def validate_storage_plan(storage, captures, family, *, native_family_watchdog_ns,
                          native_family_memory_bytes, logical_output_bound_bytes):
    """Validate against already recomputed native extents; never alter their caps.

    ``captures`` contains the declared native capture budgets. The native family
    validator remains responsible for complete coverage, original row layouts,
    publication allocation, metadata maxima and every measurement-time bound.
    A finite staging ceiling may stop an incompressible capture; it is not a
    prediction or proof that its original bytes will compress below that ceiling.
    """
    plan = _object(storage, FIELDS, "storage")
    _constant(plan["schema_version"], VERSION, "storage.schema_version")
    _constant(plan["policy_id"], POLICY, "storage.policy_id")
    _text(plan["program_id"], "storage.program_id")
    _text(plan["implementation_profile_sha256"], "storage.profile", r"[0-9a-f]{64}")
    _text(plan["program_scope_sha256"], "storage.program_scope", r"[0-9a-f]{64}")
    fixed = dict(archive_quota_bytes=QUOTA, workspace_bytes=WORKSPACE,
                 analysis_scratch_bytes=SCRATCH, disk_reserve_bytes=RESERVE,
                 codec_address_space_bytes=CODEC_MEMORY, codec_processes=1)
    for key, expected in fixed.items():
        _uint(plan[key], "storage." + key, 1)
        _constant(plan[key], expected, "storage." + key)
    positive = ("broker_address_space_bytes", "per_capture_archive_ns", "archive_staging_bytes",
                "capture_workspace_overhead_bytes", "checkpoint_bytes",
                "analysis_capture_workspace_bytes")
    for key in positive:
        _uint(plan[key], "storage." + key, 1)
    _require(plan["broker_address_space_bytes"] <= CODEC_MEMORY, "broker address-space ceiling exceeds 2 GiB")
    _require(plan["per_capture_archive_ns"] <= MAX_I64, "archive deadline overflows native duration")
    _require(0 < len(captures), "empty family")
    _require(plan["archive_staging_bytes"] <= QUOTA, "staging exceeds shared quota")
    largest = max(_uint(c.max_output_bytes, "capture.output", 1) for c in captures)
    _require(all(c.metadata_output_bytes >= plan["checkpoint_bytes"] for c in captures),
             "capture metadata cannot hold its final checkpoint")
    workspace = _sum([largest, plan["archive_staging_bytes"],
                      plan["capture_workspace_overhead_bytes"]], "storage.workspace")
    _require(workspace <= WORKSPACE, "canonical capture plus staging exceeds workspace")
    _require(largest <= plan["analysis_capture_workspace_bytes"] <= SCRATCH,
             "one-capture analysis bound omits canonical spool or exceeds scratch")
    _require(family.analysis_scratch_bytes == SCRATCH and family.disk_reserve_bytes == RESERVE,
             "family scratch/reserve differs from approved storage policy")
    disk = _sum([QUOTA, WORKSPACE, SCRATCH, RESERVE], "storage.initial_disk")
    _require(family.required_free_disk_bytes >= disk, "initial admission omits quota/workspace/scratch/reserve")
    native_time = _uint(native_family_watchdog_ns, "native.watchdog", 1)
    watchdog = _sum([native_time, _product(len(captures), plan["per_capture_archive_ns"],
                                        "storage.archive_time")], "storage.family_time")
    _require(watchdog <= family.watchdog_ns <= MAX_I64, "family deadline omits cold archive time")
    # Conservative overlap reservation: allocator retention and source vectors
    # receive no memory credit merely because native measurement has ended.
    memory = _sum([_uint(native_family_memory_bytes, "native.memory", 1), CODEC_MEMORY,
                   plan["broker_address_space_bytes"]],
                  "storage.family_memory")
    _require(family.memory_bytes >= memory, "family memory omits the codec child")
    output = _uint(logical_output_bound_bytes, "logical.output", 1)
    _require(family.max_output_bytes >= output, "logical emitted output was reduced")
    return StorageExtent(plan["program_id"], disk, workspace, watchdog, memory, output)


def remaining_admission_bytes(*, retained_program_bytes):
    """The ledger must independently prove this whole-program retained usage."""
    used = _uint(retained_program_bytes, "program.retained_bytes")
    _require(used <= QUOTA, "existing shared program quota is exceeded")
    return _sum([QUOTA - used, WORKSPACE, SCRATCH, RESERVE], "storage.remaining_disk")
