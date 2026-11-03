# ADR-0201: Live discovery controls and explicit phase identities

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-201
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: D-178 diagnostic runtime integration; no execution authority

Compose the existing owner-mapped R0 preparation, persistent mapped worker
stacks, capture/drain/reset backend and caller-owned session coordination in
one runtime. Retain actual owner TLS observations before warmup and before
measurement; reject an incomplete or changed inventory. The caller must place
the runtime, clock and TLS output in declared prepared controller storage and
invoke it on the declared controller stack. This composition does not itself
qualify placement, publish evidence or authorize an experiment.

Keep **both** workers alive through the final measurement control observations.
Previously the producer could return immediately after setting its completion
bit, while the controller had not yet read its final thread state. A delayed
native thread read reproduced that failure. Both owners now wait for completion
of the final observation hook before exiting; the consumer then performs the
existing validation/drain. The measured horizon, capture counts and drain
semantics do not change. Fatal cancellation retains the existing bounded path.

Prepare native thread monitoring outside the measured intervals. Open and retain
the actual worker task's procfs directory/stat/status descriptors while the
worker is alive. Each controller sample brackets status and affinity with stat
reads and retains identity/start time, last CPU, affinity mask, faults, context
switches and raw read results. A sample uses a fixed finite syscall count with
no allocation, opens, retries or buffer growth. File truncation, malformed data,
exited tasks and changed identities fail explicitly. These non-atomic samples
are observations, not proof of continuous CPU residency.

Prepare hardware-prefetch readback using the existing accepted model mapping,
actual controller CPUID and admitted prestate. Resolve H0/H1 expectations through
the existing resolver, then open only its registered control CPUs read-only.
One read per CPU retains partial bytes, errors and observed whole-register
values. Compare the complete expected value, preserving unrelated prestate
bits; do not invent an offset, mask or CPU set. Readback does not perform writes
or replace the outer authorized whole-plot transaction/restoration mechanism.

Attach exactly one explicit thread/hardware control group to each of the six
warmup/measurement before/during/after residency groups. Use the same prospective
request and timing bracket, so control syscall time counts toward the during
window. Retain independent page-query evidence even when control checks reject.
Reject missing mandatory groups, reused output, overlapping retained scratch,
wrong owner/CPU/affinity, identity changes, counter regressions and hardware
mismatches. Limits are explicit per phase and owner; an absent disturbance
limit is unenforced, not a zero threshold or an observed zero. Final freeze
rules remain separate. The native factory must keep monitor storage disjoint
from worker targets and residency-query storage.

Make the prospective D-178 plan bind all 36 ordered captures, exact five-second
bootstrap warmup, actual declared geometry, phase identities/namespaces, four
100,000-observation minima, release/stand/qualification/predecessor references,
monitoring/resource/namespace records and finite per-capture/session/custody
budgets. Checked integer arithmetic rejects overflow and budgets shorter than
the declared stages. The study needs at least 253.2 seconds for warmup and
measurement alone. A declaration or schema match is not verification of the
referenced files or platform and grants no authority.

Record the seed mapping explicitly: the existing D-195/D-199 continuous-ready
R0 algorithm initializes **one immutable arena/order** and preserves it across
warmup and measurement. The plan names that actual arena seed input. Separate
warmup identity and dedicated namespace/seed references remain retained; this
diagnostic algorithm draws no independent warmup arrival schedule and performs
no random draws from the reserved warmup seed. This is an implementation
interpretation for this diagnostic algorithm, not a claim that pre.3 expressly
specifies an unused seed or permission to change scheduled pilot/Stage A
warmup behavior. Do not silently generate a second arena or reseed it at reset.

The Stage 17 completion roadmap now follows D-115's operational exit validator:
the ten resolutions/three transitions, matching admitted pilot lineage, every
planned run, sealed artifacts, restoration and process quiescence. Final
scientific freezes, including application-justified `delta_star`, remain
separate Stage 18 readiness requirements. Their absence does not block the
approved Stage 17 diagnostic/calibration/pilot sequence once its own gates pass.

Validation covers the delayed final-thread-read failure and fix, mapped-runtime
composition, native thread parsing/descriptor/read failures, exact mapped MSR
readback, control scheduling/identity/disturbance failures and prospective-plan
mutants. Local injected/synthetic tests make no empirical performance claim.
The new native dispatcher, publication/recovery integration, complete source
release and exact-worker qualification remain prerequisites to stand execution.
