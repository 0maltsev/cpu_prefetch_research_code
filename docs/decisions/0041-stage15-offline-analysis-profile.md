# ADR-0041: Stage 15 offline analysis profile

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Implementation-owned statistical execution and compatibility profile
- Decision owners: Repository owner; protocol/statistical owner; analysis owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: None
- Lifecycle gate: Stage 15 synthetic software closure; no pilot or confirmatory authority

## Context and scientific constraints

The imported protocol fixes the inverse-ECDF run quantile, run as the
independent unit, the complete temporal block as the sole primary bootstrap
unit, separate H1/H2 families, the H3 candidate/context/tie rules, the
pre-sized 540 validation family and 54 post-selection comparisons, access
chronology, zero-loss/tail gates, and complete-block replacement. It leaves
the concrete `delta_star`, bootstrap count/key/seed, prospective covariance,
repetition counts, platform evidence, and outcome artifacts external.

## Options considered

1. Add a general statistical framework and translate the registered design
   into its default model/bootstrap conventions.
2. Bootstrap events or individual factor cells and repair missing cells before
   fitting.
3. Implement the registered balanced complete-block contrasts directly,
   prove the frozen design rank, resample only complete blocks, and reject any
   unresolved input or access gate.

Options 1 and 2 risk silent method substitution, pseudo-replication, or
cell-level repair. Option 3 is the smallest implementation that preserves the
scientific contract.

## Decision

Accept `STAGE-A-OFFLINE-ANALYSIS-SYNTHETIC-v1`:

- one invocation is conditioned on exactly one platform and build; a future
  multi-platform random-effects profile requires separate prospective review;
- the balanced 180-cell design is represented by the exact 40 registered
  fixed-effect columns and must have full rank;
- registered contrast estimates are evaluated as equal-weight complete-cell
  linear functions, algebraically identical to refitting those contrasts in
  the balanced full-rank design;
- H1 and H2 use separate two-sided seven- and twenty-member max-T families;
- each bootstrap draw samples complete temporal blocks with replacement using
  an explicit pre-derived key under `PHILOX4X32-10-HMAC-SHA256-v1`;
- covariance is the ordinary sample covariance of bootstrap contrast vectors
  with denominator `B_boot-1`, and the empirical 95th percentile uses the
  protocol's non-interpolated inverse-ECDF rank `ceil(0.95*B_boot)`;
- H3 training uses only the twelve-or-more training blocks, arithmetic means
  of run-level log-p99.9, and the fixed candidate-order tie break;
- held-out inference resamples complete validation blocks and controls the 54
  selected-minus-alternative one-sided family; the immutable prospective
  evidence must still prove sizing against all 540 ordered comparisons;
- prospective precision code consumes complete immutable 7/20/270/540 width
  curves and selects the first count satisfying `delta_star/2`; it does not
  invent a covariance-scaling or pilot-extrapolation rule; and
- canonical reports serialize binary64 results by exact hexadecimal bit
  identity, list immutable source hashes and software/configuration versions,
  and use a zero-self SHA-256 output envelope.

`SYNTHETIC-RLE-LATENCY-TICKS-v1` is accepted only as a compact known-answer
fixture encoding. It is marked synthetic in every output and is not a
production raw-observation format, joined artifact, empirical result, or
pilot/confirmatory input.

## Evidence

- Protocol Sections 8.1 and 10 fix quantiles, block resampling, max-T
  standardization, families, sidedness, selection, and gates.
- Stage 12 supplies exact reconciliation/derived intervals, and Stage 14
  supplies exact block/access/replacement proofs.
- Synthetic tests cover exact quantile ranks/ties, design rank, prospective
  family cardinality, known null/shift max-T cases, six-context selection ties,
  complete end-to-end analysis, immutable output reproduction, invalid joins,
  mixed versions/checksums, sealed access, valid `FULL`, insufficient tail,
  incomplete/cell-repaired blocks, replacement lineage, and budget failure.

## Consequences and compatibility

Scientific effect: none. The profile executes the imported estimands and
refuses absent pilot/freeze evidence. It never uses event-level resampling,
pooled quantiles, a combined 27-member family, observed-effect resizing, or
incomplete primary blocks.

Compatibility effect: design columns, contrast weights/order, bootstrap unit,
RNG draw mapping, covariance divisor, empirical critical-value rank, H3 family,
binary64 serialization, and zero-self hash grammar are profile identity.
Different choices require a new profile and cannot reinterpret v1 outputs.

## Verification and acceptance tests

Require GCC and Clang full builds/tests, focused known-answer and prohibited-
input tests, all four sanitizer matrices, formatting, static analysis,
protocol/schema/canonical/document/dependency/CI checks, and package review.
Every fixture/report must say synthetic and contain no empirical claim.

## Rollback or supersession

Corrections create a new derived artifact linked to unchanged sources. A
change to a scientific estimand, contrast, family, sidedness, bootstrap unit,
selection/access rule, or exclusion/replacement rule requires protocol-owner
review and normally a versioned amendment. An implementation-profile change
requires a superseding ADR, new suite/version, and full known-answer replay.

## Protocol-amendment assessment

No amendment is required. This ADR fills execution and serialization seams
without changing any fixed scientific rule. Concrete pilot values and
authorities remain unresolved and cannot be inferred from synthetic fixtures.
