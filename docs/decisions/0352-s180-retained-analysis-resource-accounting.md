# D352: reserve retained analysis output within existing storage limits

Accepted engineering completion of D326/D331/D350 accounting. The D310180
captures, original sources, estimates, durations, raw custody, native worker,
process caps and operational limits are unchanged. There is no new experiment,
storage-policy exception, replacement or execution authority.

D350 retains the two joined streams and their immutable envelope targets after
successful inverse-spool cleanup. The earlier live resource gate charged peak
native publication and four inverse spools, but omitted the accumulated joined
output from the workspace comparison. Before any real admission, include it
in the existing512GiB workspace and its inode inventory.

`analysis_output_envelope` validates the original blueprint/order and paired
sources. For each phase reserve one joined24-word row for every original
offered event, using its actual encoded run-identity row width. Take no FULL,
compression or sparse-file credit. Reserve the existing one-MiB D350 metadata
bound plus one additional MiB per capture as an engineering allowance for
allocation/objects. This allowance is not a measured filesystem property or
guarantee: actual publishers and their supervisor must enforce allocated and
logical charges, retaining failure evidence on any overrun. Reserve18 objects
per capture plus64 family metadata objects. The qualified four-worker runner
must use these per-capture limits, not silently discard successful joined data.

The live resource evidence becomes version2. Its authenticated external
declaration must additionally provide `workspace_committed_bytes` and
`scratch_committed_bytes`, with no zero default. They cover other retained,
failed and prospective usage within the same W/S ceilings. The qualified outer
must establish and authenticate their census/declaration ancestry; this pure
arithmetic does not discover old scratch or claim a platform observation.
Existing outside-Q/W/S future free-space/inode commitments remain separately
declared. Do not double-subtract physically retained bytes from actual free
space or count inside-W/S obligations as unrelated outside-pool reservations.

Add all joined-output/metadata/allocation reservations and other workspace
commitments to the existing workspace comparison. Add other scratch commitments
to the unchanged four-peak-spool plus17GiB scratch reserve. Extend future object
counts without adding fictitious ledger records. The existing remaining shared
6TB quota, free-space and reserve checks remain mandatory. No limit increases.

Against the unchanged D334 ceilings, joined logical output remains433012032000
bytes. Its complete output budget becomes433389519360 bytes. Including both
peak native/publication representations, archive staging and final metadata
gives447990954726 workspace bytes, leaving101764859162 bytes for other W
commitments. Scratch leaves237363220020 bytes for other S commitments. These
zero-other-commitment calculations are prospective arithmetic, not a census,
actual source counts, resource admission or a whole-run ETA.

Tests cover the independently calculated physical row equation, complete output
and inode reservations, an overflow caused specifically by the formerly omitted
joined output, retained W/S boundary overruns, reordered inputs and rejection of
the old declaration without explicit commitments. The existing live ownership,
locked-store, source, hardware/resource replay and failure-latching tests remain.
Native code and frozen native34247ce are unchanged; Python development/debug
checks exercise the changed path. Operational launch still requires the complete
qualified supervisor/profile, actual census and original-day ETA/admission.

Evidence: [verification report](../evidence/stage17/PILOT-D352-ANALYSIS-RESOURCES-20261123-01/REPORT.md).
