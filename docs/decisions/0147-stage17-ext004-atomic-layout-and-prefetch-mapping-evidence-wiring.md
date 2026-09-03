# 0147. Stage 17 S17-EXT-004 runtime-atomic-layout evidence wiring

Status: PROPOSED

## Context

S17-EXT-004 (`stage17_operational_semantics_v4.py`'s own `EXPECTED_ROLES`)
requires five `QUALIFICATION_EVIDENCE` artifacts, one per `kind`:
`SELECTED_PAIR_CLOCK`, `RUNTIME_ATOMIC_LAYOUT`, `ACTUAL_CPU_MIGRATION`,
`ADDRESS_RESIDENCY`, `SOFTWARE_PREFETCH_MAPPING`, each validated against
`config/schemas/qualification-evidence-v1.schema.json`. Building S17-EXT-004
from the three real Q15-R sessions this session captured (`XEON-CPU-FETCH-
Q15R-SESSION-16E`/`-17`/`-18`) is currently impossible without fabricating
data: none of the granular per-field telemetry these schemas require has
ever been serialized by any real run.

Investigation found `include/cpu_prefetch/runner/qualification.hpp` /
`src/runner/qualification.cpp` already implement complete, schema-
validated, unit-tested typed builders for all five kinds
(`make_selected_pair_clock_evidence`, `make_runtime_atomic_layout_
evidence`, `make_actual_cpu_migration_evidence`, `make_address_residency_
evidence`, `make_software_prefetch_mapping_evidence`). Their only caller
anywhere in the repository is `tests/runner_model_test.cpp`, fed
synthetic input values. None is invoked from `src/runner/stage17_fixed_
action.cpp`, the real Q15-R worker entrypoint.

This ADR originally scoped both `RUNTIME_ATOMIC_LAYOUT` and `SOFTWARE_
PREFETCH_MAPPING` together, on the assumption that both were pure wiring
of already-real, already-computed data. Follow-up investigation (recorded
in ADR-0152) found that assumption wrong for `SOFTWARE_PREFETCH_MAPPING`:
its CPUID data is real but lives only in a separate, never-yet-run action
(`--execute-stage17-pilot-session-v1`), not Q15-R's own path, and its
codegen-verification booleans require dual-compiler (GCC + Clang)
infrastructure that does not exist anywhere in this repository (only GCC
is configured; no `--llvm-objdump` flag exists in `CMakeLists.txt`).
`SOFTWARE_PREFETCH_MAPPING` is out of scope for this ADR; see ADR-0152.

For `RUNTIME_ATOMIC_LAYOUT`, the exact data the builder's `Input` struct
needs already exists, uncollected, in code `publish_q15_r` already calls:
`RuntimeAtomicLayoutInput`'s ten fields map directly onto three already-
invoked evidence objects: `ring.atomic_lock_free_evidence()` (`AtomicLock
FreeEvidence`: `atomic_pointer_width_bytes`, `atomic_pointer_alignment_
bytes`, `always_lock_free`, `runtime_lock_free`), `ring.layout_evidence()`
(`LayoutEvidence`: `requested_cache_line_bytes`, `ownership_lines_
separated`), and `termination.evidence()` (`TerminationEvidence`: `atomic_
width_bytes`, `atomic_alignment_bytes`, `requested_cache_line_bytes`,
`dedicated_cache_line`). `publish_q15_r` already computes `atomics`/
`layout`/`termination_evidence` locals from these calls today, just to
extract three booleans (`pointer_atomic_lock_free`, `queue_layout_passed`,
`termination_atomic_lock_free`) for the existing `q15-r-output-v3.json`.

This kind requires no new measurement capability -- only calling an
already-implemented, already-tested builder with data already computed,
and writing the resulting `QualificationArtifact.canonical_json` to disk
as a new, versioned artifact.

## Decision (proposed)

Extend `publish_q15_r` (or a narrow sibling function it calls) to build a
`RuntimeAtomicLayoutInput` from the `atomics`/`layout`/`termination_
evidence` locals it already computes, call `make_runtime_atomic_layout_
evidence`, and publish the resulting artifact alongside `q15-r-output-v3.
json` via the existing `ArtifactSink` mechanism `publish_all` already
uses.

This ADR does not implement the above; it records the real, verified
feasibility finding and the specific real code locations involved, so a
future implementation session does not need to re-derive them.

## Consequences

- No real hardware time is required beyond what a normal Q15-R session
  already uses -- this wires already-computed, already-real data.
- Requires a new C++ change to the compiled worker (recompiled release
  binary, new bundle profile, the full ADR-0138-style reachability
  lockstep this session has repeatedly had to complete for every new
  outer-policy generation).
- Does not by itself unblock S17-EXT-004 admission: `ACTUAL_CPU_
  MIGRATION`, `ADDRESS_RESIDENCY`, `SELECTED_PAIR_CLOCK`, and now
  `SOFTWARE_PREFETCH_MAPPING` remain blocked by separate, larger gaps
  (ADR-0148, ADR-0149, ADR-0150, ADR-0152).
