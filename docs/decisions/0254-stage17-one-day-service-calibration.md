# D254: One-day service calibration with complete context coverage

- Status: ACCEPTED by the owner; implementation and time-budget verification in progress
- Date: 2026-11-15
- Amendment: AMEND-2.0.0-pre.3-Q16B-DESCRIPTIVE-MIN2-DAYCAP-v1
- Scope: future reduced Q16b only; all prior source, plans and raw evidence remain unchanged

The owner instructed: "make less measurement, leave only main ones, this test
should be maximum 1 day". Asked which coverage to retain, with both options
explicitly replacing the original59-repetition statistical guarantee, the owner
selected "Keep all60 research settings:120 captures" with two repetitions per
setting. This is the prospective scientific decision; do not ask again for the
same count, coverage or disclosed loss of the old guarantee.

## Scientific boundary

Keep all five packages R0/R1/R2/L0/L1, both H0/H1 hardware states, both NEAR/FAR
placements and all three working-set classes. Exactly two independent captures
per cell give120 captures. Keep one-second measurement, five-second warmup,
D211 half-open consumer-completion counting, original byte-level observations,
independent producer/consumer reconciliation and every valid low/zero/FULL
outcome. No top-ups, selected repetitions, favorable retries or silent reuse of
the interrupted earlier attempts. Completed Q16a is retained, not recollected.

The new family method is SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1. Define exact
run throughput as before and take the observed minimum of the two valid runs in
each complete cell, then the minimum across all60 cells. These are descriptive
observed minima; they carry no95%-content/95%-confidence tolerance claim. Missing
or invalid required data leaves the result incomplete. A genuine zero remains
zero and may prevent downstream load selection. Do not represent this result as
SERVICE-RATE-NP-LTL95C95-MIN-v1 or silently alter the original method's59-run gate.

Use a separate service-family schema, cpu-prefetch-stage17-formal-service-plan/3,
and a separately identified descriptive report. Individual capture schemas and
their legacy method identifiers remain the unchanged collector-format identity;
their inferential_validity_established flag is false. Explicitly distinguish
that collector identity from the new family analysis method. Native measured
queue operations, clocks, observation rows and raw capture validation remain
unchanged. Cold family admission must explicitly recognize the new family;
ordinary /1 and /2 plans retain their existing requirements.

Immutable protocol/2.0.0-pre.3 remains readable unchanged under this versioned
amendment. The lowered calibration evidence strength must remain disclosed in
downstream freezes and research reporting. This changes neither the final
primary hypothesis families nor their independently required precision freezes.

## Time and operational boundary

The complete supervised operational study must finish within24hours, including
collection, lossless archive custody, independent validation, reporting and
cleanup/restoration. Prepare source, correctness tests, exact layouts and a
prospective budget before launch. Include any required fresh qualification in
the operational budget. Measure validation on retained data first; do not choose
analysis concurrency or throughput from invented hardware values.

Use finite per-capture setup/publication/drain/cleanup and archive limits, finite
analysis-worker memory/scratch/time limits and one absolute monotonic deadline.
Reserve cleanup time inside the24-hour cap. Stop incomplete before crossing any
time/storage/resource limit; retain evidence, reap owned processes and restore
hardware. The deadline is a maximum, not a promise that a failed run will finish.
No automatic retries, extensions or restart on failure are authorized.

Present the revised whole-study estimate before any new experimental launch.
Qualify an actual clean release if native admission bytes change. Reuse previous
scientific data only through its authenticated source/compatibility evidence;
never relabel an old qualification as belonging to a new executable.
