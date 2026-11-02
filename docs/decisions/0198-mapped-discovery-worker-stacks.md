# ADR-0198: Mapped discovery worker stacks and preparation admission

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-198
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: Linux x86-64 discovery runtime preparation, not run authority

The D-183 session previously created ordinary `std::thread` stacks. Setting
affinity inside a worker cannot establish placement of pages already touched
by pthread startup. D-196's new-mapping zero-write prefault cannot be applied
to a live stack because it would overwrite active frames.

Use an explicit prospective stack-body size, verified base-page size, owner
CPU and requested node. The creator reserves an anonymous private mapping
with an additional low guard page, applies nonmigrating MPOL_BIND and
MADV_NOHUGEPAGE, then protects the guard with PROT_NONE. Reject invalid or
overflowing geometry and compare actual sysconf page/minimum-stack values.
Set pthread stack and singleton affinity attributes before creating the
thread. The library guard size is zero because the mapping supplies the guard.
The body excludes that guard and is the declared residency target.

Libc may write startup/TLS metadata from the creator before worker execution.
Record that limitation; do not claim worker first touch for those bytes.
The binding request precedes those writes. On the actual worker, independently
observe singleton affinity, actual CPU, thread ID and fault counters, use
MADV_POPULATE_WRITE to populate writable translations without overwriting
live bytes, lock the body and repeat owner observations. Unsupported or
failed operations stop preparation; no zeroing, migration or alternate
prefault fallback is permitted. A failed populate may have populated a
prefix; retain failure without claiming untouched or completely populated
memory. Independent D-192/D-197 page queries and smaps checks remain mandatory.

The session accepts an explicit thread launcher. Its owner-preparation gate
precedes backend preparation and the warmup start barrier. Reject stack
preparation failure, cancel the peer, and retain zero phase attempts when
no origin was released. Partial launch failure cancels and joins already
created workers. Keep the same stacks/threads throughout warmup, drain/reset
and measurement. Legacy software-only sessions retain their standard launcher;
it supplies no hardware placement evidence.

Thread objects, callback context and stack mappings remain alive through
join. The native callback does not allocate a hidden C++ callable. Cold
pthread internals can allocate and are outside measurement. Record pthread
return codes directly, separately from syscall return/errno. Even if
attribute cleanup fails after successful creation, retain/join the actual
thread and reject launch admission. Do not unmap an unjoined stack. Join
failure terminates rather than returning into destroyed worker context.
After join, explicit release retains unlock/unmap results. Preparation,
launch and cleanup are one-shot; no detached workers or retries.

Read evidence only before launch or after join; each worker writes its own
owner observations. The calling worker can inspect its prepared state.
This decision selects no numeric stack size or monitor schedule, establishes
no NUMA residency, and does not place the session's shared controller context,
other TLS allocations or remaining runtime objects. Include those in the
complete footprint/admission work before qualified execution.

Verify real native pthread stack/affinity observations, guard permissions,
live-frame preservation, control failure propagation, premature release
rejection, partial launch cancellation and both persistent phases. Test-only
mbind injection is explicitly software evidence, never stand placement.
Run relevant compiler/sanitizer checks and strict static/format validation.

Primary references:

- [madvise(2), MADV_POPULATE_WRITE](https://man7.org/linux/man-pages/man2/madvise.2.html)
  documents writable prefault without actual writes and possible partial
  population on error.
- [pthread_attr_setstack(3)](https://man7.org/linux/man-pages/man3/pthread_attr_setstack.3.html)
  defines caller-provided stack geometry and caller responsibility for guards.
- [pthread_attr_setaffinity_np(3)](https://man7.org/linux/man-pages/man3/pthread_attr_setaffinity_np.3.html)
  defines affinity inherited through creation attributes and direct error codes.
