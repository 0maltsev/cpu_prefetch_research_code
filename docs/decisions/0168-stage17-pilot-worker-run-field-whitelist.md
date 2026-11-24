# ADR-0168: Stage 17 compiled worker pilot run-field whitelist fix

- **Status:** `ACCEPTED`
- **Decision ID:** D-168
- **Classification:** implementation correctness, compiled-binary
  defensive-bound fix; requires a new pilot-candidate release and a
  fresh journal
- **Owner:** repository/build/runner owner
- **Gate:** before any real `STAGE17-BLINDED-PILOT` `execute-action`
  can succeed; a new pilot-candidate bundle and a fresh journal's
  `S17-EXT-001` through `S17-EXT-010` admission are both required
  downstream of this fix

## Context

The first real `execute-action` attempt for `STAGE17-BLINDED-PILOT` on
standv2-31 that reached actual per-run execution (authorization
`XEON-CPU-FETCH-V2-STAGE17-PILOT-AUTH-STANDV2-31-3`, after ADR-0166's
fix cleared the earlier request-size failure and a canonicalization
fix cleared an earlier plan-hash failure) failed in under 4 seconds,
on the very first run attempted (`XEON-CPU-FETCH-V2-EXT008-C049-R000`),
before any real measurement ran (`restoration_verified: true`, all
three MSR readbacks all-zero, `quarantine_operation.performed: false`),
with `stage17-operational: FAIL: fixed worker returned 1` and real
worker stderr `"runner: FAIL: pilot session failed closed:
S17-RUN-INPUT: fixed run geometry is invalid"`.

Root-caused by direct code reading, not assumed:
`src/runner/stage17_fixed_action.cpp`'s `package_capture` validates
each individual pilot run's `action_inputs` with `exact_fields()`
against a hardcoded `pilot_fields` whitelist of 31 field names
(including `plan_sha256`, added by the caller). But the real, current,
versioned plan schema (`config/schemas/stage17-pilot-plan-v4.schema.json`,
`additionalProperties: false`) requires exactly 45 fields per run
object, and `stage17_pilot_plan_v4.py`'s own `validate()` function
reads 15 of those fields (`consumer_cpu`, `execution_ordinal`,
`nominal_rate`, `producer_cpu`, `recovery_boundary_id`,
`schedule_algorithm`, `schedule_algorithm_version`,
`schedule_namespace_id`, `schedule_parent_namespace_id`,
`temporal_block_ordinal`, `warmup_duration_ticks`,
`warmup_freeze_ref`, `warmup_regime`,
`warmup_schedule_namespace_id`, `warmup_schedule_parent_namespace_id`)
for its own topology/schedule provenance checks -- fields the compiled
worker's whitelist had never been widened to include. This is a real,
previously-latent mismatch between the schema-validated plan format
and the compiled worker's ingestion code, unreachable by any earlier
admission-time check (the Python-side plan validator checks the plan
is internally consistent; it does not simulate the C++ worker's own
`exact_fields` gate). It has been live, unexercised, since the pilot
path was first written (`git log -L` on the `pilot_fields` array shows
it unchanged since "Close Stage 17 production pilot and handoff
boundary"); this is simply the first time a real per-run pilot
execution has ever reached this code path in the engagement's history.
Confirmed none of the 15 missing fields are read anywhere in
`package_capture`'s own execution logic (they are pure schema-required
provenance/audit fields consumed only by the Python-side validator),
so widening the whitelist is a behavior-preserving fix, not a new
capability.

## Decision

Add the 15 missing field names to the `pilot_fields` array in
`package_capture` (`src/runner/stage17_fixed_action.cpp`), so it
matches `config/schemas/stage17-pilot-plan-v4.schema.json`'s real,
current 45-field run-object schema exactly (46 fields including the
caller-added `plan_sha256`). No other logic in `package_capture`
changes.

## Effects

- Changes a file already hash-pinned by the real, already-admitted
  `S17-EXT-006` resolution (`STAGE17_FIXED_ACTION_WORKER` release
  artifact) and by the operational evidence admission policy's own
  `runtime_closure` binding. Per this engagement's established
  pattern for compiled-file changes (ADR-0159 through ADR-0161,
  ADR-0166), this requires: a real rebuild of the worker binary
  (`release-gcc` CMake preset, GCC 16.1.1, matching ADR-0151's
  documented real build facts), a new pilot-candidate bundle with a
  new worker `binary_sha256`, and a fresh journal admitting
  `S17-EXT-001` through `S17-EXT-010` again from scratch against that
  new build -- including real hardware re-execution of Q15-R, Q15-W,
  Q16a, Q16b (3540 real runs), and Q16c, followed by rebuilding the
  `S17-EXT-007` calibration freeze (a fresh freeze decision is needed;
  the prior `mu_ref=829,100 Hz` freeze was reasoned about the prior
  real Q16 data and cannot simply be carried over), `S17-EXT-008`
  pilot plan, `S17-EXT-009` custody/storage evidence, and a
  freshly-signed `S17-EXT-010` authorization.
- The operational evidence admission policy is re-pinned
  `v46 -> v47` (`author_stage17_policy_v47.py`/
  `stage17_semantic_verifier_v47.py`), following the exact same
  additive pattern ADR-0159/v45 and ADR-0166/v46 established: no
  admission logic changes, only the file's re-pinned hash and a
  matching schema/verifier version bump.
