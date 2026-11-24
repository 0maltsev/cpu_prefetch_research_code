The D282 campaign is **STOPPED AND RESTORED**. No restart, new window,
qualification repeat or Q16c capture was performed during this status check.

Actual corrected-release qualification succeeded. Q15-R completed at09:28:01UTC
(12:28Moscow), terminal Q15_R_READ_ONLY_COMPLETE. Q15-W completed at09:35:06UTC
(12:35Moscow), terminal Q15_W_RESTORED_COMPLETE, restoration_verified=true,
quarantined=false. The one persistent supervisor exited0 and was reaped. Both
clock passes remain preserved in the preceding qualification report.

Q16c failed during construction of administrative inputs, before signing,
registration, native collection or analysis. The actual trace ends at
`tools/stage17_q16c_empty_reuse_v1.py:153`: discovered Python dependency closures
are sets, but `admission.same` canonicalizes its arguments as JSON and rejects
sets. The raised error is `TypeError: unsupported JSON value: <class 'set'>`.
Construction exited1 after about48.35s; original isolation restoration was
verified at09:39:45UTC (12:39Moscow). The failed study remains retained.

This is a confirmed administrative implementation defect. The native repair,
qualification checks and measurement results are not implicated by this trace.
A pure local reproduction using the actual comparison helper rejects even
identical sets. Inspection also found the same API misuse at line158, where
source-file bytes are passed to this JSON-only helper. A second pure reproduction
confirms identical bytes also raise TypeError. The byte comparison was not reached
on the stand; it is an additional confirmed software defect on the same path.
No production source or tests were changed during this read-only investigation.

The earlier tests covered empty-attempt eligibility, plan invariance, window
budgets, module/CLI composition, handoff and namespaces. They did not execute
`inspect(..., validation=current_qualification)` across both qualified producer
and consumer contexts, so the source-closure branch was unverified. The prior
packet import and original-context precheck did not establish that branch works.
Before another launch, repair the local comparison calls while retaining exact
set membership and per-file byte checks; exercise this entire branch with both
matching and mismatching qualified closures. Passing import/plan tests alone is
insufficient. Execution remains subject to the existing stop/no-retry decision;
this report grants no restart or qualification-reuse authority.

Live read-only verification at 2026-11-18T10:37:31.329827+00:00:

- All three owned services have MainPID0; qualification result=success,
  study result=exit-code, isolation keeper inactive.
- Reserved cgroup absent; root effective CPUs0-31 and isolated CPU list empty.
- Partition restoration verified, no reported errors.
- New Q16c authority directory and family working directory absent.
- Q16c0/180: zero checkpoints, successful captures or archives for this family.
- Original program ledger unchanged at66472, SHA256
  25a3d0aee5a175eb2a0a8d49a6d8c564716ce3d17f0240c98eed4540ec16280d.
- Original Q16a708/Q16b120 and previous empty failed evidence remain preserved.

The old17h27m completion forecast is withdrawn because the campaign stopped.
D282's signed absolute deadline remains19November09:16UTC/12:16Moscow; it was
not reset or extended. EXT007/Stage17 remain incomplete; Stage18 remains blocked.
Only reports and metadata were copied to the PC; scientific raw remains on stand.
