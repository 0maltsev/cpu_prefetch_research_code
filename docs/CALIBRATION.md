# Stage 13 Calibration Framework

## Scope and evidence boundary

`cpu_prefetch_calibration` and `tools/calibration_statistics.py` implement the
accepted D-035 through D-038 procedures. Repository tests use fake clocks and
synthetic records only. They do not produce `mu_cell`, `mu_ref`, a frozen load,
a platform `d2`, a feasibility verdict for the planned experiment, or any
performance claim.

The framework separates three operations:

1. a prepared calibration data plane captures bounded raw observations under
   an explicit prospective plan;
2. typed C++ evaluators validate context equality and calculate exact
   service/ring summaries after each run; and
3. the offline Python layer evaluates the matrix bound, canonicalizes records,
   and publishes them append-only.

Configuration parsing, plan creation, allocation, serialization, hashing,
statistics, filesystem I/O, and freeze evaluation stay outside calibration
timed intervals. The ring trace requires an explicit attempt capacity and
preallocates all four series. A capacity overrun invalidates capture; it never
grows a vector in the interval.

## Service-rate contract

The exact required cell product is five registered packages times H0/H1 times
near/far times the three registered working-set classes: 60 cells. Every cell
binds explicit platform, build, queue implementation, consumer action,
placement, logical capacity, working-set evidence, requested/verified hardware
evidence, software policy, and clock policy. Evidence must match that context
and the prospective fixed duration exactly. The only allowed workload change
is `CALIBRATION` + `SERVICE_RATE_CALIBRATION` + `CONTINUOUS_READY`.

For each valid run:

```text
T_r = consumed_events * ticks_per_second / interval_ticks
```

The implementation cancels common factors before checked multiplication and
retains an exact reduced rational. At least 59 valid results from the immutable
plan are required in every cell; invalid results remain referenced and require
failure evidence. Missing runs do not authorize top-up. `mu_cell` is the exact
minimum, `mu_ref` is the minimum over all 60 cells, and candidate loads are
exactly `1/4`, `1/2`, and `3/4` of `mu_ref`. A valid zero remains eligible and
therefore becomes the minimum.

Every cell result carries one decision per present planned run: run identity,
validity, counts/units, exact throughput when valid, raw and integrity sources,
and failure source when invalid. Calibration/statistical owner IDs plus hashed
authority and stand-budget artifacts are mandatory plan inputs. Thus the
valid-run set and absence of an unauthorized top-up are independently
auditable from the result graph.

## Ring-distance contract

The ring calibration product is near/far times the three working-set contexts,
with separate prospective H0 and H1 plans in each context. Every run must be
ring-off R0, mode `D2_CALIBRATION`, and use no confirmatory outcomes or
software-prefetch treatment. Within a context, H0 and H1 must have identical
platform, build, queue, action, placement, capacity, working-set, software,
clock, and logical-capacity identities; only the verified hardware-state
evidence may differ. Logical capacity must equal the distance geometry. The
ring queue exposes a calibration-only observer immediately before and after
the same acquire load that decides slot availability. It does not change the
normal release/acquire path.

Demand latency is recorded for every producer/consumer acquire observation.
`FULL` and empty counts remain in the trace. Issue intervals use demand-start
timestamps only between successive accepted producer operations or successful
consumer dequeues; non-advancing observations never reset that cadence.

Each valid positive run series uses exact `X_(ceil(p*N))`, with p=999/1000 for
demand and p=1/1000 for issue. At least 59 valid prospectively planned results
are required for each H state. The evaluator takes the maximum demand and
minimum issue across runs, workers, and both states, then applies:

```text
d1_slots  = ceil(cache_line_bytes / slot_bytes)
raw_slots = ceil(conservative_demand / conservative_issue)
raw_lines = ceil(raw_slots / d1_slots)
cap_lines = floor((logical_capacity / 4) / d1_slots)
d2_lines  = min(max(2, raw_lines), cap_lines)
d2_slots  = d2_lines * d1_slots
```

