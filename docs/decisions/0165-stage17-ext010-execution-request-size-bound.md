# ADR-0165: Stage 17 STAGE17-BLINDED-PILOT execution-time request size bound

- **Status:** `ACCEPTED`
- **Decision ID:** D-165
- **Classification:** implementation correctness, defensive-bound
  adjustment for a real, legitimately-sized artifact
- **Owner:** repository/build/runner owner
- **Gate:** before any real `STAGE17-BLINDED-PILOT` `execute-action` can
  succeed

## Context

The real `STAGE17-BLINDED-PILOT` execution attempt on standv2-30
failed at its very first step, before any real hardware run started
(pilot output directory empty, no partial evidence lost), with
`"fixed request exceeds its fixed size limit"`. Root-caused by direct
code reading: `stage17_phase_controller_v18.py`'s `prepare_action`
reads the real request file via `controller_support._read_binding(
authorization["request_binding"], "fixed request")`, which enforces
`stage17_phase_controller_v2.py`'s `MAX_BOUND_INPUT_BYTES` -- already
raised once, from 16 MiB to 64 MiB, by `stage17_phase_controller_v17.py`
(ADR-0159), for Q16b's real ~47 MB request. The real `STAGE17-BLINDED-
PILOT` request embeds the complete, real, admitted `S17-EXT-008` pilot
plan verbatim (required by `stage17_phase_controller_v10.py`'s
`_validate_action_inputs`), making the real request file 68,835,354
bytes -- about 1.65 MB past the 64 MiB (67,108,864-byte) ceiling, never
anticipated to need to grow again for the pilot's own, larger request.

As `stage17_phase_controller_v17.py`'s own docstring already
establishes, this bound gates nothing about worker/evidence identity --
it is purely an arbitrary file-size ceiling, so raising it again
changes no security property.

## Decision

Ship `tools/stage17_phase_controller_v20.py`, an additive successor
following the exact same pattern as `stage17_phase_controller_v17.py`
(ADR-0159) -- `import stage17_phase_controller_v2 as _v2; _v2.
MAX_BOUND_INPUT_BYTES = 128 * 1024 * 1024`, module-level attribute
mutation, re-exporting everything else from `stage17_phase_controller_
v19` unchanged.

## Effects

- `execute-action` for `STAGE17-BLINDED-PILOT` can now read the real,
  68.8 MB request file.
- On the real, already-sealed admission root, execution is run through
  a wrapper that imports `stage17_operational_semantics_v9.py`
  (ADR-0160), `stage17_pilot_plan_v5.py` (ADR-0162), `stage17_
  operational_semantics_v10.py` (ADR-0163), `stage17_operational_
  cli_v12.py` (ADR-0164), and this file together, for their import-time
  monkey-patch side effects, before importing `stage17_operational_
  cli_v11`.
- A future pilot-candidate bundle rebuild should fold `v20.py` into the
  real import chain (analogous to `v17.py`/`v10.py`/`v9.py`) so a fresh
  journal does not need the wrapper.
