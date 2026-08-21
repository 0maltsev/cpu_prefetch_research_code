# Stage 15 Offline Analysis

Protocol version: **`2.0.0-pre.2`**

`cpu_prefetch_analysis` is an offline, synthetic-only implementation of the
registered Stage A analysis. It cannot control the stand, execute a queue, open
outcomes without a passing Stage 14 access grant, or turn a synthetic result
into empirical evidence.

## Versioned pipeline

The pipeline records these ordered stages:

1. finalized artifact, version, ID, and SHA-256 validation;
2. exact Stage 12 reconciliation or verification of a named prior proof;
3. exact joined-interval verification;
4. independent validity, count, zero-loss, and effective-tail gates;
5. inverse-ECDF p50, p90, p99, p99.9, qualifying p99.99, maximum, exact
   throughput/full ratios, and registered subpath diagnostics;
6. exact complete-block construction without a filter or cell-repair API;
7. H3 training access and six-context selection;
8. immutable zero-self-hashed selection output;
9. validation-unseal evidence verification;
10. 54 selected-minus-alternative validation comparisons;
11. one-sided H3 evaluation;
12. H1/H2 release evidence verification;
13. separate seven- and twenty-member two-sided max-T inference; and
14. canonical machine and explicitly synthetic human reports.

Every run projection and compact fixture payload is immutable and
content-hashed. Mixed `pre.1`/`pre.2` graphs, incomplete evidence, failed
checksums, unknown schemas, invalid joins, unevaluated validity, sealed access,
missing cells, active invalid blocks, cell repair, and unexplained filtering
fail closed.

## Quantiles, gates, and diagnostics

For a sorted run distribution of size `N`, every registered quantile is
`X_(ceil(pN))`; equal observations remain separate through exact
multiplicities. Events are never pooled across runs. The primary response is
`log(Qhat_0.999)`. Diagnostic series use the same inverse-ECDF estimator and
remain separate from the additive end-to-end response. Exact consumed-event
throughput, full fraction, final occupancy, raw/effective counts, and maximum
are retained.

`FULL` and genuine low effective count preserve a valid run and its summaries,
but block dependent primary inference. An invalid run makes an active original
block incomplete and is refused. A retained inactive original may be replaced
only by a Stage 14-validated complete block with passing frozen-budget evidence.

## Registered complete-block inference

The frozen fixed design contains 40 full-rank columns: package baseline,
hardware/context main effects, queue/context, queue/hardware,
hardware/software, hardware/context, and software/context terms. For the
balanced complete product, the registered contrasts are exact equal-weight
cell linear functions. This is algebraically the registered refit while making
the contrast weights directly reviewable.

H1 contains exactly seven two-sided contrasts and H2 exactly twenty. They are
never merged. Each bootstrap replicate resamples complete temporal blocks with
replacement, thereby preserving both whole plots, all 180 cells, pairing, and
seed structure. The implementation uses the accepted explicit Philox stream,
sample covariance across replicate contrast vectors, standardized max-T, and
the non-interpolated empirical 95th percentile. No event-level bootstrap is
present.

Prospective precision accepts immutable complete width vectors for the exact
7/20/270/540 registries. It applies the fixed minima, `delta_star/2` rule,
H1/H2 ceiling, and `R12`/`Rtotal`/`Nruns` equations. It deliberately does not
invent missing pilot covariance, extrapolation, counts, or a practical bound.

## H3 chronology

Training requires all registered candidates in all six L050 contexts across
at least twelve complete `H3_TRAIN` blocks. It selects the smallest arithmetic
mean of run-level log-p99.9, breaking exact ties by the registered package-first
candidate order. Its immutable record binds every training source, rule
version, six selections, and a zero-self SHA-256.

Validation cannot be evaluated without a Stage 14 grant at
`VALIDATION_UNSEALED` or later. The 54 selected-minus-alternative differences
are a subset of the prospectively sized 540 ordered family. Complete validation
blocks are resampled for the one-sided max-T upper limits. H1/H2 are evaluated
only after a separate `H1H2_RELEASED` grant names the entire active pool.

## Synthetic fixture boundary

`SYNTHETIC-RLE-LATENCY-TICKS-v1` compactly describes analytically constructed
distributions of 200,000 or more observations without allocating a fabricated
raw stream. It is accepted only by `STAGE-A-OFFLINE-ANALYSIS-SYNTHETIC-v1` and
cannot be cited as a production physical format or observation artifact.

Fixtures cover known null/shift, exact ties, insufficient p99.9/p99.99 tail,
valid `FULL`, incomplete originals, authorized complete replacement,
replacement-budget failure, sealed validation, invalid joins, bad hashes,
mixed versions, and filtering/cell-repair attempts. Machine reports carry
`SYNTHETIC_KNOWN_ANSWER_ONLY`; human reports state that they contain no
empirical findings. Sensitivity and diagnostic products are labeled
non-primary.

## Focused verification

```sh
cmake --build --preset dev-gcc --target analysis-check
ctest --preset dev-gcc -L analysis --output-on-failure
ctest --preset asan-ubsan-gcc -L analysis --output-on-failure
ctest --preset tsan-gcc -L analysis --output-on-failure
ctest --preset asan-ubsan-clang-libcxx -L analysis --output-on-failure
ctest --preset tsan-clang-libcxx -L analysis --output-on-failure
```

These commands perform no performance experiment and create no pilot or
confirmatory output.
