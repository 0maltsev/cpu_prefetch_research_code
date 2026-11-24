# ADR-0160: Stage 17 Q16b durable-session deadline

- **Status:** `ACCEPTED`
- **Decision ID:** D-160
- **Classification:** implementation correctness, latent capacity limit
  in already-accepted production code, action-time reachability gap
- **Owner:** repository/build/runner owner
- **Gate:** before any real `Q16b` `execute-action` can complete its
  full 3540-run matrix; a new pilot-candidate release and a fresh
  journal's `S17-EXT-001` through `S17-EXT-006` admission are both
  required downstream of this fix (see Effects)

## Context

The first real, live, full-scale Q16b execution attempt against a
worker binary containing the fixed `MeasurementExecutionReport`
initialization (journal `standv2-30`, worker `binary_sha256=
fa486e5558c790856032dccae5c11b8d6a27082310fc8969b7cf105db3531abc`)
succeeded for 458 of 3540 real runs -- real data, no corruption, clean
per-run envelopes -- before failing: `stage17-operational: FAIL: fixed
worker exceeded the common wall deadline`. The real, preserved failure
record (`stage17-q16b-failure-v4.json`) shows `failure_category:
WORKER_TIMEOUT`, `restoration_verified: true`, and a real elapsed time
of 255 seconds between the signed authorization's `issued_at_utc`
(`2026-09-11T08:40:06Z`) and `completed_at_utc`
(`2026-09-11T08:44:21.592975Z`).

Root-caused by direct code tracing, not assumed. `tools/stage17_fixed_
action_executor_v2.py` defines `GLOBAL_WALL_SECONDS = 180` (line 32)
and computes `global_deadline_ns = started_ns + GLOBAL_WALL_SECONDS *
1_000_000_000` (line 414) -- a single monotonic deadline covering
marker creation, transport, output retention, receipts, and completion
for the *entire* worker subprocess invocation, per ADR-0108's own
unification of what were previously six independent per-command
limits. This bound is applied uniformly to every fixed action
(`Q15-R`, `Q15-W`, `Q16a`, `Q16b`, `Q16c`) under `deadline_policy.mode
= "ONE_SHOT_ACTION"`, and is completely independent of the signed
authorization's own `issued_at_utc`/`expires_at_utc` window (that
window only bounds how long the authorization remains valid for being
*submitted*, not how long the worker subprocess may run once started).

`Q16a`'s real, live execution (708 runs, one shared runner_admission
per run) already completed within this bound. `Q16b`'s real design is
structurally larger: `_validate_q16_matrix` (`tools/stage17_phase_
controller_v4.py:134-189`) requires the complete, cryptographically-
bound 3540-run matrix (60 cells x 59 repetitions) present in a single
request -- confirmed directly by re-reading this function live, after
first mistakenly assuming a smaller per-batch submission might be
possible. At the real measured rate from the 458 completed runs (255s
/ 458 runs, dominated by real per-run producer/consumer/joined raw
output of several MB each, not the 10ms `duration_ticks` measurement
window itself), a full 3540-run completion needs approximately 1972
seconds (~33 minutes) -- far beyond 180 seconds regardless of output
tuning, since the fixed per-run overhead (thread/queue setup, fsync)
dominates, not data volume.

ADR-0108's own classification states "Scientific effect: None" for
the 180-second unification, and its Supersession rule is explicit:
*"Any change to authority time, OpenSSH argv, action programs, record
schemas, runtime bindings, directory-FD storage, durability ordering,
retry policy, or global deadline requires a new ADR, policy, plan,
schemas, and implementation versions."* This ADR is that required new
decision for `Q16b` specifically; it does not alter `GLOBAL_WALL_
SECONDS` itself, nor any other action's deadline behavior.

The codebase already has a sanctioned mechanism for actions that need
longer than 180 seconds: `deadline_policy.mode = "DURABLE_PILOT_
SESSION"`, used today only by `STAGE17-BLINDED-PILOT`, which supplies
an explicit `session_max_wall_seconds` strictly greater than 180 and
derived from that action's own `pilot_plan` resolution
(`repetitions_per_cell`, `recovery.duration_ticks`). `Q16b` carries no
comparable predecessor resolution to derive a plan-based maximum from
(its own `required_resolution_ids` are only `S17-EXT-001` through
`S17-EXT-006`), so this decision uses a fixed, real, measured-with-
margin constant instead of a plan-derived formula.

## Options considered

