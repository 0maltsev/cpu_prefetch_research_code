# D347: exact implementation of the accepted D346 numerical method

Accepted engineering implementation of the unchanged owner-approved D346
proposal and acceptance. This library computes descriptive numerical results;
it grants no raw-validity, qualification, scientific-freeze or execution claim.
Immutable protocol files, completed calibration and frozen native34247ce remain
unchanged. No operational window or research source has started.

`stage17_s180_tail_numerics_v1` verifies the exact approved proposal/acceptance
bytes before calculating. Its input is a bounded explicit sequence of exact
unsigned64 end-to-end tick values in accepted order. The caller must first
independently establish raw reconciliation, schedule and provenance. A numerical
report explicitly records that this library performs none of those checks.

Snapshot into packed unsigned64 storage and hash the ordered big-endian words
with a versioned domain/count. Exact inverse-ECDF sorting retains ties and zero
quantiles. Sparse positive-lag exceedance pair counts give the exact fixed-N
covariance formula approved in D346. Integer comparisons select the strict
ten-lag horizon; rational arithmetic computes complete adjacent IPS pairs,
the observed nonpositive stop, autocorrelation time and effective count.
No FFT rounding, fabricated stop, positive-pair truncation or zero padding is
used. Undefined variance, absent observed stops, nonpositive raw time and
low effective count remain explicit. Secondary p9999 uses its own indicator
and own two-million effective-count gate. Effective counts never exceed N.

The engineering sample ceiling is2505857, derived from D334's unchanged
ceil(2*5011713/4) measurement offered-count ceiling. Each actual call must also
provide its authenticated per-run maximum and remaining original analysis
deadline. Check that deadline during copying, histogram creation and lag scans.
Sorting is bounded by the frozen count and checked immediately afterward; the
qualified supervising process must enforce the actual wall deadline too.
Histogram work is O(N+K²); the strict p999 tail has at most ceil(N/1000)
exceedances. Synthetic maximum-size stand timing tests this numerical workload,
not empirical CPU latency, full raw validation or the whole operational ETA.

Serialize exact fractions as canonical decimal numerator/positive-denominator
strings: their defining products may exceed JCS-I64 even though individual
observations fit unsigned64. The closed versioned schema rejects changed
authority, malformed fractions and inconsistent secondary suppression. Semantic
correctness remains the implementation/independent-test responsibility.

The aggregate helper requires the exact complete180-run identity set and this
method's reports. It proposes2*max(h) only when every horizon is observed.
It does not select a favorable subset, establish family validity, implement
stability resampling, freeze warmup/horizon or authorize Stage18. Undefined
horizons keep the candidate unresolved; low effective counts never cause runs
to be repeated or extended.

Verification uses a separate direct centered rational covariance reference on
all binary sequences of lengths1–9 and additional dispersed/clustered inputs.
Sixteen cases cover ties, rank and strict-threshold boundaries, raw/secondary
effective-count gates, empty/degenerate/absent-stop cases, integer overflow,
proposal/acceptance tampering, deadlines and full-population aggregation.
All pass registered CTest and Python development/debug execution. No production
C++ or new native sanitizer path is changed.

The stand software-only timing fixture is pinned to the exact implementation,
approved documents, actual CPU3 affinity and child-only16GiB address-space cap.
Largest array2505857 takes2.260431006s dispersed and1.753781225s clustered,
with187864KiB peak RSS. These four synthetic cases read no original raw data,
generate no research sources and perform no qualification or operational start.

Evidence: [verification report](../evidence/stage17/PILOT-D347-TAIL-NUMERICS-20261123-01/REPORT.md).
