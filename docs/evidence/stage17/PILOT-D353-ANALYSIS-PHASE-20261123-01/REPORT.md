# D353 analysis bottleneck measured and phase gate verified

Actual stand synthetic timing finds about20s per million accepted events for
the unchanged independent join, including durable write/readback. The original
four-worker proposal projects to2.466h for joins alone at conservative full
capture sizes, exceeding90minutes. A12-core check processes six million events
in14.399s including fixture generation, with actual affinity/topology readbacks,
all children reaped and every temporary synthetic file removed. It projects to
72.165minutes for joins alone, leaving17.835minutes for all other analysis.
These are software-only projections, not a verified whole-analysis/launch ETA.

The new [owned phase resource gate](../../../../tools/stage17_s180_analysis_phase_v1.py)
requires actual same-process source release without descriptor aliases,
successful completed environment restoration, no remaining parent child,
fresh physical/cgroup memory and limits, original affinity/partition and12
distinct physical cores. Admission/expiry failures consume/latch the original
attempt. The original5400s analysis cap,1800s exit reserve and24h window remain.
It launches no worker and grants no scientific, custody or execution authority.

The versioned resource model reserves the larger complete stage, with analysis
bounded to196GiB across12 workers and the parent. A temporary2GiB decoder limit
must be read back inside each16GiB worker; no simultaneous separate decoder is
budgeted. Twelve peak inverse spools plus existing reserve stay within256GiB;
retained joined outputs stay within512GiB workspace. The actual fixed supervisor
must enforce the transition and pool before this resource model can execute.
[Decision, exact counts and remaining prerequisites](../../../decisions/0353-s180-post-restoration-analysis-resource-phase.md).

Eight affected registered suites pass122 distinct cases. All47 ownership,
environment and phase cases pass final Python development/debug allocation.
Format, protocol/schema/canonical and runner/qualification schema checks pass.
The initial missing-monitoring software-fixture failure is retained; the corrected
12-case phase run passes. Explicit synthetic hardware/RAM/topology fixtures have
no stand qualification credit. Native measurement and historical calibration
are unchanged; no new native sanitizer path exists.

The benchmark source closure is pinned to local clean6d2969b and actual hashes.
Only code and small metadata came back to the PC. Original research raw was not
read/copied, no scientific source generated, and no hardware state changed.
Verified redundant PC staging files are removed after evidence retention.
Stage17 remains incomplete: supervised complete analysis, qualified outer
operator/profile, full ETA/resources/admission and the conditional pilot/exit
remain. No operational window or Stage18 execution started.
