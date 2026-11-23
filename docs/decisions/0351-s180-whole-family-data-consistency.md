# D351: complete S180 family data-consistency validation

Accepted engineering implementation of D310/D346 and the existing native and
custody contracts. No setting, count, duration, seed, source, estimator, storage
policy, measurement code or operational limit changes. This component grants
no execution, qualification, retry or Stage18 authority.

`stage17_s180_family_validation_v1.validate_family` checks all180 records in
the exact approved order against the concrete original plan and native result.
Sizing packets, missing/reordered/duplicate records and changed blueprints fail.
The original monotonic operational window remains exactly24h; no reset is
introduced. Raw observations use their separate CLOCK_MONOTONIC_RAW domain;
their phase origins and complete drain checkpoints must remain ordered, with
no comparison to the operational CLOCK_MONOTONIC domain.

Require the complete1980 native artifact references in publication order,
all attempts, checkpoints, eight originals per capture and custody receipts.
Reconcile original plan/session/run/source identities, independent stream
counts/extents, checkpoint hashes, registry relationships, parent receipts and
broker cleanup records. Both paired sources remain identical across packages
and hardware states. All six shared contexts retain the same mappings, arena
identity, node publication and successful later cleanup through all treatments.
The12 persistent regions cannot overlap each other or any capture's private
regions, stack guards or monitor mapping.

Match both native whole-plot restorations, preserving full MSR values and the
actual cumulative apply/restore histories. The control object retains those
histories across whole plots; H0 adds no writes, and H1 restores in reverse CPU
order. Require independent successful full-value prestate observations. Do not
infer an independently measured recovery duration from these records: native
recovery and event observations use different clocks.

Verify publication/report/audit/envelope relationships against the normative
immutable raw-observation schema. Joined references, source relationships,
format/units/byte counts, independently derived hashes and original artifact
identities must agree. Validate D346 numerical schemas and defining fixed-N
variance, exact rational IPS/effective-count and threshold equations. A reported
horizon requires all ten observed lags. The family block candidate requires
every approved run's horizon; retain undefined, low-count and FULL outcomes
without replacement, pooling, repeated-block covariance or inferential freeze.

This is a bounded pure metadata consistency layer. Its qualified caller must
authenticate actual input bytes, accepted-generator provenance, real analysis
process completion, current original archive custody and live restoration.
This component explicitly leaves each of those gates, operational exit and
execution authority false. Matching metadata alone cannot establish them.
Family metadata is bounded to256MiB and checked under the original deadline.

Fourteen targeted cases pass Python development/debug execution. Five relevant
registered suites pass85 distinct cases; protocol integrity, schema fixtures and
canonical checks pass. Tests use explicit synthetic metadata families derived
from D350's real software-fixture publication, not180 collected captures.
Coherently rebound negative cases reach the actual shared-identity, global
overlap, phase-order, envelope and numerical guards. Native code is unchanged;
there is no changed native sanitizer path. The original frozen34247ce worker
remains byte-identical.

Supervised archive inverse/analysis, actual input authenticity/custody, the
qualified outer operator/profile, full ETA/resource admission and operational
exit remain. No source preparation, qualification or pilot has started.

Evidence: [verification report](../evidence/stage17/PILOT-D351-FAMILY-VALIDATION-20261123-01/REPORT.md).