1. Raise `GLOBAL_WALL_SECONDS` itself. Rejected: it is a shared bound
   applied uniformly to every fixed action, including the already-
   accepted, already-proven-sufficient `Q15-R`/`Q15-W`/`Q16a` designs;
   widening it globally would silently change every other action's own
   safety margin as a side effect of a `Q16b`-specific need.
2. Split `Q16b` into multiple smaller `execute-action` submissions,
   each within 180 seconds. Rejected: `_validate_q16_matrix` requires
   the complete, cryptographically-bound matrix in one request
   (`set(counts) != set(expected)` and a `plan_sha256` binding over the
   full `runs` list); accepting partial submissions would require
   redesigning this frozen, shared semantic check (also used by
   `Q16c`), a materially larger and riskier change than adopting the
   already-existing durable-session mode.
3. Reduce `Q16b`'s real per-run output volume (`capacity`, `sample_
   count`, `offered_count`) to fit within 180 seconds. Rejected: the
   measured 458-run rate (~0.557s/run) is dominated by fixed per-run
   overhead (thread/queue setup, fsync), not by the 10ms `duration_
   ticks` measurement window or output size; tuning these parameters
   would not bring the full matrix under 180 seconds, and would also
   depart from the real, intended production configuration this
   confirmation run is meant to validate.
4. Grant `Q16b` `DURABLE_PILOT_SESSION` mode with a fixed, real,
   measured-with-margin `session_max_wall_seconds`, following the
   existing, already-accepted precedent this codebase uses for
   `STAGE17-BLINDED-PILOT`. Selected.

## Decision

`Q16b`'s `deadline_policy.mode` becomes `DURABLE_PILOT_SESSION` with
`session_max_wall_seconds = 3600` (one hour) -- approximately 80%
margin over the measured ~1972-second realistic completion time, still
bounding the maximum real-hardware exposure for this one-shot,
`retry_allowed: false` action, matching the spirit of ADR-0108's own
fail-closed, no-implicit-extension design. `per_run_max_wall_seconds`
remains 180, `implicit_extension` remains `false`, and `partial_
session_completes` remains `false`, unchanged from every other action.

`prepare_action` (defined once, in the policy-pinned `stage17_phase_
controller_v4.py`; every successor since `v5` only ever re-exports it,
so its own free variables resolve against `v4.py`'s own module globals
regardless of which successor a caller imports, per ADR-0126/
ADR-0131) cannot be edited in place. `tools/stage17_phase_controller_
v18.py` is a new, additive successor with a faithful copy of `prepare_
action`, changed only to (a) widen `expected_deadline_mode` to
recognize `Q16b` alongside `STAGE17-BLINDED-PILOT`, and (b) add a
`Q16b`-specific branch validating `session_max_wall_seconds` against a
fixed `Q16B_SESSION_MAX_WALL_SECONDS = 3600` constant instead of a
pilot-plan-derived formula. Because `execute_once` (defined once, in
`v15.py`) makes its own bare call to `prepare_action` that resolves
against `v15.py`'s own module globals -- the identical free-variable
trap `v15.py`'s own docstring already documents for `executor` --
`v18.py` also monkey-patches `stage17_phase_controller_v15.prepare_
action` to the new function, so `execute-action`'s real call path (not
only `verify-signature`'s direct `controller.prepare_action` call)
exercises the new logic. `tools/stage17_operational_cli_v11.py`'s own
`author_authorization` gains a matching `Q16b` branch building the
same `session_max_wall_seconds = 3600` `deadline_policy`, and its
`controller` import is bumped to load `v18`.

`prepare_action`'s own re-validation is not the only enforcement point:
`execute_fixed_action` (defined once, in `stage17_fixed_action_executor_
v5.py`) has its own, completely separate, hardcoded `if action ==
"STAGE17-BLINDED-PILOT": ... else: require ONE_SHOT_ACTION ...` branch
-- discovered live only after `verify-signature` (which exercises
`prepare_action`) passed cleanly but the real, live `execute-action`
attempt still failed (`ACTION_DEADLINE: one-shot action deadline
contract drifted`), confirming this is a real, distinct gate rather
than a hand-waved concern. `tools/stage17_fixed_action_executor_v6.py`
is a new, additive successor with a faithful copy of `execute_fixed_
action`, changed only to add a `Q16b`-specific branch matching the
same fixed `Q16B_SESSION_MAX_WALL_SECONDS = 3600` bound. Unlike
`prepare_action`, `execute_once` reaches this function via `executor.
execute_fixed_action(...)` -- a fresh attribute lookup on the real
`v5` module object on every call, not a bare name resolved against
`v15.py`'s own globals -- so patching `v5`'s own attribute directly
(as an import-time side effect of `v18.py` loading `v6.py`) is
sufficient, with no further rebinding needed.

No change is made to `Q16c`, `Q15-R`, `Q15-W`, `Q16a`, or `STAGE17-
BLINDED-PILOT`'s own deadline behavior. If `Q16c`'s own real execution
is later found to need more than 180 seconds, that is a separate,
future decision under the same standard -- not assumed here.

A third, independent enforcement point exists: `_phase_family`
(defined once, in `tools/stage17_operational_semantics_v4.py`)
cross-validates every fixed action's authorization/request/attempt/
result/completion lineage whenever it is later referenced by another
admission, and enforces its own hard `<=1800`-second authorization-
lifetime bound uniformly, with no `Q16b`-specific exception --
discovered live only while admitting `S17-EXT-007` (the calibration
freeze), the first and only code path that ever calls `_phase_family`
on `Q16b`'s own real authorization (`S17-EXT-004`/`S17-EXT-005`
exercise it only for `Q15-R`/`Q15-W`, both real 30-minute windows,
which never tripped this). `tools/stage17_operational_semantics_v9.py`
is a new, additive successor with a faithful copy of `_phase_family`,
changed only to accept the same fixed `Q16B_SESSION_MAX_WALL_SECONDS
= 3600` bound for `Q16b` specifically. `_phase_family`'s own three
real callers are all defined in `v4.py` itself and reach it via a
bare name resolved against `v4.py`'s own module globals, so patching
`v4`'s own attribute (as `v9.py`'s own import-time side effect) is
sufficient, with no further rebinding needed.

Unlike the two enforcement points above, `_phase_family` runs only at
admission time, over already-completed, already-signed real evidence
-- not inside the compiled worker's own real-time execution path, and
not exercised by `standv2-30`'s already-sealed admission-root until
`S17-EXT-007` was attempted. This fix is deployed to that already-
sealed admission-root via a local wrapper script (mirroring the `q15_
session_journal_runtime_patch_standv2-30.py` precedent already used
this engagement for the separate Q15-session entrypoint) rather than
a new bundle/journal: no real hardware evidence changes, only which
authorization-lifetime bound this one Python-side admission-time
check accepts for `Q16b` specifically. A future pilot-candidate
bundle rebuild should still fold `v9.py` into the real import chain
(analogous to `v18.py`/`v6.py`) so a fresh journal does not need the
wrapper.

## Effects

`standv2-30`'s existing chain cannot be salvaged by this fix in place:
a new `tools/stage17_operational_cli_v11.py` and a new `tools/stage17_
phase_controller_v18.py` both change the runtime closure the pilot-
candidate bundle pins, so a new bundle must be cut and a fresh journal
must redo `S17-EXT-001` through `S17-EXT-006` admission (including a
fresh, real, live `Q15-R`/`Q15-W` pairing and a fresh, real, live
`Q16a` execution) against the new `binary_sha256` before `Q16b`
`execute-action` can be retried. `Q16b`'s already-signed `standv2-30`
authorization is separately non-retryable regardless (`retry_allowed:
false`, and its own attempt marker was already written by the real,
live `WORKER_TIMEOUT` failure). No scientific design, hardware-safety
mechanism, queue semantics, timing unit, or admission *semantics*
changes -- only how long `Q16b`'s own worker subprocess is permitted
to run before the executor's supervisor intervenes.

## Verification and supersession

Acceptance requires: (1) the real, live `standv2-30` failure record
above (`WORKER_TIMEOUT`, `restoration_verified: true`, 458/3540 real
runs completed with no corruption), confirming this is a real,
measured capacity gap and not a hand-waved concern; (2) direct code
inspection confirming `GLOBAL_WALL_SECONDS`/`session_max_wall_seconds`
is `Q16b`'s only wall-clock gate affected by this change, and that no
other compiled or Python-side bound independently duplicates or would
still block a full 3540-run completion after this change; (3)
confirmation, at the time a new pilot-candidate bundle is cut, that
the rebuilt worker's regression matrix and `Q15-R`/`Q15-W`/`Q16a`'s own
real, live executions still pass unchanged, none of which is expected
to exercise the new `Q16b`-only headroom. Any later request-shape or
timing change to `Q16b` itself, or any future action found to need
`DURABLE_PILOT_SESSION` mode, needs another prospective review under
the same standard.
