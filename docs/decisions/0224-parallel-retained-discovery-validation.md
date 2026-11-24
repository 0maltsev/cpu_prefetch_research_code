# ADR-0224: Bounded parallel validation of retained D207 captures

- Status: `ACCEPTED` — engineering-only offline analysis scheduling
- Date: 2026-11-03
- Scope: existing D207 R3 bytes; no experiment, recollection or method change

The D213 serial reanalysis is CPU-bound on independent retained captures. At
15:47 UTC it was validating capture ordinal 3, with the final report still
pending. The stand reports 32 available CPUs and approximately 255 million kB
of available memory under the original boot. Use bounded parallel processes
to shorten the remaining independent validation work.

The new adapter pins the exact D213 validator SHA256 and invokes its existing
capture validator without changes. It preserves the original bound-document,
native-input, whole-plot, output-budget, control/raw custody and retained-count
checks. All thirty-six captures remain mandatory. Results are put back into
their original prospective order, and the unchanged count-only selector is
called only after the whole family passes. Completion order cannot change
membership, repeat a capture, filter a low count or select a duration early.

Use at most eight worker processes with an explicit address-space ceiling per
worker. The intended stand analysis uses eight workers at 8 GiB each, plus an
8 GiB parent allowance and an 8 GiB supervisor allowance: 80 GiB total.
Fresh admission requires at least eight available CPUs, 80 GiB MemAvailable,
the expected original boot, and disk space for a separate 16 GiB scratch
allowance plus a 16 GiB free-space reserve. Admit a finite 86400-second
whole-analysis deadline before launch. These are analysis resource limits, not
experimental parameters or
changes to the frozen collection budget. Original raw/control bytes remain
read-only; temporary decoding spools and small results use a new analysis
directory outside the immutable output root. Only small provenance/results
return to the PC.

Address-space limits are hard per-process limits. Scratch is monitored once
per second, including unlinked temporary files held by the analysis descendants;
it is not a filesystem quota and can overshoot between polls. The launcher also
checks the 16 GiB free-space reserve. Admission verifies the original retained
control-file size bindings against the 281439954-byte ceiling. Eight times this
ceiling times a conservative factor of six is 13509117792 bytes, below 16 GiB;
the factor is a planning estimate, not a proved serializer expansion bound.

Each worker receives a fixed disjoint subset of prospective captures. There is
no worker respawn or failed-job retry. Exception, unexpected exit, missing or
duplicate result, or deadline failure terminates and reaps the other workers
and yields no selected result. The outer launcher additionally bounds the
entire analysis process group. A successful worker message alone is not a
successful family. Preserve the serial analysis, its original files and any
partial report; running analysis code is never overwritten.

Before stand use, compare the complete thirty-six-capture synthetic result
against serial D213 output. Test late capture corruption, original input/hash
failures, hardware readback failures, worker exception/death/timeout, complete
cleanup and absence of selector calls on any failed family. Record the adapter,
wrapper, decision and dependency hashes in a fresh exclusive analysis intent.
The qualified experiment source and completed custody admission are unchanged.

## Pre-admission rejection and corrected resource allowance

The first D224 launcher in `discovery-analysis-r3-d224-1` rejected before
creating an analysis intent or starting the wrapper. The 281439954-byte control
ceiling above came from a partial summary and did not cover the complete family.
This was a launcher resource-admission rejection; it performed no experiment
and no independent raw reconciliation. Preserve that installed directory,
its code, manifest and rejection receipt without modification.

The complete original retention report has SHA256
`89c5ce6c123195aba3831cc62972bb7c671e07110aa2c051bcb59366c7ceddc0`.
Its largest control is capture 08, 3373611301 bytes, SHA256
`0c96a6c62553469ed74a9b8270f19ab83cee28296b32dfb526d7d19ec541abaa`;
the eight largest controls total 25811843355 bytes. These are original retained
size bindings, not new observations or a scientific interpretation of the raw.

For the fresh exclusive `discovery-analysis-r3-d224-2` preparation, replace the
control ceiling with 3373611301 bytes and the scratch allowance with 256 GiB.
Keep the separate 16 GiB free-space reserve, requiring at least 272 GiB free
disk at fresh admission. The hard address-space limits remain 8 GiB for each
worker, the parent and the supervisor; MemAvailable must still be at least
80 GiB and affinity must expose at least eight CPUs under the expected boot.
The revised conservative scratch estimate is
`8 * 3373611301 * 6 = 161933342448` bytes, below 256 GiB. The sixfold expansion
remains an estimate, not a proved serializer bound. Scratch remains monitored
once per second, including unlinked spools, with possible between-poll overshoot;
it is not a filesystem quota. The whole-analysis deadline remains 86400 seconds.

This accepted offline engineering correction changes neither validator bytes,
capture membership, selector ordering nor scientific acceptance. The new wrapper
and installation manifest bind this revised ADR. Independent launcher tests must
accept a control above the old ceiling when within the new original-byte bound,
and reject a control above the corrected ceiling. No old serial process is killed.
