# ADR-0127: Stage 17 phase-controller runtime-context restoration

- **Status:** `ACCEPTED`
- **Decision ID:** D-127
- **Classification:** implementation correctness, latent defect in already-
  accepted production code, request-preparation binding
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `author-request` for Q15-R, Q15-W, Q16a, Q16b,
  Q16c, or the blinded pilot can succeed

## Context

While rebasing the hermetic Stage 17 handoff rehearsal
(`tools/check_stage17_production_handoff_v4.py`) to exercise the real,
currently accepted admission chain end to end, request preparation for
Q15-R failed inside already-accepted, hash-pinned production code:
`tools/stage17_operational_cli_v10.py` calls
`controller._runtime_from_context(action, validation)` at its
`author-request` implementation, where `controller` is
`tools/stage17_phase_controller_v8.py`. That module does not define
`_runtime_from_context` -- confirmed directly with
`hasattr(stage17_phase_controller_v8, '_runtime_from_context')` returning
`False` -- and does not re-export it from any predecessor. The function
existed in `stage17_phase_controller_v2.py` through `_v4.py` and was
dropped somewhere in the `v4`-to-`v8` succession without a replacement.
No prior test or real usage ever exercised `author-request`, so this
defect has been sitting undetected in the accepted `v18` closure.

The function's two branches were checked directly against the current
real data shapes before drafting this decision, not assumed compatible:
for `Q15-R`/`Q15-W`, `S17-EXT-003`'s admitted `semantic_context` still
carries a `runtime` key whose `measurements` sub-object has exactly the
fields the `v4` implementation read (`worker_path`, `worker_role`,
`runtime_profile`, `worker_size_bytes`, `worker_sha256`,
`supported_actions`), because `stage17_operational_semantics_v4.py`'s
`_verify_extracted_release` still populates a `RUNTIME_IDENTITY` typed
record with those exact keys. For every other action, `S17-EXT-006`'s
admitted `semantic_context` still carries `release_artifact_path`,
`release_artifact_size_bytes`, `release_artifact_sha256`,
`release_artifact_role`, `runtime_profile`, and `supported_actions` as
flat keys, exactly as the `v4` implementation expected. The constant
`"STAGE17-FIXED-ACTION-WORKER-v4"` is still the correct, unchanged
compiled-worker runtime-profile identity. This is a restoration of
verified-compatible logic, not a redesign.

## Decision

Add `tools/stage17_phase_controller_v9.py` as an additive successor to
`stage17_phase_controller_v8.py`, re-exporting every `v8` name unchanged
and adding back `_runtime_from_context`, ported from `v4`'s
implementation with no behavioral change beyond what the current data
shapes above already require (none, since they matched exactly).
`stage17_operational_cli_v10.py` and `stage17_phase_controller_v8.py`
remain byte-identical; `v8`'s own accepted closure is untouched. A new
operational-policy successor binds `stage17_phase_controller_v9.py`'s
real hash in place of `v8`'s in the same additive, non-promoting pattern
ADR-0124 through ADR-0126 already established: sealing a new successor
does not itself make it the policy `stage17-operational-successor-check`
reports as current, and does not grant any stand, execution, Q15, or
pilot authority by itself.

## Effects

`author-request --action Q15-R` (and, by the same restored function,
Q15-W/Q16a/Q16b/Q16c/the blinded pilot) becomes callable through the new
successor without raising `AttributeError`. No scientific design, request
schema, or authority boundary changes. This does not authorize a real
Q15-R/Q15-W/Q16/pilot request; it only fixes a defect that would have
blocked one.

## Verification and supersession

Acceptance requires: a regression proving the unmodified `v8` chain is
completely unaffected and importable/usable exactly as before; a positive
test that `author-request --action Q15-R` (and, if practical, the other
five actions) succeeds through the new successor using the same synthetic
`S17-EXT-002`/`003`/`006` fixtures the hermetic handoff rehearsal already
builds; confirmation via `git diff` that no file in the accepted `v18`
closure changed. Any later change to what `_runtime_from_context` reads
or how request preparation binds runtime/release evidence requires
another prospective successor under the same standard applied since
ADR-0108.
