# Prospective V5 clock requalification proposal

Status: **OWNER_APPROVED_FINITE_PLAN — IMPLEMENTATION CHECKS REQUIRED**.

The owner approved this exact plan in the conversation on 2026-11-03:
“yes, I approve the requalification plan”. Approval was recorded before
any isolation mutation or fresh qualification capture. It authorizes the
finite work below; it does not waive a feasibility, validity or stop gate.

The retained 2026-11-03 capture failed the unchanged D009 p99.999 limit on
both CPUs. [Evidence and exact results](evidence/stage17/STAND-QUALIFICATION-EXT007-20261103-01/README.md)
remain valid failed qualification data. The cause is not established.
This proposal is only a prerequisite to the existing EXT007 task.

## Proposed finite scope

1. Preserve the failed capture and all earlier qualification records.
2. Prepare and independently check a reversible, no-reboot cgroup-v2 CPU
   isolation configuration for this stand. Reserve CPUs 0, 1, 2 and 8 plus
   their observed siblings 16, 17, 18 and 24, covering both accepted worker
   pairs and the existing controller CPU. Verify topology, cgroup support,
   current memberships and parent/child constraints before any mutation.
   Snapshot every changed setting. Do not change governor, turbo, IRQ
   routing, kernel boot options, clock source or production binaries.
3. Freeze the exact applied settings, independent readbacks, rollback
   sequence, launcher, process limits and complete command hashes before
   capture. Unsupported isolation, unexpected memberships or failed
   readback stops preparation and requires restoration; it does not permit
   an alternative configuration. Keep ordinary preparation, hashing and
   admission work off the reserved CPUs. Run no such work concurrently with
   either clock capture.
4. Under that one fixed configuration, perform at most one fresh near-pair
   qualification (CPUs 0/1), followed only on success by at most one far-pair
   qualification (CPUs 0/8). Use the unchanged release `817c652` tool and
   accepted clock/counts/limits: 100,000 prime reads and 10,000,000 deltas
   per CPU; three windows of 100,000 exchanges per direction over the
   prescribed span; p99.9 <= 1 us and p99.999 <= 10 us. Apply a prospective
   600-second timeout to each invocation, with new identities and exclusive
   output paths. Maximum two invocations; stop at the first failure.
5. Retain complete available outputs, actual exit status, environment and
   before/after control evidence in verified stand and PC copies. Do not
   discard outliers, select the best attempt, loosen a threshold, change
   counts, substitute CPUs, or repeat a failed capture.
6. On any failure, restore and verify the recorded prestate and remain
   blocked. On success, keep the explicitly verified configuration bound
   to subsequent qualification and the prospective discovery environment;
   do not apply isolated-clock evidence to an unisolated experiment. Renew
   expired Q15 authority with fresh records before proceeding. Restore the
   stand's recorded prestate when this work stops or completes.

## Decision boundary

Approval accepts this finite remediation/requalification design, not a
claim that interference caused the failed tails or that isolation will
produce a pass. Exact cgroup feasibility, safe rollback and source-specific
integration still require engineering verification before capture. A
failure at those checks leaves the affected work blocked.

D009 says a failed qualification rejects the build/platform/pair before
measurement; ADR0150 specifies qualification once per selected pair. The
existing failed capture cannot be relabeled or silently repeated under
those records. This explicit prospective decision is required before a
new capture under a changed stand configuration. Clock policy and its
scientific acceptance thresholds remain unchanged.

## Execution result

Executed 2026-11-03. The near pair passed; the far invocation failed on a
software affinity guard before completing collection. Both permitted
invocations are consumed. The operator restored the exact stand prestate,
confirmed by an independent read-only check. See the
[retained result](evidence/stage17/STAND-CLOCK-REQUALIFICATION-20261103-01/README.md).
This completed approval does not authorize another capture after D-205.
