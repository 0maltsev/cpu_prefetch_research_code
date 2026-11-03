# ADR-0230: Exact formal calibration from bound capture-validation reports

- Status: ACCEPTED — engineering composition of accepted estimators
- Date: 2026-11-03
- Scope: Offline Q16a/Q16b family evaluation; no Q16c probability-method change
- Scientific authority: D035/D037, accepted D211/D212
- Execution authority: None

## Evidence boundary

`tools/stage17_formal_calibration_v1.py` exposes
`evaluate(action, plan, run_records, ring_geometry=None)` and
`validate_calibration_record(document)`. The full prospective plan passes the
existing D228 family contract; Q16a still delegates to unchanged D221. This
module does not open raw streams, repeat per-capture reconciliation, execute
hardware operations, choose a new plan, or grant authority.

Each supplied run record has exactly `capture_ordinal`, `measurement_run_id`,
`validity`, `report_binding`, and `report_utf8_bytes`. A report binding contains
`artifact_id`, `size_bytes`, and `sha256`. The evaluator verifies those original
UTF-8 bytes before strict duplicate-key JSON decoding; a separately supplied
decoded object cannot substitute for them. Unplanned/duplicate ordinals or run
IDs are rejected. Input order does not change prospective membership.

VALID reports must use the actual D220 Q16a or D229 Q16b schema and method,
match the planned capture and both phase run identities, assert the required
completed independent raw and execution-evidence checks, and grant no authority.
Clock windows, explicit duration, counts, exact quantile ranks and relevant
cross-field equations are checked before inference. Original raw hashes remain
part of the capture report; this layer never re-reads those raw files.

The caller must authenticate the original report-producing analysis, its source
code, its input-plan/control/final-result bindings and its evidence provenance.
A hash proves byte identity, not that a trustworthy validator produced those
bytes. This module's required report flags are checked facts asserted by that
authenticated producer; arbitrary flags do not supply provenance or authority.

## Invalid and missing runs

INVALID requires an explicitly bound
`cpu-prefetch-stage17-formal-capture-validation-failure/1` report. Its exact
fields are schema/action/method identity, capture ordinal, warmup and measurement
run IDs, canonical plan SHA256, source revision, `error {type,message}`,
`input_bindings {native_input,control,final,raw_artifacts}`, and false execution
and Phase 18 authority fields. Every referenced artifact uses the binding shape
above; all eight Q16a raw inputs or all five Q16b primary/node-order inputs must
be bound. Missing failure identity, error or raw-input binding is rejected.
An arbitrary invalidity boolean cannot exclude an unfavorable run.

Every planned run appears in the output. An absent report receives an explicit
MISSING decision with no invented report binding, summary or failure. Any
MISSING receipt makes its cell/state and the whole family UNRESOLVED,
independently of the number of remaining valid results. Thus 60 planned runs
with 59 valid and one missing report cannot resolve. A complete fixed 60-run
plan with one documented invalid run and 59 valid results can resolve under
D035/D037. Invalid runs remain visible and estimator-ineligible; neither case
permits a top-up, replacement or extension.

## Q16a arithmetic

Use `RING-D2-RUNTAIL-LTL95C95-WINDOW-v2`, retaining D212's measurement demand
window and D037's exact inverse-ECDF ranks. D220 already supplies the independently
decoded per-run demand p99.9 and advancing-issue p0.1 values. This layer verifies
the explicit minimum and the exact `ceil(p*N)` ranks, then recomputes run-level
maximum demand and minimum issue summaries for each owner under each hardware
state. At least 59 valid runs and complete prospective receipt coverage are
required in each state/context. Merge both owners and both states conservatively
into `ell_star` and `c_star` for each of the six placement/working-set contexts.
The tolerance interpretation remains marginal 95%/95%, not a new simultaneous
confidence claim.

Six explicit native geometry records contain `context_ordinal`, `capacity`,
`cache_line_bytes`, `slot_storage_bytes`, and `source_binding`. The caller
authenticates the native storage evidence. This module checks every matching
planned H0/H1 geometry and derives the individual slot size by exact division
of native total slot storage by capacity. It does not assume pointer or atomic
width, invent a slot size, or interpret a success flag as geometry proof.

