# D286: proposed locked-page compaction control after Q16c ordinal 86

Status: **PROPOSED scientific platform amendment; not execution authority.**
Amendment: `AMEND-2.0.0-pre.3-Q16C-LOCKED-COMPACTION-v1`.
Recorded 19 November 2026 Moscow (18 November UTC).

The owner's “fix it” authorizes diagnosis and software repair. It does not
override D282/D285's explicit stop-on-failure/no-automatic-retry rule or approve
a previously unspecified scientific platform state. The immutable protocol and
the actual stopped attempt remain unchanged.

The retained control artifact establishes that the very first warmup-before
residency probe returned syscall success but one page status `-ENOENT`; the
other 15,834 pages were on node 0. The page is inside the copied warmup schedule,
not overlapping another storage region. Both workers had prepared; neither
warmup nor measurement was released, and no environment/control sample ran.
The page error correctly failed the existing full-residency gate. The broad
`wrong_node` diagnostic is not proof of an observed page on the wrong node.

A bounded software diagnostic on the same stand/kernel reproduced `-ENOENT`
while explicitly migrating one private, prefaulted, mlocked, read-only page.
All contents remained intact; final query placed all 16,384 pages on node 0.
This proves that mlock does not make the query immune to migration. It does
**not** establish which kernel activity caused the historical ordinal-86 result.
Current stand settings allow locked-page compaction (`compact_unevictable_allowed=1`),
with proactive compaction 20. These are diagnosis-time observations, not invented
historical per-capture readbacks. The kernel documentation explains that this
sysctl allows compaction to move mlocked pages and that setting 0 prevents it.

Proposed scientific change, for future Q16c work only:

1. During the entire native family, request
   `/proc/sys/vm/compact_unevictable_allowed=0`. Keep every existing page query,
   expected-node requirement, observation deadline and failure gate unchanged.
   Do not accept, skip, retry or relabel negative page statuses.
2. Bind the guard source, exact boot, durable actual prestate, requested value
   and actual readbacks separately. Use one exclusive root-held lease. Verify
   the guard immediately before and after each capture outside the measured
   loop; attach those actual receipts to the capture's platform lineage.
3. The existing supervisor must stop, reap native children and restore on every
   error. Restore the exact observed prestate, verify it and durably publish
   restoration before clearing the lease. Add an independently bound systemd
   stop-post recovery entry for supervisor death. Stale leases block another
   acquisition; live holders and mismatched/foreign-boot receipts cannot be
   overridden. Do not enable this guard in an unsupervised research invocation.
4. Preserve all 86 native-complete captures, the failed capture and their
   original qualification/platform identities, as well as Q16a708/Q16b120.
   Assess the prefix once under its original validity rules. Record the new
   control regime explicitly; do not claim the old prefix was acquired under
   the new regime or combine regimes as identical platform evidence. Any reuse
   in a descriptive final matrix needs a separately reviewed continuation and
   explicit platform lineage. No homogeneous performance/inferential claim is
   created. Qualification reuse needs an explicit dependency assessment.
5. This proposal changes no count, rate, geometry, duration, seed, storage quota
   or existing time limit. It authorizes no measurement, qualification, prefix
   validation retry, new family, deadline extension or Stage18 action. D282's
   original absolute end remains 19 November 09:16:07 UTC. A separately prepared
   continuation must fit all remaining work, give its ETA and receive the
   required execution authorization. No completed measurement may be rerun.

Software implementation is deliberately an inactive guard component, not a
modified signed packet or experiment launcher:
`tools/stage17_locked_compaction_guard_v1.py`. Fourteen failure/recovery tests
pass locally and on the stand. A bounded stand-only control test verified
actual `1 -> 0 -> 1`, durable recovery and a successful independent stop-post
readback; no research process was invoked. The host is back at its original
value 1. This demonstrates control/restoration, not absence of every migration
source or success of a future Q16c run.

[Evidence, sources and limits](../evidence/stage17/Q16C-D286-MIGRATION-DIAGNOSIS-20261119-01/REPORT.md).
