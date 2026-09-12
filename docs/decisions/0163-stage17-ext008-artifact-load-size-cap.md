# ADR-0163: Stage 17 S17-EXT-008 manifest artifact load-size cap

- **Status:** `ACCEPTED`
- **Decision ID:** D-163
- **Classification:** implementation correctness, defensive-bound
  adjustment for a real, legitimately-sized artifact
- **Owner:** repository/build/runner owner
- **Gate:** before any real `S17-EXT-008` admission can be attempted

## Context

Attempting to admit the real, locally-validated `S17-EXT-008` pilot
plan (`config/stage17/ext008-pilot-plan-standv2-30.json`,
`68,832,714` bytes) failed with `"artifact size/type differs from its
bounded contract"`. Root-caused by direct code reading, not assumed:
`tools/stage17_operational_semantics_v4.py`'s `_artifact_content`
rejects any fully-parsed (`load=True`) artifact larger than
`64 * 1024 * 1024` bytes (64 MiB) -- unconditionally, with no
per-role exception. `S17-EXT-008`'s single required `PILOT_PLAN_V4`
artifact must be fully parsed (`pilot_plan_runtime.validate()` needs
the parsed document to cross-check every one of its 540 real runs), so
it is subject to this cap, and exceeds it by about 1.7 MiB.

The real size is not padding or redundancy introduced by this
engagement's own choices: measured directly (`one run: 68,239 bytes`,
of which `schedule_deadline_ticks` + `warmup_schedule_deadline_ticks`
together account for roughly 85%), the bulk is the genuine,
schema-required per-run `schedule_deadline_ticks`/
`warmup_schedule_deadline_ticks` arrays for 540 real runs --
`config/schemas/stage17-pilot-plan-v4.schema.json`'s `run` definition
requires each run object to carry its own complete copy of both
arrays; there is no more compact in-schema representation available
without changing the schema itself.

This is not the first time this engagement has hit an artifact-size
bound sized for smaller inputs than a real, legitimate artifact needs:
an earlier commit ("Raise the Python-side MAX_BOUND_INPUT_BYTES to
match the C++ side") raised a comparable bound for exactly this
reason.

## Decision

Ship `tools/stage17_operational_semantics_v10.py`, an additive
successor (`import stage17_operational_semantics_v4 as base`,
monkey-patching `base._artifact_content`) following the same pattern
already established for `stage17_operational_semantics_v9.py`
(ADR-0160) and `stage17_pilot_plan_v5.py` (ADR-0162) --
`_artifact_content` is called via a bare name from `_read_artifacts`
within the same module, a free-variable lookup resolved fresh at call
time, so patching the module attribute is sufficient.

A faithful full copy of `_artifact_content`, changed only to replace
the hardcoded `64 * 1024 * 1024` bound with a named
`LOAD_ARTIFACT_MAX_BYTES = 128 * 1024 * 1024` (128 MiB) -- comfortable
headroom over the real artifact's size, while remaining a bounded,
defensive limit rather than no limit at all.

## Effects

- `S17-EXT-008`'s real `PILOT_PLAN_V4` artifact (68,832,714 bytes) now
  loads successfully during manifest verification.
- On the real, already-sealed admission root, `S17-EXT-008` admission
  is run through a wrapper that imports `stage17_operational_
  semantics_v9.py` (ADR-0160), `stage17_pilot_plan_v5.py` (ADR-0162),
  and this file together, for their import-time monkey-patch side
  effects, before importing `stage17_operational_cli_v11`.
- A future pilot-candidate bundle rebuild should fold `v10.py` into the
  real import chain (analogous to `v9.py`/`v5.py`/`v18.py`/`v6.py`) so
  a fresh journal does not need the wrapper.
