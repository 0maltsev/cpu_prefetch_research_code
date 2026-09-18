# ADR-0169: Stage 17 pilot runner-admission hash canonicalization

- Status: `ACCEPTED`
- Date: 2026-09-18
- Classification: Real bug fix, tooling only (no worker/bundle change)
- Decision owners: Protocol owner; repository owner
- Protocol version: `2.0.0-pre.3`
- Supersedes: None

## Context

The first-ever real execution attempt of the compiled `STAGE17-BLINDED-
PILOT` action failed on its very first real run with `S17-RUN-ADMISSION-
HASH: sealed runner admission/evidence bytes drifted`. The real,
compiled worker's own admission-ticket check
(`load_sealed_runner_ticket`, `src/runner/stage17_fixed_action.cpp`)
recomputes `runner_admission_sha256`/`runner_evidence_set_sha256` via
`protocol::json::canonicalize` (`src/protocol/json.cpp`: sorted keys,
compact separators, **no** trailing newline). `tools/
stage17_pilot_plan_v4.py`'s own `canonical()` -- used both to construct
those two fields when authoring a pilot plan, and by `_validate_admission`
to independently re-verify them at admission time -- appends `"\n"`
before hashing. These two canonicalizations can never agree for those two
fields: a value the Python-side admission accepts is guaranteed to fail
the compiled worker's own independent check, and vice versa.

Confirmed directly, this session, against the real admitted EXT-008
plan: the stored `runner_admission_sha256` for the run that failed
matches `sha256(canonical(admission) + "\n")` and does not match
`sha256(canonical(admission))` (no newline) -- the value the compiled
worker actually computes.

This was never caught before because, as far as this engagement's
history shows, no session had gotten a real `STAGE17-BLINDED-PILOT`
execution to actually reach the compiled worker's run loop before now --
Q16a/Q16b/Q16c never exercise this specific check, since their own
Python-side admission never independently re-verifies a runner-admission
hash the way the pilot's `_validate_admission` does.

## Decision

Add `tools/stage17_pilot_plan_v6.py`, an additive successor to `v5.py`
following this repository's established monkey-patch convention. It
redefines `_validate_admission` with one narrow change: the two
comparisons against `runner_admission_sha256`/`runner_evidence_set_sha256`
use a canonicalization with no trailing newline (`canonical_no_newline`),
matching `protocol::json::canonicalize` exactly. Every other use of
`canonical()` is untouched, because no other `canonical()`-derived field
(`plan_core_sha256`, `frozen_schedule_hash`, `seed_derivation_hash`) is
independently re-verified by the compiled worker at runtime -- only
`runner_admission`/`runner_evidence_set` go through
`load_sealed_runner_ticket`.

Because `v5.py` redefines `validate()` in full (importing
`_validate_admission` by name into its own module rather than doing a
bare-attribute lookup against `v4.py`), the fix reassigns
`stage17_pilot_plan_v5._validate_admission` directly -- the same
free-variable-resolution rule this repository's own `v10.py`/`v18.py`
docstrings already document for other functions.

This is a tooling-only fix: the compiled worker and the release bundle
are unchanged. Only a pilot plan authored (or re-authored) against the
corrected hash convention can pass both the Python-side admission check
and the compiled worker's own check. Any pilot plan admitted before this
fix (i.e. today's original EXT-008) must be re-authored and re-admitted
under the corrected convention before a real pilot execution can
succeed; EXT-001 through EXT-007, EXT-009 are unaffected and do not need
to change.

## Consequences

Scientific effect: none -- this only fixes which serialization of the
same runner-admission JSON object is hashed for a purely mechanical
integrity check; it does not change any measured or frozen quantity.

Compatibility effect: EXT-008 (and, transitively, EXT-010, which embeds
EXT-008's plan verbatim in its signed request) must be rebuilt against
this fix before a real pilot execution can succeed.

## Rollback or supersession

Reverting this file restores the prior (broken) behavior, under which no
real pilot execution can ever pass the compiled worker's own admission
check. A future fix that instead changes the compiled worker's
`protocol::json::canonicalize` to append a trailing newline would be an
equally valid alternative resolution of the same inconsistency, but was
not chosen here since it requires a new worker binary and full release
bundle, whereas this fix requires only re-authoring the two affected
external inputs.
