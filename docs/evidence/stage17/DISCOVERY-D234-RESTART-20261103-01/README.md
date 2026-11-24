# D234 retained-data analysis restart

D224 attempt 2 aborted at 17:29:13 UTC on 2026-11-03 after 18/36 capture
progress checks. An exiting worker made `/proc/<pid>/fd` inaccessible before
its exit was observed. The original terminal receipt records all owned children
reaped. No duration was selected and no raw data was changed. The original
terminal files are preserved byte-for-byte under `d224-aborted-*`; the inventory
binds their sizes and SHA256 values.

D234 repairs process-exit observation using pinned pidfds and start identities,
while still rejecting inaccessible descriptors of a live worker. The launcher
passed 20 tests, the wrapper 13, and the parallel adapter 13 plus its targeted
largest-control-first ordering/serial-equivalence check.

A new exclusive stand directory `discovery-analysis-r3-d234-1` was installed and
started at 17:45:42 UTC. Supervisor PID 35143. Fresh admission observed
261,340,426,240 available memory bytes and 6,933,554,974,720 available disk bytes.
The pool has 16 workers, each with an 8 GiB address-space ceiling; aggregate
admission includes parent/supervisor, requiring 144 GiB available memory.
Scratch is monitored at 512 GiB (not a hard quota), with 16 GiB reserve and a
24-hour deadline. All 36 captures are revalidated; partial previous progress
is not substituted for a completed result. Original serial analysis remains.

Full validation and duration selection remain pending. This is offline analysis
of existing evidence and authorizes no experimental invocation.
