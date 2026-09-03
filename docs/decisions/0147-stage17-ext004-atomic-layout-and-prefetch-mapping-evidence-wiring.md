# 0147. Stage 17 S17-EXT-004 atomic-layout/software-prefetch-mapping evidence wiring

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

For two of the five kinds, the exact data each builder's `Input` struct
needs already exists, uncollected, in code `publish_q15_r` already calls:

- `RuntimeAtomicLayoutInput`'s ten fields map directly onto three
  already-invoked evidence objects: `ring.atomic_lock_free_evidence()`
  (`AtomicLockFreeEvidence`: `atomic_pointer_width_bytes`, `atomic_
  pointer_alignment_bytes`, `always_lock_free`, `runtime_lock_free`),
  `ring.layout_evidence()` (`LayoutEvidence`: `requested_cache_line_
  bytes`, `ownership_lines_separated`), and `termination.evidence()`
  (`TerminationEvidence`: `atomic_width_bytes`, `atomic_alignment_
  bytes`, `requested_cache_line_bytes`, `dedicated_cache_line`).
  `publish_q15_r` already computes `atomics`/`layout`/`termination_
  evidence` locals from these calls today, just to extract three
  booleans (`pointer_atomic_lock_free`, `queue_layout_passed`,
  `termination_atomic_lock_free`) for the existing `q15-r-output-v3.json`.
- `SoftwarePrefetchMappingInput`'s CPUID fields (`SoftwarePrefetchCapability
  Observation`: `maximum_extended_leaf`, `extended_leaf_ecx`, `prfchw_
  supported`) match what `AffinedObservationPreparation` already reads via
  its injected capability backend before every measurement (docs/
  PRODUCTION_RUNNER.md, "Affined preparation and static specialization
  boundary"). The four `*_codegen_passed`/`*_objdump_passed` booleans
  match the already-passing `runner-relax-codegen-check`/`runner-
  combined-codegen-check` CMake targets' own real, current results.

Neither kind requires new measurement capability -- only calling an
already-implemented, already-tested builder with data already computed,
and writing the resulting `QualificationArtifact.canonical_json` to disk
as a new, versioned artifact.

## Decision (proposed)

Extend `publish_q15_r` (or a narrow sibling function it calls) to:

1. Build a `RuntimeAtomicLayoutInput` from the `atomics`/`layout`/
   `termination_evidence` locals it already computes, call `make_
   runtime_atomic_layout_evidence`, and publish the resulting artifact
   alongside `q15-r-output-v3.json` via the existing `ArtifactSink`
   mechanism `publish_all` already uses.
2. Add a small Python-side authoring step (mirroring `author_stage17_*`
   tools already established for S17-EXT-002/003) that reads the CPUID
   observation the worker publishes plus the CMake codegen-check
   targets' own already-produced pass/fail state, builds a `Software
   PrefetchMappingInput`-shaped document, and either (a) calls a new,
   thin C++ CLI wrapper around `make_software_prefetch_mapping_
   evidence`, or (b) reproduces its (already-tested) canonicalization
   logic in Python against the same schema -- to be decided during
   implementation scoping, not here.
3. Extend `stage17-q15-r-output` to a new schema generation (`/4`) if the
   worker's own JSON output needs new fields to carry this data forward,
   or keep it purely additive as sibling artifacts -- to be decided
   during implementation.

This ADR does not implement any of the above; it records the real,
verified feasibility finding and the specific real code locations
involved, so a future implementation session does not need to re-derive
them.

## Consequences

- No real hardware time is required beyond what a normal Q15-R session
  already uses -- both fixes wire already-computed, already-real data.
- Requires a new C++ change to the compiled worker (recompiled release
  binary, new bundle profile, the full ADR-0138-style reachability
  lockstep this session has repeatedly had to complete for every new
  outer-policy generation).
- Does not by itself unblock S17-EXT-004 admission: `ACTUAL_CPU_
  MIGRATION`, `ADDRESS_RESIDENCY`, and `SELECTED_PAIR_CLOCK` remain
  blocked by separate, larger gaps (ADR-0148, ADR-0149, ADR-0150).
