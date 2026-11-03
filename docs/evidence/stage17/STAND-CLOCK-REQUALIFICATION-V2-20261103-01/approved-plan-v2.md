# V5 repaired-release clock qualification — finite plan v2

Status: **OWNER_APPROVED_FINITE_PLAN — PREREQUISITES VERIFIED**.

The owner approved this exact v2 plan in the conversation on 2026-11-03:
“Yes, approve plan v2”. Approval preceded any v2 isolation mutation or
capture. Fresh v5-19 journal 000006 admits EXT001/002/003/006 and records
PREFLIGHT_ACCEPTED with two transitions; all six preflight observations pass.

The first approved family is finished: near passed, far stopped because
the legacy affinity helper rejected CPU 8, and the stand was restored.
Its two invocations remain consumed. [D205](decisions/0205-stage17-clock-affinity-selected-pair.md)
repairs that implementation defect without changing the CLI's accepted
CPU pairs, clock source, counts or limits. This plan proposes one new finite
family against the repaired release; it does not repeat or relabel an old
capture.

## Exact release

- Clean source: `ac64633662c4e61c8dd98e332dc70f77085e2e48`.
- Archive: `cpu-prefetch-pilot-candidate-2.0.0-ac64633-clean-91a93014b4eb.tar.gz`.
- Archive SHA-256: `428b69b160429bca9c6ba0690e1136e4c2e131d6a1ba7d53377c69fc088ef5e7`.
- Clock executable SHA-256: `1e6bde398d7188e97c05b2293a596c64612b39f54a0c81aec430faa152f784ba`.
- Stand evidence namespace: `/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19`.
- New capture directory: `clock-requalification-2`, created exclusively.
- New partition: `/sys/fs/cgroup/cpu-prefetch-v5-clock-qualified-2`.

Both compiler test configurations and all four sanitizer configurations
pass the focused regression. The seven clean release code-generation gates
pass. Local and stand package checks verify 1,826 files; release admission
also passes. Both GNU and LLVM disassembly show three calls to the generic
owner affinity binder, two actual-thread observations, and no call to the
legacy Q15 affinity binder in this exact clock executable. The archived
source equals the repaired source; the CLI pair-selection bytes are unchanged.

## Execution and stop rules

1. Complete the fresh release/preflight prerequisites. Confirm unchanged
   boot and topology and the recorded restored cgroup prestate. Any drift
   stops before mutation; do not substitute another setup.
2. Reapply only the same verified no-reboot isolation configuration: reserve
   CPUs 0/1/2/8/16/17/18/24, memory nodes 0/1, valid isolated partition,
   and exact effective/exclusive readbacks. Ordinary preparation remains
   outside the reserved set and stops during each capture. Do not alter
   governor, turbo, IRQ routing, boot options or clock source.
3. Freeze the script, exact commands, control readbacks and limits before
   collection. The supervisor stays on CPU 3; each UID/GID-1000 launcher
   enters the partition and starts on CPU 2 before native worker pinning.
   Use an 8 GiB address-space limit and preserve the observed 8 MiB memlock
   limit, verifying both. Apply a 600-second timeout per invocation.
4. Run **near 0/1 once**, then **far 0/8 once only if near passes**. Use
   100,000 prime reads and 10,000,000 deltas per CPU, three windows of
   100,000 exchanges per direction and the prescribed window span. Keep
   p99.9 <= 1 us and p99.999 <= 10 us, and every other accepted gate.
   Maximum two invocations; stop at the first failure. No diagnostic count
   overrides, outlier removal, best-attempt selection, CPU substitution or
   repeated capture is permitted.
5. Retain outputs, missing-output facts, actual exits, control and restoration
   evidence in verified uncompressed stand/PC copies. On failure, restore
   and independently verify the recorded prestate and remain blocked.
6. If both pass, bind the retained isolation configuration to subsequent
   qualification and the prospective EXT007 discovery environment. Do not
   apply isolated-clock evidence to an unisolated experiment. Obtain fresh
   signed Q15 action records as already authorized, and restore the stand
   when the work stops or completes. This plan itself does not authorize
   pilot, confirmation, Stage 18 or extra discovery captures.

Approval is required because the previous exact-binary, two-invocation plan
is consumed. Approval accepts this bounded new family, not a guarantee of
clock success or a waiver of any acceptance gate.
