# 0147. Stage 17 S17-EXT-004 runtime-atomic-layout evidence wiring

Status: ACCEPTED

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

## Decision

Extend `publish_q15_r` to build the `RuntimeAtomicLayoutInput`-shaped
fields from the `atomics`/`layout`/`termination_evidence` locals it
already computes, and publish them as a new, additive sibling artifact
alongside `q15-r-output-v3.json` via the existing `ArtifactSink`
mechanism `publish_all` already uses.

## Implementation

`publish_q15_r` now also publishes `Q15_R_ATOMIC_LAYOUT_RAW` (`q15-r-
atomic-layout-raw-v1.json`, new schema `stage17-q15-r-atomic-layout-raw-
v1.schema.json`), a pure sibling addition -- `q15-r-output-v3.json`
itself is unchanged. Building this surfaced a real, previously-latent
bug: `qualification-evidence-v1.schema.json`'s `protocol_version` const
was pinned to the stale `2.0.0-pre.2` while the live `protocol::
kProtocolVersion` is `2.0.0-pre.3`; every `make_*_evidence` builder would
have produced schema-invalid output. Fixed alongside this change (both
the schema const and `tools/check_qualification_schema.py`'s matching
synthetic fixture).

Verified: `cmake --build --preset dev-gcc` (full default target set)
succeeds; `cpu_prefetch_runner_tests` (20/20, including the
`Stage17FixedAction` suite) passes; `check_qualification_schema.py` and
`check_runner_schema.py` both pass.

Chose to build the raw, un-enveloped fields as a new artifact (rather
than calling `make_runtime_atomic_layout_evidence` directly from the
worker) because `QualificationIdentity`'s `stand_id`/`binding_id`/
`binary_sha256` fields are external-identity concepts the compiled
worker cannot cheaply and correctly self-derive; a later Python
authoring tool (mirroring ADR-0151's pattern) wraps this raw artifact
into the final schema-compliant envelope using real, externally-known
facts, the same way `RUNTIME_IDENTITY`/`PLATFORM_MANIFEST` were already
hand-authored this session.

## Real envelope (session -20, toward an S17-EXT-004 admission attempt)

Exercised for real: real session `-20` (run after this ADR's wiring was
in the staged bundle) produced a real `q15-r-atomic-layout-raw-v1.json`
(sha256 `5e5d0d617c4982c9f56a915d4ffb9e7a0c4a35cce3a354a649a072564c0921fe`,
511 bytes, confirmed by reading it directly off the stand over a
read-only SSH session). `cpu_prefetch_q15_qualification_evidence_tool`
built the real `RUNTIME_ATOMIC_LAYOUT` envelope from it (identity bound
to session `-20`'s real facts, matching ADR-0151/0152's pattern),
`eligible: true`, saved to `/home/omaltsev/stage17-owner-evidence/
ext004-authoring-20/qualification-evidence-runtime-atomic-layout-
20.json`, validates against `qualification-evidence-v1.schema.json`.

## Consequences

- No real hardware time is required beyond what a normal Q15-R session
  already uses -- this wires already-computed, already-real data.
- Now exercised for real end to end: real session `-20` produced the raw
  artifact, and a real, eligible, schema-valid envelope was built from
  it (see above).
- Does not by itself unblock S17-EXT-004 admission: `ADDRESS_RESIDENCY`
  has no raw data for session `-20` (published only after ADR-0149) and
  `SELECTED_PAIR_CLOCK` has no real raw data anywhere yet. `ACTUAL_CPU_
  MIGRATION` (ADR-0148) and `SOFTWARE_PREFETCH_MAPPING` (ADR-0152) also
  now have real, eligible session `-20` envelopes.
