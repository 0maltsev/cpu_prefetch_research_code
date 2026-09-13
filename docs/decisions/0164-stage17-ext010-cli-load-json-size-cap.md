# ADR-0164: Stage 17 S17-EXT-010 CLI load_json size cap

- **Status:** `ACCEPTED`
- **Decision ID:** D-164
- **Classification:** implementation correctness, defensive-bound
  adjustment for a real, legitimately-sized artifact
- **Owner:** repository/build/runner owner
- **Gate:** before any real `S17-EXT-010` (`STAGE17-BLINDED-PILOT`
  authorization) admission can be attempted

## Context

Drafting the real `S17-EXT-010` authorization failed at `author-request`
with `"not a bounded regular file: .../action-inputs.json"`.
Root-caused by direct code reading, not assumed:
`tools/stage17_operational_cli_v11.py`'s own `load_json` -- a
completely separate function from `stage17_operational_semantics_v4.py`'s
`_artifact_content` (already raised to 128 MiB in ADR-0163) -- caps any
local JSON file it reads at 64 MiB, unconditionally. `load_json` is
the CLI's local-file reader, called from `author_request` (reading
`--action-inputs`), `author_authorization` (reading the just-authored
request file back), `append_resolution` (reading `--repository-
evidence` files), and other commands.

`STAGE17-BLINDED-PILOT`'s real `action_inputs` must embed the complete,
real, admitted `S17-EXT-008` pilot plan inline as `action_inputs.
pilot_plan` -- required verbatim, byte-for-byte, by `stage17_phase_
controller_v10.py`'s `_validate_action_inputs` (`values["pilot_plan"]
!= plan_context["pilot_plan"]` raises `"pilot action differs from
admitted frozen plan"`). The real `action-inputs.json` input is
74,831,673 bytes; the resulting request document is comparably large.
Both are read back via `load_json` repeatedly through the real
admission flow (`author-authorization` immediately, and every later
journal re-validation) -- not a one-off cost.

## Decision

Ship `tools/stage17_operational_cli_v12.py`, an additive successor
(`import stage17_operational_cli_v11 as base`, monkey-patching
`base.load_json`) following the same pattern as `stage17_pilot_plan_
v5.py` (ADR-0162) and `stage17_operational_semantics_v10.py`
(ADR-0163) -- `load_json` is called via a bare name from every site
above, all within the same module, a free-variable lookup resolved
fresh at call time, so patching the module attribute is sufficient.

A faithful full copy of `load_json`, changed only to replace the
hardcoded `64 * 1024 * 1024` bound with a named `LOAD_JSON_MAX_BYTES =
128 * 1024 * 1024` (128 MiB), matching ADR-0163's bound for
consistency.

## Effects

- `author-request`/`author-authorization` for `S17-EXT-010` can now
  read the real, 74.8 MB `action-inputs.json` and the resulting
  request document.
- On the real, already-sealed admission root, `S17-EXT-010` drafting
  and admission is run through a wrapper that imports `stage17_
  operational_semantics_v9.py` (ADR-0160), `stage17_pilot_plan_v5.py`
  (ADR-0162), `stage17_operational_semantics_v10.py` (ADR-0163), and
  this file together, for their import-time monkey-patch side effects,
  before importing `stage17_operational_cli_v11`.
- A future pilot-candidate bundle rebuild should fold `v12.py` into the
  real import chain (analogous to `v10.py`/`v9.py`/`v5.py`) so a fresh
  journal does not need the wrapper.