Producer and consumer receive the same resolved `d2_slots`. An incomplete
prospective plan is `NOT_EVALUATED`; a run labelled valid but lacking complete
positive series/integrity evidence is rejected and must instead carry an
explicit invalidity decision and failure artifact. Arithmetic overflow,
`cap_lines<2`, or collapse to `d1` is `INELIGIBLE`. None is repaired with a
default. Distances are context-specific where the evidence differs.

## Matrix strict-zero-loss feasibility

The offline method is
`MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1`. A run is the independent
cluster and retains its offered and `FULL` counts; arbitrary within-run
dependence is allowed. Zero-offered runs fail. The complete family contains
180 cells and all five prospective global candidates, with
`alpha_cj=1/18000`. For each cell/candidate:

```text
Y_r    = full_r / offered_r
w_r    = offered_r / sum offered
p_hat  = sum w_r * Y_r
p_U    = min(1, p_hat + sqrt(ln(18000) * sum(w_r^2) / 2))
E_cj   = planned_confirmatory_runs * scheduled_events_per_run
P_L,j  = max(0, 1 - sum_c E_cj * p_U,cj)
```

Estimator ID, arithmetic profile, confidence, threshold, family sizes,
candidate index, global scale, planned run exposure, namespaces, schedules,
and hashes are mandatory inputs. The accepted confidence and threshold are
both 19/20. The global scale ladder is `[1, 9/10, 4/5, 7/10, 3/5]`; the first
complete passing candidate applies to every load and cell. Evaluated candidates
must form the exact descending prefix with distinct predeclared namespaces;
later candidates are not observed after the first pass, though all five remain
in the simultaneous confidence family. A skipped prefix candidate,
post-success outcome, or cell-specific adjustment fails. Confirmatory, pilot,
or treatment outcomes are rejected as calibration inputs.

The concrete arithmetic profile is
`HOEFFDING-DECIMAL80-GUARD160-UP-v1`, recorded by ADR-0039. All-zero finite
evidence has a positive upper margin. Final matrix feasibility remains
`NOT_EVALUATED` until immutable Stage 14/15 `Rtotal` and schedules supply every
exposure. A separate pure-Python `_pydecimal` precision-240 pass checks the C
Decimal precision-160 enclosure at every direct vector.

## Records, failures, and invalidation

The five schemas in `config/schemas/` cover prospective plans, service results,
ring results, feasibility results, and freezes. Records include method/profile
versions, assumptions, planned and raw source references, validity/blocker
states, per-run summaries, owner/authority/budget evidence, proposed outputs,
unresolved inputs, SHA-256, and supersession. A
partial feasibility record can truthfully retain fewer than 180 cells only as
`NOT_EVALUATED` with explicit blockers; `EVALUATED` requires all 180. Resolved
service/ring children require their outputs and empty blockers. A record ID is
opaque and cannot contain a path separator. Publication uses exclusive
creation and directory sync; an existing identity is never overwritten.

The invalidation fingerprint binds all caller-enumerated material platform,
build, queue, memory-order, action, clock, geometry, hardware, schedule,
estimator, and arithmetic identities. A change makes the earlier freeze
inapplicable and requires a new linked record. Partial or invalid evidence is
retained; no missing artifact, result, retry, or freeze output is fabricated.

## External inputs still required

Before stand calibration, owners must freeze the exact stand/authority,
contexts and verified states, capacities and line/slot facts, duration, full
prospective run IDs/counts, minimum per-run series counts, namespaces/seeds,
storage budget, and schedule family. Before a final feasibility freeze, Stage
14/15 must additionally supply immutable planned blocks, `Rtotal`, every
schedule count, and simultaneous exposure. None has a repository default.

## Verification

With the accepted dependency prefix and `PYTHONPATH`:

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target calibration-check
ctest --preset dev-gcc -L calibration --output-on-failure
```

The suite covers exact rational arithmetic/overflow, all required cells,
58/59 eligibility through invalid-run retention, prospective-plan completion,
authority/budget validation, context drift, no top-up, fake-clock acquire
boundaries, advancement-only
issue series, inverse-ECDF ranks, conservative min/max, cap rounding/collapse,
complete 180-cell exposure, forbidden confirmatory access, global ladder,
Decimal direct/reference vectors, five schemas, canonical hashing,
material-change invalidation, and append-only publication.
