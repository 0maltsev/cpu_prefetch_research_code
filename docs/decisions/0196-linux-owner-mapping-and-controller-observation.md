# ADR-0196: Prepare Linux owner mappings and gate phases on controller observations

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-196
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: EXT007 R0 diagnostic preparation and lifecycle engineering

Prepare new, private anonymous mappings on the actual owner worker. Require
explicit byte size, verified base-page size, requested CPU and requested NUMA
node. Compare page geometry to the running kernel before mapping. Apply
`MPOL_BIND` without migration flags and `MADV_NOHUGEPAGE` before first touch.
Request singleton affinity and independently observe affinity, current CPU,
thread identity and thread fault counters. Start byte-array lifetime without
initialization, force one owner write per page, lock the mapping, and repeat
owner observations. Reject invalid geometry, failed controls, wrong affinity,
CPU/thread changes and decreasing fault counters. Do not infer topology from
CPU numbers or select a CPU/node pair here. The native adapter supports one
native nodemask word and rejects larger node indices rather than truncating.
Pass word-bit count plus one as syscall `maxnode`: Linux's bitmap import
decrements this argument before copying/masking. A node-index-plus-one argument
would omit node zero/the highest requested bit. Test the actual native request,
including the bottom/top bits, rather than relying on injected bind acceptance.
See [Linux get_nodes/kernel_mbind](https://raw.githubusercontent.com/torvalds/linux/v6.16/mm/mempolicy.c)
and the [mbind interface](https://man7.org/linux/man-pages/man2/mbind.2.html).

Keep every attempted control and actual readback distinct from the requested
plan. Unattempted operations remain absent. Preparation is one-shot; failures
retain mappings and facts for managed publication/cleanup rather than retrying,
rebinding or replacing them. Optional read-only protection is one-shot and
cannot report readiness on failure. Explicit cleanup retains unlock and unmap
results separately, attempts unmap even if unlock failed, and never labels
failed cleanup as release. Destruction provides best-effort cleanup only when
explicit cleanup has not already been attempted. This class owns only its new
mapping; it must never prefault, erase or unmap borrowed/active stack pages.

Accepted binding/locking syscalls and owner observations are not proof of page
residency, huge-page readback or fault-free capture. Independent all-page
queries, smaps/control validation, owner stack preparation and complete live
provider construction remain required. CPU affinity in these preparation
workers is process-local; there is no global memory/CPU policy or MSR change.

Add an explicit controller observer to the persistent discovery session.
Observe before each release, during its fixed horizon using the actual released
origin/duration and read-only completion mask, and after both workers stop but
before validation/drain/reset. The live observer must use prospectively finite
schedules and preallocated retained scratch. Controller observations must not
read mutable worker rows during capture. No monitoring operation is inserted
into the measured worker attempt or queue algorithm.

A rejected or throwing pre-release observation cancels release. A failure
during capture requests phase stop while preserving the consumer's bounded
drain. The consumer waits for controller observations before validating and
draining. Failed warmup observations prohibit warm reset and measurement
release, including failures reported after both warmup deadlines. Failed
measurement observations prohibit session completion even when workers already
finished their horizons and independent raw integrity passes. Retain raw
integrity and controller validity as separate facts; complete physical streams
do not establish scientific validity. Exceptions remain distinct from explicit
rejections. No failed observation authorizes a retry, extension or top-up.

Keep the four-argument software-only session API compatible, explicitly marking
its observations `not_configured`; do not synthesize passing hardware checks.
Unreached hooks remain `not_started`. A qualified live action must explicitly
provide its observer and qualify its actual schedule, controls and boundaries.
This decision supplies no finite capture resource values, residency schedule,
execution admission or formal experiment design changes. D-178's approved study
and all immutable D-037 estimator rules remain unchanged.

Verify every preparation/control failure and cleanup boundary, requested versus
observed mismatches, one-shot lifetime, native Linux mapping and per-worker CPU
readback, and independence of page-residency checks. Verify controller ordering,
all rejection/exception boundaries, early and late failure, preserved bounded
drain/integrity, absent measurement after warmup failure, and explicit missing
monitoring status. Run both compilers, relevant sanitizers and existing release
checks. Local Linux checks establish software behavior only; no stand run or
hardware qualification follows from them.
