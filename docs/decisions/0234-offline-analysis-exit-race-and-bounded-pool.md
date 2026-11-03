# ADR-0234: Offline analysis exit-race repair and bounded scheduling

- Status: `ACCEPTED` — scoped engineering correction, verification required
- Date: 2026-11-03
- Scope: Reanalysis of the unchanged D207 R3 artifacts only
- Scientific method and experiment authority: unchanged; no new collection

The D224 parallel supervisor stopped at 17:29:13 UTC after 18 capture checks
passed. Its scratch monitor received `EACCES` while listing `/proc/32835/fd`;
that owned worker exited successfully. The supervisor conservatively terminated
and reaped its entire own child family. The result is `ANALYSIS_ABORTED`, not a
validated study. Original raw and the older serial analysis remain preserved.

Repair only the offline supervisor's process-lifetime observation. Retain a
pidfd and process start-time identity for every owned descendant. A procfs
permission failure may be treated as an exited-process observation only when
that exact pidfd proves exit; live permission failures remain blocking. Bound
the exit recheck, account for PID reuse, and do not signal unrelated processes.
Test actual exiting/zombie children, live permission failures, descriptor
disappearance, cleanup and existing deadline/resource failure cases.

Use a separate `stage17_discovery_validation_parallel_v2.py` adapter with at most
16 workers. Schedule larger control artifacts first, using only already bound
file sizes, and distribute the resulting fixed job list across workers. This
changes offline work order only. Every original `validate_capture` check still
runs under the exact D213 v3 checker SHA256
`661613aedbc77fd538970b8c5e79a4bbaa3d2acb7f503cb802725239b25e94bf`.
Restore original capture ordinals before applying the unchanged D207 selector.
No partial-family selection, automatic worker retry or empirical run credit.

Before launch require the same boot, at least 16 available CPUs and 144 GiB
MemAvailable: 16 workers, one parent and one supervisor, each with an enforced
8 GiB address-space ceiling. Require 512 GiB scratch allowance plus a separate
16 GiB disk reserve. The sixfold control-expansion estimate is planning context,
not a proved bound. Scratch polling includes open unlinked spools and can
overshoot between polls; it is not a filesystem quota. Keep the 24-hour whole-job
deadline and existing process cleanup. These are offline analysis resources,
not D233's future formal archival quota or a concurrent experimental allowance.

Install exclusively in `discovery-analysis-r3-d234-1`. Preserve both prior D224
installations, aborted receipts, exact source snapshots and partial progress.
Fresh full-study custody admission and all 36 capture checks are required; the
18 progress messages alone cannot substitute for retained result objects.

Verification requires exact serial/16-worker result equality, deliberately
out-of-order completion, original-order selection, corrupt/missing input
rejection, worker death/timeout, full reaping and rejection above 16 workers.
Launch only after the corrected supervisor, wrapper and adapter checks pass and
their exact installation bytes are pinned. No raw mutation or hardware action
is added by this correction.
