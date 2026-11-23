# D357: fresh environment readback after S180 analysis

Accepted engineering implementation of D310's existing restoration and exit
conditions. No scientific method, source, capture, deadline, control prestate,
resource limit, qualification or Stage18 authority changes.

D356 required actual owned restoration before analysis, but its final report
left live restoration unverified. Historical successful restoration cannot
establish that controls still match after the analysis interval. The new
`final_restoration_observation` consumes one same-process check after completed
restoration. It requires no remaining owned children and fresh original boot,
affinity, absent recovery cgroup/unit file, original root cpuset state,
maintenance enablement/timer activity, inactive recovery service and all three
complete MSR values/device identities. It uses the original maintenance
restoration predicate; it does not require unchanged transient oneshot substates.

The actual closed compaction owner rereads its protected original owner, intent
and restoration receipt. A read-only descriptor and shared nonblocking lock on
the existing lease require the original inode, empty bytes and no exclusive
holder. Fresh control readback must match its actual original prestate, including
zero. No lease creation, adoption, truncation, control write or restoration call
occurs. A changed control or occupied/replaced lease fails without repair.

The final check stays within the caller's existing analysis deadline, the
original absolute day and a120-second local ceiling. It never restarts a deadline.
Failure consumes the check. The original command deadline is restored on return
or failure; the qualified outer remains responsible for durable terminal/failure
retention and stopping the original family.

The D356 coordinator invokes this check only after actual pool completion,
family consistency and unchanged original custody. Its report becomes version2,
with the fresh observation and final-live-restoration true only after the actual
check succeeds. Signed operational exit, termination of the outer operator,
inferential freeze and execution authority remain explicitly unestablished.
This is one exit fact producer, not Stage17 completion from ten resolutions.

Fifteen targeted cases pass Python development/debug allocation. Five affected
registered suites pass74 cases. They exercise real temporary MSR/lease files,
an actual live child and exclusive lock, with explicit systemd/cgroup/CPU doubles.
Changed MSRs, cpusets, maintenance, service state, control, lease, receipt,
children and deadlines all fail. The successful check makes no repairs or file
changes, and cannot repeat. These are software checks, not stand qualification.
No native path changes; frozen34247ce remains byte-identical.

The first contract invocation omitted the pinned Python dependency directory and
failed the rpds version check. The corrected documented environment passes
format/protocol/schema/canonical checks; both logs remain retained. Read-only
stand inspection confirms idle services, no native runner/prospective directory,
unchanged boot/journal and guard1. No operational preparation or raw read occurs.

Fixed operator/profile, complete timing and storage census, whole ETA/budget,
actual admission and the single conditional pilot still precede scoped exit.
Stage18 execution remains deferred.

Evidence: [verification report](../evidence/stage17/PILOT-D357-FINAL-ENVIRONMENT-20261123-01/REPORT.md).
