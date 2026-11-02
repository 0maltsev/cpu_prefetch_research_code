# ADR-0200: Caller-owned controller storage and actual thread TLS observations

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-200
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: continue the explicit EXT007 runtime footprint; no execution authority

Move the persistent session's shared barriers, stop/completion flags and retained
result into caller-owned `DiscoverySessionStorage`. The caller constructs it
once in prepared, declared memory and keeps it alive through worker join and
result inspection. An atomic claim rejects reuse without modifying the original
result, including reuse after an invalid plan. Retain the existing convenience
overload for software callers; automatic storage is not a live footprint
declaration. Capture ordering, drain, reconciliation, clocks and scientific
controls are unchanged.

Exercise the complete existing R0 session from an explicitly mapped controller
stack. Construct the provider, backend, clock and shared storage in a separate
controller-owned mapping, with both existing persistent mapped worker stacks.
Keep controller invocation frames, closures and launcher objects within that
stack's declared lifetime. Destroy the typed objects after joins and before
mapping release. Test containment using actual frame and object addresses,
retained results and exact independent primary joins. Native mapping/affinity/
guard/prefault operations are exercised; NUMA binding is injected and clocks
are synthetic. This is software integration evidence, not stand qualification.

Add a cold owner-thread TLS observation using the actual Linux thread ID,
`ARCH_GET_FS` readback and `dl_iterate_phdr` data. Retain each TLS module's ELF
image base, module ID, owner-specific payload address and `PT_TLS` extent, plus
loader generation counters, visited-object count, syscall statuses and iterator
return. Check the callback ABI size before accessing its TLS fields. Null payload
addresses remain explicit unallocated observations; do not force allocation or
substitute another thread's TLS address. Caller-provided finite output retains
its prefix on exhaustion and cannot report complete. Identity, ABI, malformed
module and generation failures remain distinct. No page policy is changed.

Compare only complete retained snapshots from the same owner, FS base, loader
generation and module inventory. Truncated or mismatched snapshots reject.
This comparison is not proof against all intervening changes. Loader iteration
belongs outside all measured intervals: it may acquire loader locks. TLS module
payloads and an FS base are also not a complete libc thread control block,
dynamic thread vector, allocator or process-memory inventory. Full coverage
and actual placement remain requirements of the final runtime admission.

The native tests identify actual executable TLS and libc `errno` on both the
calling thread and an actual mapped worker, reject short storage, and compare
owner/generation/address facts. They make no hard-coded TLS offset, libc object
size, physical placement or NUMA inference. Sanitizer behavior is software
verification; it does not qualify the uninstrumented stand footprint.

The owner's latest answers dedicate the stand to these experiments and provide
no additional deadline/storage cap. Continue deriving finite budgets from real
resources. The answer “anything” supplies no positive, justified primary
`delta_star`; retain that final precision input unresolved without blocking
independent engineering or the already-approved duration discovery. Neither
this engineering decision nor the answer changes the immutable design or
turns the sensitivity-only `log(1.05)` into the primary threshold.

Remaining work includes full native runtime/control coverage, monitoring and
publication/watchdog integration, source-bound exact-worker qualification and
finite diagnostic admission. The 36 diagnostic captures, 708 fresh formal Q16a
captures, Q16b/Q16c, EXT008–010, pilot and final freeze/exit have not executed.

Native interface references:

- [Linux `dl_iterate_phdr` contract](https://man7.org/linux/man-pages/man3/dl_iterate_phdr.3.html)
- [Linux `ARCH_GET_FS` readback](https://man7.org/linux/man-pages/man2/arch_prctl.2.html)
