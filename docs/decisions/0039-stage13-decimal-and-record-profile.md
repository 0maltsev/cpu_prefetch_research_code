# ADR-0039: Stage 13 concrete Decimal and record profile

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Implementation-owned arithmetic / record compatibility
- Decision owners: Repository owner; calibration implementation owner; validation owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: None; implements the delegated concrete-profile closure in ADR-0038
- Lifecycle gate: Stage 13 software closure; no calibration execution authority

## Context and scientific constraints

ADR-0038 accepts an offline Python 3.14 Decimal boundary but delegates the
concrete profile ID, precision, operation order, outward rounding, schemas, and
conformance vectors to Stage 13 implementation. The implementation must never
make a Hoeffding upper bound smaller through numerical rounding and must add no
statistics dependency. All counts, weights, rates, and exposures remain exact
integers or reduced rationals until the single transcendental margin.

## Options considered

1. Binary64 `math.log`/`sqrt` with undocumented error allowance.
2. A new MPFR, SciPy, R, or Boost.Math dependency.
3. Python 3.14 Decimal with 160-digit guard precision, explicit upper enclosure,
   an 80-digit serialized boundary, and a separate 240-digit reference pass.

Options 1 and 2 respectively weaken the conservative bound or violate the
accepted dependency policy. Option 3 uses the already accepted offline runtime
and makes every rounding step and compatibility identifier explicit.

## Decision

Accept arithmetic profile `HOEFFDING-DECIMAL80-GUARD160-UP-v1`:

1. Keep `p_hat` and `sum(w_r^2)` as Python `Fraction` values.
2. Use a local Decimal context with precision 160 and `ROUND_CEILING`.
3. Evaluate `ln(18000)` with Decimal's correctly rounded operation and advance
   it once with `next_plus()`.
4. Convert the exact squared-weight rational upward; multiply by the enclosed
   logarithm and divide by two under `ROUND_CEILING`.
5. Evaluate the square root and advance it once with `next_plus()`.
6. Convert `p_hat` upward, add the margin, and clamp at exactly one.
7. Serialize at 80 significant decimal digits with `ROUND_CEILING`, without an
   exponent. A separate pure-Python `_pydecimal` precision-240 evaluation must
   agree at that boundary and never exceed the selected C-Decimal
   precision-160 enclosure.

Accept these implementation-owned Draft 2020-12 schema identities:

- `cpu-prefetch-calibration-plan/1`;
- `cpu-prefetch-service-rate-result/1`;
- `cpu-prefetch-ring-distance-result/1`;
- `cpu-prefetch-zero-loss-feasibility-result/1`; and
- `cpu-prefetch-calibration-freeze/1`.

All use protocol `2.0.0-pre.2`, `JCS-I64-v1`, explicit artifact IDs and
lowercase SHA-256 values, zero-self record hashing, source lineage, and
append-only no-replace publication. Values outside the `JCS-I64-v1` integer
domain are encoded as grammar-checked exact decimal strings. A material
identity fingerprint is the SHA-256 of the canonical caller-enumerated
platform, build, queue, memory-order, consumer-action, clock, capacity,
hardware-state, schedule, estimator, and arithmetic identities. Any change
invalidates rather than mutates a dependent freeze.

## Evidence

- Q12 accepted ADR-0035 through ADR-0038 and delegated this implementation
  profile without providing stand values.
- Python 3.14 Decimal supplies correctly rounded `ln` and square-root
  operations; the one-ulp advances enclose a possible half-ulp downward result.
- Three direct vectors cover equal and unequal cluster weights and nonzero
  `p_hat`; the independent `_pydecimal` precision-240 pass agrees at the
  80-digit boundary.
- Six positive and sixteen negative schema fixtures and append-only overwrite
  tests pass using synthetic records only.

## Consequences and compatibility

Scientific effect: outward rounding can only make the accepted feasibility
test at least as conservative at the recorded decimal boundary. It does not
change the D-036 estimator, confidence family, exposure equation, threshold,
or global ladder.

Compatibility effect: precision, operation order, `next_plus()` sites, decimal
serialization, five schema identities, fingerprint grammar, and hash profile
are version identity. Another implementation may reproduce v1 only by passing
the same boundary and structural/semantic conformance suite.

## Verification and acceptance tests

Require direct vectors, precision-240 reference comparison, finite all-zero
positive bounds, clamp-to-one, unequal weights, exact 180-cell exposure,
unknown/mixed-version rejection, canonical round trip, material-change
invalidation, and attempted-overwrite rejection. Development fixtures are
labelled synthetic and cannot be cited as platform calibration evidence.

## Rollback or supersession

A precision, rounding, operation-order, serialization, schema, fingerprint,
hash, runtime, or dependency change requires a new profile/schema version and
superseding ADR. Prior records remain immutable and bound to v1.

## Protocol-amendment assessment

No amendment is required: the accepted estimator and scientific thresholds
are unchanged, and ADR-0038 explicitly delegates the concrete conservative
arithmetic and record implementation. A smaller-than-mathematical upper bound,
changed estimator, hidden default, or discarded evidence conflicts with the
accepted decision and must not be implemented.
