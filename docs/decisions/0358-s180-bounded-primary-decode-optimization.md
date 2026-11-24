# D358: bounded primary decoding and equivalent packed clock checks

Accepted engineering optimization following a measured analysis-budget risk.
No measurement, source, estimator, row, clock rule, integrity check, archive
codec, deadline, resource limit or execution authority changes. Frozen native
34247ce and historical calibration remain unchanged.

On the actual stand, clean764c45a software takes61.333seconds to inverse eight
synthetic archives, validate two million accepted events and publish/read back
joined results. Twelve distinct physical cores process2.4million synthetic
events in8.560seconds after a preparation barrier, including actual child exit
and reap. Linear projection of that concurrent throughput to the unchanged
1804216800-row ceiling is6435.136seconds, about107.25minutes, before maximum
control metadata and whole-family overhead. This is a software timing risk,
not an actual5400-second family run or a scientific result. It blocks claiming
the analysis estimate fits; no experiment is launched.

Profiling the synthetic100000-event-per-phase case attributes2.287seconds to
1800004 clock-pair calls, including3600052 repeated uint checks, and2.654seconds
to400002 individual row decodes. Profiled timings include instrumentation and
are not used as uninstrumented throughput. The fixture uses small synthetic
54-query controls, capacity512, longest actual44-byte identity widths, the
stand interpreter and its already-provisioned accepted zstd1.5.7 image. Its
encoder is the independent software fixture, not the production encoder. All
research data and controls remain untouched. The initial stand fixture failed
at its PC-only default library path; selecting the observed accepted stand
codec fixes the fixture without installing or replacing anything.

The S180 join now reads at most64KiB of whole rows per primary block through
the original hashed stream. A cached Struct decodes every row only after exact
length/UTF8 identity/zero-padding prefix comparison. Per-row order, flags,
record index, accepted ordinal, timestamps, FULL exclusion, checksum and joined
tuple construction remain unchanged. Original file/hash/stamp checks and full
candidate fsync/hash reconstruction remain mandatory. Two bounded buffers add
at most128KiB; there is no whole-primary materialization or hot-loop change.

Packed clock words already have exact uint64 types/ranges from Struct. Requiring
absolute>=origin and(absolute-origin)*1000==relative is equivalent to the old
checked conversion: equality to a uint64 relative word also bounds the product,
so overflow cannot be admitted. The accepted publication clock is checked only
for accepted rows, exactly as before; FULL accepted-only fields must remain zero.
The shared original decoder and archive format are unchanged.

Two new oracle cases compare both15/10-word block decoders to the original
decoder across multiple blocks, UTF8 identities and maximum padding widths,
and compare valid/invalid boundary/random uint64 clocks to the original checked
conversion. Prefix/short-block failures and original mutation/hash/clock/ordinal/
FULL/drain/golden joined-row cases pass. The mutation test now injects its same-byte
write at the hashed-read boundary, retaining the actual timestamp/stamp failure.

All18 join cases pass Python development/debug allocation; seven affected suites
pass100 cases. Pinned format/protocol/schema/canonical, AST and whitespace checks
pass. No native code changes or new native sanitizer path exist. Local timing
is software evidence only and cannot establish the stand budget.

The optimized clean source must be retimed on the stand. No success projection,
whole-analysis budget, whole-run ETA or actual admission is claimed here. Larger
controls/context reconstruction and fixed operator/profile/census remain before
the one conditional pilot and scoped exit. No operational window has started;
Stage18 execution remains deferred.

Evidence: [baseline timings and verification](../evidence/stage17/PILOT-D358-ANALYSIS-TIMING-20261123-01/REPORT.md).
