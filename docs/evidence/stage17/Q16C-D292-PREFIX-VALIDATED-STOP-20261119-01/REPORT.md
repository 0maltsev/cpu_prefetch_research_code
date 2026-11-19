# All86 retained captures validated; D292 stopped in qualification setup

Checked19November2026 at17:14UTC (20:14Moscow); report hashes and current hardware
readbacks verified at17:15:10UTC (20:15:10Moscow). The dedicated D292 service is
failed, MainPID0/exit1. It stopped at **15:59:11UTC (18:59:11Moscow)** after
approximately21minutes. The previous6–9h completion estimate is withdrawn.

Completed and preserved:

- **86/86 original captures passed independent raw reconciliation and capture
  execution-evidence validation.** Every original ordinal0–85 is present. The
  accepted prefix manifest records all_required_reports_valid=true. Failed
  original ordinal86 remains separate diagnostic evidence.
- Rehashed all86 report files against the completed-analysis bindings and
  accepted-prefix manifest: every size/SHA256 matches. All86 process receipts
  record exit0 and leader_reaped=true; the completion records all_workers_reaped.
  This verification read reports only; no raw capture was decoded again.
- All86 reports explicitly retain family_validity_established=false and no
  execution/Stage18 authority. Full180 calibration/composition remains pending.
  The original platform stratum remains UNRECORDED. Raw validity does not imply
  passing the separate zero-loss gate.
- No near/far clock, persistent Q15-R/W, qualification prerequisite step, new
  family preparation or new capture ran. New captures remain **0/94**. Q16a708,
  Q16b120, original Q16c data and failed evidence remain preserved.

The completed-analysis manifest is19,637bytes, SHA256
`3bba1f5820a2a238f818f07234bd641aa18e252330ef93e08e51d6d739469b2a`.
The accepted86-prefix manifest is12,698bytes, SHA256
`5fcb47af34943777bb60ca9cf1900d22f609bfd3d20ae147119151cd9a135f3a`.
Both are retained here together with the86 reports and86 process receipts.
The prefix operator published ALL_86_VALID_PREFIX_MANIFEST_PUBLISHED and exited0.
These reports must be reused in a subsequent authorized continuation; do not
repeat their raw validation or their completed measurements.

Confirmed software failure: after accepting the86-prefix manifest and acquiring
the D286 guard, `stage17_q16c_continuation_study_v1.py` wrote
`continuation-window-1.json` with qualification_deadline_monotonic_ns,
started_monotonic_ns, global_deadline_ns and new_window. It omitted boot_id.
The actual source-bound `run_qualification_v31.Packet.__init__` immediately
requires anchor['boot_id'] to equal the finite release's boot. This raised
**KeyError('boot_id')** before the first qualification step. The traceback and
actual anchor are retained; the producer/consumer mismatch is confirmed by
source inspection. This was a qualification setup defect, not a measured Q15 or
Q16 capture failure. The earlier sequence tests substituted Packet and missed
this real metadata handoff.

Recovery is verified independently and by the supervisor, with errors=[]. The
platform guard restored compaction from requested0 to the actual prestate1.
Fresh readbacks at17:15:10UTC verify complete MSR values0000000000000000 on CPUs
0/1/8 match their recorded prestate. The dedicated native partition is absent;
no qualification-step log exists. The independent recovery signalled no native
or owner survivor. No retry, new window, deadline reset or production fix was
performed during this status check.

Remaining plan: repair and verify the qualification metadata handoff, then obtain
the explicit continuation decision required by D292's first-failure/no-retry
rule. Reuse the completed86 reports, qualify once, collect only94 pending
positions, restore, validate94 and compose180 under the applicable fresh bound
authority. Do not rerun the completed prefix. EXT007/Stage17 remain incomplete;
this record grants no EXT008–010 or Stage18 authority.
