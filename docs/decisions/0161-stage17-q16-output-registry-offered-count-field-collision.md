# ADR-0161: Stage 17 Q16-family output-registry offered_count field collision

- **Status:** `ACCEPTED`
- **Decision ID:** D-161
- **Classification:** implementation correctness, latent output-admission
  defect never previously reachable, action-time reachability gap
- **Owner:** repository/build/runner owner
- **Gate:** before any real `Q16b`, `Q16c`, or `STAGE17-BLINDED-PILOT`
  `execute-action` output can be admitted; a new pilot-candidate release
  and a fresh journal's `S17-EXT-001` through `S17-EXT-006` admission
  are both required downstream of this fix (see Effects)

## Context

The first real, live, full-scale `Q16b` execution to ever reach full
completion (journal `standv2-30`, worker `binary_sha256=
1f4c67af16d51e88e561c6a11d16979a32ab08a1256ed37f9f5e63edcbf10501`,
under ADR-0160's `DURABLE_PILOT_SESSION` fix) ran all 3540 real
hardware runs to completion -- every producer/consumer capture,
reconciliation join, and per-run raw-byte-identity check passed for
every run, confirmed by direct inspection of the real, preserved
per-run output files (`q16b-r00000` through `q16b-r03539`, 35400 files
total, matching 3540 runs x 10 artifacts). Execution then failed at
the very last stage, output admission, with `stage17-operational:
FAIL: run offered count differs from frozen plan`. The real, preserved
failure record (`stage17-q16b-failure-v4.json`) shows
`failure_category: RESULT_ARTIFACT`, `failure_stage:
POST_MARKER_FIXED_ACTION_V4`, `restoration_verified: true` -- the
hardware was already safely restored before this failure was even
raised.

Root-caused by direct code tracing, not assumed. `tools/stage17_output_
registry_v4.py:353` (`_validate_run_families`) checks `document
["offered_count"] != run["offered_count"]`, where `document` is the
real worker's own run-summary output and `run` is the corresponding
entry from the signed request's `action_inputs.runs` (or
`pilot_plan.cells[].runs` for the pilot). Direct inspection of every
one of the 3540 real run-summary files on `standv2-30` (`q16b-r*-run-
summary-v3.json`) shows `offered_count` values clustered around
20,400-22,600 -- varying run to run, consistent with a genuine,
duration-bound hardware measurement -- against every `run["offered_
count"]` in the signed request equal to `1,000,000` (the real,
intended per-run attempt ceiling). Direct inspection of `src/runner/
stage17_fixed_action.cpp:2652-2676` (`run_artifacts`) and `config/
schemas/stage17-run-output-v3.schema.json` confirms the real worker's
output schema deliberately carries *two distinct, both-required*
fields that happen to share a name with two different request-side/
output-side concepts:

- `planned_attempt_capacity` -- echoes the *request's* ceiling
  (`uint_value(*planned_attempt_capacity)`, read from the same input
  key named `offered_count`).
- `offered_count` (output-side) -- the real, measured, duration-bound
  attempted count (`uint_value(capture.report.attempted)`), which is
  the actual scientific measurement Q16b/Q16c/the pilot exist to
  produce, and is *expected* to be materially smaller than the
  request's ceiling whenever `duration_ticks` (not the ceiling) is the
  binding constraint -- exactly the real, intended design for a fixed-
  duration continuous-ready service-rate capture.

