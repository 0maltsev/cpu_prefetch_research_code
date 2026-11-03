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
