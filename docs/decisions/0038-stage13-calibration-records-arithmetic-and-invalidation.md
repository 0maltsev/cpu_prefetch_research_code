# ADR-0038: Stage 13 calibration records, arithmetic, and invalidation

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Calibration data contract / arithmetic / lifecycle / compatibility
- Decision owners: Repository owner; validation owner; calibration owner; data-integrity owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: None; resolves D-038
- Lifecycle gate: Accepted before Stage 13 implementation; concrete schemas, arithmetic profile, and conformance suite must close Stage 13 software

## Context and scientific constraints

D-035 through D-037 require prospective plans, exact source relationships,
checked arithmetic, explicit unresolved results, and append-only freezes. The
imported schemas do not define calibration-specific records. Configuration,
statistics, hashing, serialization, allocation, and artifact publication must
remain outside each calibration timed interval.

The implementation must not hide missing external facts, repair a failed plan,
reinterpret an old result under a new method, or add a statistics dependency
for convenience.

## Options considered

1. Unversioned human-readable calibration reports.
2. A new third-party statistics runtime and its native serialization.
3. Implementation-owned versioned canonical records, checked exact arithmetic,
   a minimal versioned offline Decimal boundary, and append-only invalidation.

Options 1 and 2 weaken compatibility, auditability, offline reproducibility,
or the accepted dependency policy. Option 3 preserves the logical protocol
model and makes every method/input relationship explicit.

## Decision

Select D-038 as specified by the accepted
[`STAGE13_CALIBRATION_DECISION_BUNDLE.md`](../STAGE13_CALIBRATION_DECISION_BUNDLE.md):

- add implementation-owned Draft 2020-12 logical schemas for versioned
  calibration plan, service-rate result, ring-distance result, zero-loss
  feasibility result, and calibration freeze records;
- use explicit artifact IDs, source IDs and SHA-256 values, protocol
  `2.0.0-pre.2`, `JCS-I64-v1`, zero-self SHA-256 where applicable, and no path
  parsing;
- store counts, ticks, rates, throughput comparisons, quantiles, exposure,
  geometry, and distance arithmetic as checked integers or exact reduced
  rationals;
- restrict transcendental evaluation to the positive Hoeffding margin in an
  offline implementation-owned Python 3.14 Decimal suite with a new explicit
  profile ID, precision, operation order, and conservative outward rounding;
- publish direct boundary vectors and independent higher-precision reference
  vectors before accepting that concrete arithmetic implementation;
- add no SciPy, R runtime, Boost.Math, or other dependency under Q12;
- enumerate every plan before value access; retain failures and partial
  products append-only; forbid hidden top-up, retry-until-valid, selective
  rerun, mutable result files, and placeholder results; and
- invalidate every dependent freeze after a material platform, build, queue,
  memory-order, consumer-action, clock/boundary, capacity/geometry,
  hardware-state, package, schedule, estimator, or arithmetic-profile change.

The concrete schema IDs, field grammars, Decimal precision/order/profile ID,
and conformance vectors are Stage 13 implementation outputs. They must be
explicitly recorded and reviewed before Stage 13 can close; Q12 does not
silently supply them. They may not change D-035 through D-037 equations,
coverage, thresholds, eligibility, or global action.

An absent prerequisite or incomplete estimator emits a stable
`NOT_EVALUATED` or blocking state. A provisional matrix calculation cannot be
frozen as final until immutable `Rtotal`, `Nruns`, and schedules exist.

## Evidence

- The protocol, statistical, and repository owners answered
  `Q12 - accept the bundle` on 2026-08-21.
- ADR-0001, ADR-0004 through ADR-0006, ADR-0015, ADR-0022, and ADR-0034.
- Imported lifecycle, integrity, failure, access, version, and calibration
  requirements.
- The accepted Python standard-library boundary adds no new dependency or
  license; no calibration result selected the record or arithmetic policy.

## Consequences and compatibility

Scientific effect: prospective enumeration and explicit unresolved states
prevent favorable completion, deletion, or repair. Outward rounding must never
make a feasibility upper bound smaller than the exact mathematical value.

Compatibility effect: schemas, canonicalization, arithmetic profile, method
IDs, source graph, record completeness, and invalidation fingerprint are
compatibility identity. Unknown versions and mixed graphs fail closed. Old
records remain immutable and require a new derived identity plus explicit
lineage for conversion.

## Verification and acceptance tests

Stage 13 must provide structural and semantic positive/negative fixtures,
canonical round trips, mixed-version rejection, source/hash/identity checks,
partial-plan and no-top-up faults, material-change invalidation, exact rational
and overflow tests, direct/outward Decimal vectors, independent reference
vectors, and applicable sanitizer/static/package checks using synthetic inputs
only.

The concrete arithmetic profile is not accepted merely because code compiles:
its versioned operation order, precision, outward-rounding proof, and vectors
are Stage 13 closure evidence.

## Rollback or supersession

Changing a record family, schema, canonicalization, arithmetic profile,
rounding direction, dependency, lifecycle rule, source graph, or invalidation
fingerprint requires a new version and superseding ADR. Existing records remain
immutable and version-bound. A new dependency also requires the accepted
dependency/license review.

## Protocol-amendment assessment

No amendment is required because this decision supplies implementation-owned
records and arithmetic for the protocol's explicitly open calibration methods.
Any record or lifecycle rule that discards required observations, hides
missing evidence, changes a scientific equation, allows outcome-driven repair,
or moves offline work into a measured path conflicts with protocol-fixed
behavior and requires protocol review.