Apply the accepted checked integer formula: ceiling cache-line/slot ratio,
ceiling demand/issue ratio, whole-line rounding, two-line minimum, and the
one-quarter-capacity limit. Both producer and consumer distances are identical.
A cap below two lines or collapse to R1 yields UNRESOLVED without a usable R2
distance. Geometry, source bindings and all intermediate quantities remain in
the record. No successful context authorizes use of a partial unresolved family.

## Q16b arithmetic and separate zero-loss reporting

Use `SERVICE-RATE-NP-LTL95C95-MIN-v1`. The numerator is D229's independent D211
count of consumer action completions in the fixed half-open measurement
interval, not its drain-inclusive count. Check exact interval duration/clock
units and the inside/outside partition. Retain the full consumed count separately.

Compute reduced exact rational events per second using integer/Fraction
arithmetic, with cancellation before the unsigned-64-bit result bound. Each of
the 60 complete cells needs at least 59 valid planned runs. Its `mu_cell` is the
minimum valid run rate; `mu_ref` is the global minimum only when every cell
resolves. Candidate rates remain the accepted exact 1/4, 1/2 and 3/4 multiples.
Unrepresentable exact results reject the evaluation; they are not rounded,
dropped or converted into favorable invalid-run exclusions.

Valid zero throughput is retained and may make `mu_ref` and every candidate
rate zero. FULL remains retained valid data, separate from estimator validity.
The record reports measurement and warmup zero-loss gates independently as
PASS, FAIL, or UNRESOLVED; invalid or missing runs cannot establish a zero-loss
pass. A known FULL can establish failure even when other receipts are unresolved.

## Output and semantic checking

The output identity is
`cpu-prefetch-stage17-formal-calibration-validation/1`. It contains `action_id`,
`method_id`, `stand_id`, `source_revision`, registry-canonical `plan_sha256`
(including its trailing LF), `status` VALIDATED/UNRESOLVED, `prospective`,
`ring_geometry` (null for Q16b), `run_sources`, `derived_result`, and false
`execution_authority` and `phase18_authority`.

`run_sources` retains every prospective ordinal/run identity, its bound source
report, VALID/INVALID/MISSING decision, normalized exact estimator inputs, and
explicit failure where present. `derived_result` contains the six Q16a context
summaries/distances or the 60 package-major Q16b cell summaries, global minimum
and candidate rates, plus separate zero-loss gates. No new record ID is needed:
the caller can bind the immutable artifact ID/SHA256 as the R2 evidence ID.

`validate_calibration_record` recomputes coverage, counts, extrema, rational
rates, distances, status and zero-loss gates from the retained normalized
inputs. It rejects altered derived claims, including numeric/boolean type
substitution. It does **not** prove that those normalized inputs or an embedded
failure came from the original report hash: the original UTF-8 report bytes
are not duplicated in the result. Nor does it authenticate the original plan
or native geometry from a hash alone. The caller must authenticate the immutable
record and its producer/provenance before accepting it as prerequisite evidence.
Passing this semantic checker alone is not a stand qualification or an execution
approval.

## Verification

Tests consume actual small D220 and D229 software-fixture outputs for shape
compatibility, then use explicit synthetic reports for complete 708/3540-member
family arithmetic. Known vectors are checked against
`tests/calibration_model_test.cpp`: exact rate 15/1, the 60-cell minimum 80/1 and
20/40/60 candidate rates, and ring `ell=100,c=4,C=1024,line=64,slot=8` yielding
four lines and 32 common slots. Scaled picosecond tails preserve that ratio in
the D212 family fixture. No new native build or empirical capture is claimed.

Required negatives include missing and documented invalid attrition, no top-ups,
original-byte/hash/duplicate-key errors, false validity flags, incomplete failure
evidence, source/capture/window/minimum/rank mismatch, explicit geometry mismatch,
quarter-cap collapse, altered derived records, exact zero/FULL handling and
unsigned arithmetic boundaries/overflow. The 60-planned/59-valid/one-MISSING
case is explicitly UNRESOLVED, distinct from a documented invalid receipt.