`_validate_run_families`'s check compares the *output-side* `offered_
count` (the achieved measurement) against the *request-side* `offered_
count` (the ceiling) -- two different quantities that happen to share
a JSON key name across the request and output schemas. The correct
comparison is `document["planned_attempt_capacity"] != run["offered_
count"]`, which is exactly the field the real worker populates to
echo the request's ceiling back for exactly this kind of frozen-plan
cross-check.

This function is shared, unconditionally, by all three real actions
that use an `offered_count`-style (as opposed to `Q16a`'s `sample_
count`-style) schema: `Q16b`, `Q16c`, and `STAGE17-BLINDED-PILOT` (all
three route through `_run_groups`/`_validate_run_families` per the
`action_id` branch at `stage17_output_registry_v4.py:289-294`). None of
the three had ever reached this code path with a real, complete run
set before this session: every real `Q16b` attempt prior to ADR-0160
failed earlier, at the `WORKER_TIMEOUT` bound, before any output
admission was attempted; `Q16c` cannot run at all without a real,
successful `Q16b` completion (`_validate_q16_matrix` requires a real
`q16b_result_sha256`); and `STAGE17-BLINDED-PILOT` has not yet been
attempted in this engagement. This is a second, previously-latent,
completely independent defect that ADR-0160's fix exposed for the
first time by finally letting a real `Q16b` run reach its own output-
admission stage.

## Options considered

1. Change the *request-side* ticket-building convention so future
   requests set `offered_count` to a value the real hardware is
   expected to hit exactly. Rejected: run-to-run achieved counts vary
   naturally (20,404-22,589 observed across just the first 20 real
   runs), so no single a-priori constant could satisfy an *exact*
   match against the real, duration-bound measurement; this would also
   misrepresent the real scientific design, where `offered_count`
   (output) is meant to be an *observed outcome*, not a pre-declared
   target.
2. Remove the `_validate_run_families` offered-count cross-check
   entirely. Rejected: the check itself is sound in intent (bind the
   real output back to the frozen, signed request) -- only the field
   it reads is wrong. Removing it would silently drop a real integrity
   binding rather than fix the one-line defect.
3. Fix the comparison to read `document["planned_attempt_capacity"]`
   -- the field the real worker already populates for exactly this
   purpose -- instead of `document["offered_count"]`. Selected.

## Decision

`tools/stage17_output_registry_v4.py`'s `_validate_run_families` is
defined once; every real caller (`validate_worker_result`, defined in
the same module) reaches it via a bare name resolved against `v4.py`'s
own module globals, the same free-variable-resolution rule already
established repeatedly this engagement (ADR-0126/ADR-0131). It cannot
be edited in place (already policy-pinned by the sealed `standv2-30`
bundle). `tools/stage17_output_registry_v5.py` is a new, additive
successor with a faithful copy of `_validate_run_families`, changed
only to compare `document["planned_attempt_capacity"] != run["offered_
count"]` instead of `document["offered_count"] != run["offered_
count"]`. It monkey-patches `stage17_output_registry_v4._validate_run_
families` to the corrected function as an import-time side effect, so
`validate_worker_result`'s own bare call (real caller:
`stage17_fixed_action_executor_v5.py`/`v6.py`'s `output_registry.
validate_worker_result(...)`, itself a fresh attribute lookup on the
real `v4` module object every call) exercises the fix with no further
rebinding needed -- the identical pattern ADR-0160's `stage17_fixed_
action_executor_v6.py` already used for `execute_fixed_action`.

`tools/stage17_fixed_action_executor_v7.py` is a new, additive
successor of `v6.py` whose only change is importing `stage17_output_
registry_v5` (for its monkey-patch side effect) alongside the existing
`stage17_fixed_action_executor_v6` import chain; `tools/stage17_phase_
controller_v19.py` is a new, additive successor of `v18.py` whose only
change is importing `stage17_fixed_action_executor_v7` instead of `v6`
(the same side-effect-import role `v18.py` already gave `v6.py`).
`tools/stage17_operational_cli_v11.py`'s `controller` import is bumped
from `v18` to `v19`.

No change is made to the real scientific measurement, the real worker
binary's behavior, `ADR-0160`'s own durable-session deadline fix, or
any other action's output-admission logic. `Q16a` is unaffected (it
never carries an `offered_count` field at all; it uses `sample_count`
instead, per its own, separate schema branch).

## Effects

`standv2-30`'s just-completed `Q16b` attempt cannot be salvaged by
this fix in place: the real, live 3540-run hardware measurement itself
was genuinely clean (confirmed by direct inspection of every run's
producer/consumer/join/reconciliation artifacts), but its signed
authorization is `retry_allowed: false` and its own attempt marker was
already written by the real `RESULT_ARTIFACT` failure -- non-
retryable regardless of this fix. A new `tools/stage17_operational_
cli_v11.py` and a new `tools/stage17_phase_controller_v19.py` both
change the runtime closure the pilot-candidate bundle pins, so a new
bundle must be cut and a fresh journal must redo `S17-EXT-001` through
`S17-EXT-006` admission (including a fresh, real, live `Q15-R`/`Q15-W`
pairing and a fresh, real, live `Q16a` execution) against the new
`binary_sha256` before `Q16b` `execute-action` can be retried a third
time. No scientific design, hardware-safety mechanism, queue
semantics, timing unit, or admission *semantics* changes -- only which
output field the frozen-plan cross-check reads.

## Verification and supersession

Acceptance requires: (1) the real, live `standv2-30` failure record
above (`RESULT_ARTIFACT`, `restoration_verified: true`, all 3540 real
runs' raw producer/consumer/join artifacts independently confirmed
clean by direct inspection before the output-admission failure was
reached), confirming this is a real, measured defect and not a hand-
waved concern; (2) direct code inspection confirming `planned_attempt_
capacity` is the only field the real worker populates to echo the
request's `offered_count` ceiling, and that no other compiled or
Python-side check independently duplicates or would still misapply
the wrong field after this change; (3) confirmation, at the time a new
pilot-candidate bundle is cut, that the rebuilt worker's regression
matrix and `Q15-R`/`Q15-W`/`Q16a`'s own real, live executions still
pass unchanged, none of which is expected to exercise this fix (`Q16a`
never reaches `_validate_run_families`). Any later request-shape or
output-schema change to `Q16b`, `Q16c`, or `STAGE17-BLINDED-PILOT`
needs another prospective review under the same standard.
