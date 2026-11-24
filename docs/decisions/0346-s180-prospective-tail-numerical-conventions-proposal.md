# D346 proposal: prospective S180 tail numerical conventions

Status: **PROPOSED — owner decision pending; not executable**.
Amendment: `AMEND-2.0.0-pre.3-D310-TAIL-NUMERICS-v1`.

The immutable specification sections8.1/10.4/10.5 and approved D310 require
inverse-ECDF quantiles, ten consecutive small tail-indicator correlations and a
positive-sequence effective count. They do not specify finite-sample covariance
normalization, adjacent-pair indexing, boundary/degenerate cases or exact numeric
comparison. No pilot autocorrelation/positive-sequence implementation was found in the
current include/src/tools/tests or accepted decision set. Different choices can
produce different effective counts/horizons. Freeze the following conventions
before pilot outcomes; retain all immutable protocol and completed data.

## Unchanged collection and interpretation

This approves no new setting, repetition, source realization, duration, rate,
qualification attempt, clock/control change, storage quota, operational deadline
or Stage18 execution. S180 remains180 settings once,5s warmup/1s measurement,
the original seeds/order, one24-hour window and stop-on-failure/no-retry rules.
No existing calibration is repeated or relabelled. Numerical software and its
verification must still pass before the one conditional family can start.

Use each independently reconciled measurement run's accepted events, ordered
by accepted ordinal, including their normal drain completions. The primary
series is the original integer-tick end-to-end latency `L_i=f_i-a_i`. Preserve
every correctly recorded FULL/drop observation separately; it has no consumer
latency. Do not pool runs, include warmup in measurement statistics, filter
extremes, fill missing events or treat record index as event identity.

Quantiles use the existing exact rank `ceil(p*N)` without interpolation.
Retain ties. A zero quantile stays zero; its logarithm is undefined rather than
replaced by an epsilon. No accepted events means undefined latency quantiles,
with valid all-FULL evidence and its separate zero-loss failure still retained.

## Exact finite-sample autocorrelation

For the primary quantile `q=Q_0.999`, let `I_i=1` exactly when `L_i>q`, and0
otherwise. With `K=sum(I_i)`, `m=K/N`, use the fixed-N autocovariance convention

`gamma_k=(1/N)*sum_{i=0}^{N-k-1}((I_i-m)*(I_{i+k}-m))`, for `0<=k<N`.

Use `rho_k=gamma_k/gamma_0`; do not replace N by N-k, recenter each overlapping
slice, detrend, smooth or impose monotonicity/convexity. All comparisons and
reported defining quantities use exact integer/rational arithmetic. An exact
sparse pair-count implementation is equivalent to direct summation, not a new
estimator. No floating FFT approximation chooses a boundary.

For auditable implementation, if `P_k=sum(I_i*I_{i+k})`, `A_k=sum(I_i)` over
`0..N-k-1`, and `B_k=sum(I_i)` over `k..N-1`, then

`rho_k=[N^2*P_k-N*K*(A_k+B_k)+(N-k)*K^2]/[N*K*(N-K)]`.

If `N=0`, `K=0` or `K=N`, variance is undefined/zero: dependence horizon and
effective count are **UNDEFINED**, with an explicit reason. Do not substitute
independence, a different quantile, jitter, a replacement run or an extended run.

## Correlation horizon and positive sequence

The horizon is the smallest observed lag `h>=1` with `h+9<N` for which all ten
`abs(rho_h),...,abs(rho_{h+9})` are strictly below `1.96/sqrt(N)`. Report both
`h` and the confirmation endpoint `h+9`. Use exactly `1.96=49/25`; for a
correlation `num/den`, the strict test is `625*N*num^2 < 2401*den^2`.
If no such observed ten-lag interval exists, the horizon is **UNRESOLVED**;
do not pretend an administrative lag cutoff is a measured horizon.

For effective count, form `G_j=rho_(2j)+rho_(2j+1)`, starting at j=0. Use only
complete observed pairs (`2j+1<N`). Stop before the first `G_j<=0`; sum the
preceding strictly positive pairs. Set `tau_raw=-1+2*sum(G_j)`.
If no terminating nonpositive complete pair is observed, or `tau_raw<=0`, the
estimate is **UNRESOLVED**. Do not zero-pad beyond the observed series, silently
truncate a positive sequence or select another prefix.

Otherwise set `tau=max(1,tau_raw)` and `N_eff=N/tau` as an exact rational. The
cap enforces the existing protocol requirement `N_eff<=N`; display rounding
does not decide a gate. Primary p99.9 estimability requires the existing exact
`N_eff>=200000`. For secondary p99.99, apply the same convention to its own
strict exceedance indicator and require `N_eff>=2000000` before reporting that
secondary quantile as estimable. Missing/low counts remain explicit outcomes.

The adjacent-pair convention is the initial-positive-sequence construction in
[Geyer's method documentation](https://www.stat.umn.edu/geyer/mcmc/library/mcmc/html/initseq.html).
Its theoretical guarantees concern reversible Markov-chain functionals. No
stationarity, reversibility, confidence coverage or estimator consistency for
the CPU latency process is asserted here; D310 outputs remain descriptive.

## Scope of derived pilot outputs

Report each run's quantiles, exact defining tail counts, horizon, IPS stop,
tau/effective-count fractions, raw counts, duration, FULL and separate gates.
Across the full required valid pilot population, the existing candidate moving
event-block length is `2*max(h)` only when every required horizon is defined.
An undefined required horizon leaves that candidate unresolved; a favorable
subset cannot define it. Genuine low effective count or FULL never authorizes
another run or exclusion. Report unresolved gates without inventing a freeze.

This amendment does not select a future confirmatory horizon, scale, matrix
feasibility, bootstrap repetition/seed contract or precision freeze. Moving-block
resampling/half-double sensitivity remains explicitly NOT_EVALUATED until its
own complete method exists; no successful stability or warmup/confirmation freeze
may be claimed from these numerical outputs alone. S180 still supplies no
repeated-temporal-block covariance estimate. Operational Stage17 exit retains
these limitations and grants no Stage18 permission.

Existing prospective process/memory,5400-second analysis and24-hour limits remain
mandatory. Exhaustion is a retained incomplete analysis, not evidence that a
statistical horizon converged and not authorization for an automatic retry.

Acceptance must bind the exact proposal SHA256 and owner response. Until then,
only independent engineering/raw-integrity work may continue; these proposed
scientific choices cannot be used for actual pilot analysis or launch readiness.
