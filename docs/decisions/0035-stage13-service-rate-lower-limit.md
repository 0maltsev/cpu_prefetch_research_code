# ADR-0035: Stage 13 service-rate lower tolerance limit

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Scientific calibration estimator / offered-load basis
- Decision owners: Protocol owner; statistical owner; calibration owner; repository owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: None; resolves D-035
- Lifecycle gate: Accepted before Stage 13 implementation; exact plan and eligible stand evidence remain required before calibration access

## Context and scientific constraints

Protocol Section 5.3 requires fixed-duration independent service-calibration
runs, a one-sided 95% cell lower bound over run-level consumed-event
throughput, and `mu_ref` as the minimum valid cell bound. It leaves the
estimator, duration, and repetition count open. Calibration must otherwise
reproduce the applicable Stage A queue, package, consumer action, placement,
capacity, working-set class, hardware state, clock, reset, and drain behavior;
its sole workload difference is a continuously ready producer.

The estimator must be frozen before values are opened, retain valid low or zero
throughput, and never extend a plan until a favorable number of valid results
exists.

## Options considered

1. A one-sided Student-t lower confidence bound on mean throughput.
2. A percentile or BCa bootstrap lower bound.
3. The sample minimum from a prospectively enumerated independent-run plan as
   a distribution-free lower tolerance limit.

Options 1 and 2 introduce distributional, resampling, seed, dependency, and
finite-sample choices not supplied by the protocol. Option 3 is conservative,
exact over rational throughput inputs, and has a direct finite-sample coverage
statement.

## Decision

Select D-035 suite `SERVICE-RATE-NP-LTL95C95-MIN-v1` as specified by the
accepted
[`STAGE13_CALIBRATION_DECISION_BUNDLE.md`](../STAGE13_CALIBRATION_DECISION_BUNDLE.md):

- for valid independent run `r` in service-calibration cell `c`, retain exact
  integers `consumed_r`, `interval_ticks_r`, and `ticks_per_second`;
- define exact reduced rational throughput
  `T_c,r = consumed_r*ticks_per_second/interval_ticks_r` without a binary
  floating-point conversion;
- enumerate the complete run plan before value access and never top it up,
  selectively repeat it, or discard a valid low result;
- let `n_c` be the number of valid results from that fixed plan and require
  `n_c>=59`; invalid artifacts remain immutable but are estimator-ineligible;
- define `mu_cell,c=min_r(T_c,r)` and
  `mu_ref=min_c(mu_cell,c)` over the complete required 60-cell product; and
- treat `n_c<59`, an incomplete cell product, or missing prerequisite evidence
  as unresolved. A valid zero throughput remains the minimum and cannot be
  replaced.

For independent identically distributed run-level throughput, the sample
minimum is a one-sided 95%-content lower tolerance limit with confidence
`1-(19/20)^n_c`; `n_c=59` exceeds 95% confidence. This suite therefore targets a
conservative lower run-throughput percentile, not a Gaussian mean.

Q12 does not choose duration, exact planned count, seed, namespace, capacity,
stand, authority, or budget and does not produce `mu_cell` or `mu_ref`.

## Evidence

- The protocol and statistical owners answered
  `Q12 - accept the bundle` on 2026-08-21.
- Imported implementation specification Sections 5.1 through 5.3, the data
  dictionary, and the calibration freeze-checklist row.
- NIST's nonparametric one-sided tolerance-limit formulation for population
  percentiles.
- No calibration, pilot, confirmatory, latency, throughput, or queue outcome
  was used to select this estimator.

## Consequences and compatibility

Scientific effect: the estimator is deliberately conservative and can lower
all offered rates or make the design unresolved. It avoids silently imposing a
normal mean model and makes invalid-run attrition visible.

Compatibility effect: content probability, confidence construction, planned
sample grammar, valid-run rule, exact-rational throughput, cell product, and
both minimum operations are suite identity. A mean LCB, interpolated statistic,
floating-point pre-rounding, hidden top-up, or favorable cell omission is not
compatible with v1.

## Verification and acceptance tests

Stage 13 must test exact rational throughput, configuration equality with only
the allowed continuous-ready difference, all 60 cells, run-plan enumeration,
`n=58` rejection, the `n=59` boundary, invalid/partial plans, zero throughput,
cell/global minima, overflow, canonical records, and material-change
invalidation using synthetic inputs only.

Implementation tests do not qualify a stand and may not report a real
throughput, `mu_ref`, load, or performance result.

## Rollback or supersession

Changing the estimand, content/confidence, estimator, eligibility, planned-run
rule, cell product, arithmetic grammar, or minima requires a new method ID,
prospective superseding ADR, and complete recalibration. Existing records
remain immutable and version-bound.

## Protocol-amendment assessment

No amendment is required because the imported protocol explicitly leaves the
one-sided estimator, duration, and count open. If protocol review instead
requires a lower confidence bound on a mean, implementation must stop and that
scientific-meaning conflict requires owner clarification and, if necessary, a
versioned amendment.
