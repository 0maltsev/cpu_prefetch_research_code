# D210/D211 components and D213 independent analysis

Software verification only. The qualified experiment remains at `a1ade11`;
these changes do not qualify a new worker or authorize formal collection.

The persistent service-session component prepares the same workers once,
performs actual warmup/drain/parked reset, releases a fresh measurement origin
and retains failure evidence. It exercises all five existing packages. Two
clock regressions failed before correction and pass afterward: a late terminal
empty poll and an origin that regresses into the prior warmup drain.

The D211 cold C++ counter and independent Python raw decoder retain total
consumed and interval counts separately, implement the approved half-open
completion window, and reject malformed clock bindings or rows even outside
the interval. Formal output/admission integration remains required.

Accepted hermetic runtime: GCC 16.1.1, Clang/libc++ 22.1.6, glibc 2.43,
Python 3.14.5 and CMake/CTest 4.3.3. Development and all four sanitizer
configurations ran the 28 selected CTest entries: 14 service-session tests,
13 native counter tests and the 17-case Python suite as one CTest entry.
Clang TSan passes 27 entries and explicitly skips the unsupported global
allocation-replacement assertion; all its functional cases run. The other
four configurations pass all 28. Changed-file strict static analysis and
format checks pass. Exact commands, source hashes, logs and limitations are
in `component/verification-summary-with-d213.json` and its bound records.

D213's corrected independent validator passes 22 tests, including the original
validation and metadata regressions, the native H0/H1 action-log shape,
corrupted/missing per-capture hardware evidence, and separate analysis-module
placement. Its registered CTest also passes. The original v2 validator remains
byte-identical. The separate reanalysis wrapper passes 13 metadata, custody,
lineage, exclusive-output and rejection tests; expensive whole-study processing
is stubbed only in those wrapper orchestration tests, not in the validator tests
or actual stand analysis.

`analysis/` preserves the frozen wrapper, tests, exact installation bindings
and launcher. It started one analysis of the unchanged D207 family on the stand
at 14:48:46 UTC, PID 31525, in a new directory. The original rejected analysis
remains retained. No raw stream was transferred and no new experiment ran.
Stand analysis results are separate evidence and remain pending at this checkpoint.

`inventory.json` records every copied evidence file's original path, size and
SHA256. Source bindings were checked against the actual working files before
retention. Earlier mixed-environment attempts remain in the ignored preparation
directory; only the explicitly hermetic final matrix supports this record.
