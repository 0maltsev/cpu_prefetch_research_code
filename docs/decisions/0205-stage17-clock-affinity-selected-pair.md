# ADR-0205: Use the selected pair for clock qualification affinity

- Status: `IMPLEMENTED_VERIFIED_LOCAL_NO_EXECUTION_AUTHORITY`
- Decision ID: D-205
- Scope: required EXT007 far-pair clock qualification compatibility
- Scientific rules: unchanged D009 and ADR0173 pair identities

The owner-approved finite isolated requalification ran on 2026-11-03.
The near pair passed; the far invocation stopped with
`producer_pinned=1 consumer_pinned=0 complete=0`. The operator stopped the
family and verified restoration. Both captures and the failure remain
retained; this decision grants no additional measurement attempt.

The exact qualified clock tool selects the accepted V5 pair 0/8 through
its registered CPUID mapping. Its clock collector then calls
`LinuxQ15PlatformOperations`, whose fixed legacy affinity guard allows only
0/1/26. That guard rejects CPU 8 before `sched_setaffinity`. The retained
before/after cgroup readbacks include CPU 8, and disassembly of the exact
capture binary independently confirms the legacy guard. This is an
implementation incompatibility, not a measured far-pair clock-tail failure.

Use the existing `LinuxOwnerMemoryOperations` affinity mechanism in the
clock collector's per-core and cross-core phases. It binds the explicitly
requested CPU and reads actual affinity and CPU identity without importing
the unrelated legacy Q15 probe domain. Preserve the clock collector's
singleton-mask and actual-CPU predicates before and after per-core capture.
The shared observation also reads thread ID and faults outside the clock
sequence; those fields do not introduce new clock acceptance criteria.

The public clock CLI's registered-family/model and selected-pair gates
remain unchanged. The collector remains a mechanism whose caller supplies
the authorized pair, as its existing API documents. Do not widen the
legacy Q15 probe's CPU whitelist, alter its NUMA rules, infer topology from
CPU numbering, add a fallback pair, or change any clock source, timestamp
boundary, repetition count, quantile rule or threshold.

The regression must reproduce CPU 8 rejection before the fix, then exercise
both capture phases at reduced test scale on local CPUs 0/8. It must verify
pinning/readback, clock read status, no regressions, cross-core completion,
and rejection as real qualification because the accepted production counts
are not met. Keep the near-pair and out-of-range failure cases. Run affected
compiler and sanitizer checks; local results are software evidence only.

No policy-pinned header or operational runtime changes. Preserve policy 56,
profile 24 and all deployed bytes if their actual authoring/verification
checks confirm compatibility. Issue a new clean source/archive identity
and rerun required release gates. The earlier source `817c652` and its
qualification evidence cannot be relabeled as the repaired release.
A new prospective capture authority is required before measuring again.

Verification: the new CPU 0/8 regression failed before the production edit
at `consumer_pinned=false`. All three clock integration cases then passed
under GCC/libstdc++, Clang/libc++, and both compilers' ASan/UBSan and TSan
configurations. Formatting and targeted static analysis passed. The actual
policy-56 and preflight-policy-30 authoring checks pass with preserved bytes.
The production clock tool's self-test passed without reading a clock,
pinning a thread or touching hardware. See the
[local verification evidence](../evidence/stage17/LOCAL-VERIFICATION-EXT007-D205-20261103-01/README.md).

Package freshness requires explicitly building the clock qualification and
qualification-envelope executable targets before `pilot-candidate-bundle`:
the package copies those tools but its target prerequisites omit them.
Retain their clean compile/link evidence and inspect the actual packaged
clock executable's binding path under both disassemblers. Do not treat a
new archive's existence as proof that its clock executable was rebuilt.
