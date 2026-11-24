# ADR-0216: Shared cold native observation storage

- Status: ACCEPTED — engineering refactor authorized by the owner on 2026-11-03
- Scope: identical cold native monitor layout, construction and destruction helpers
- Scientific method change: none
- Execution authority: none

Formal Q16a must use its accepted persistent warmup, producer-stop and continuous
consumer-drain lifecycle. Reusing the diagnostic discovery lifecycle would change
that behavior. D210 service and later scheduled service integrations also need the
same native owner mappings, stacks, TLS facts, finite monitoring buffers, observed
hardware controls, raw environmental snapshots and publication lifetime.

Extract the unchanged native monitor object, scratch layout, checked monitor
arena sizing and prepared environmental-file construction into a shared detail
header. Preserve member order and types, alignments, six-group allocation order,
file path copies, per-read retained scratch, destructor order and all failure
results. The diagnostic public API, mapping-size calculation, session choice,
publication view and dispatch remain unchanged. Its measured worker loops are
outside this extraction.

Formal native integration may reuse these cold helpers and existing platform
primitives with a statically typed capture/lifecycle policy. It must not select
packages dynamically in the hot path, substitute diagnostic endpoints, infer
scientific validity from raw delivery, or omit unsuccessful current captures.
The formal native owner runtime uses the caller-owned termination lines from
D215; this does not modify diagnostic runtime storage.

Characterization retains the existing native/mapped discovery test results and
both-disassembler discovery generated-code gate before extraction, followed by
fresh affected checks after extraction. Formal integration requires its own
failure, bounds, lifetime and sanitizer verification. The existing qualified
stand archive remains immutable. No partial R0-only formal release may be
qualified or executed as the eventual complete Q16a/Q16b/Q16c implementation.

The formal owner runtime binds its preparation, backend, session storage and
result types through a compile-time policy. Q16b retains D210 service bounds and
D211 completion counting. Q16c binds the D219 scheduled lifecycle and disables
that service-rate counter; it does not extend arrivals to the schedule horizon.
Both use the same five package types and accepted model-specific software
prefetch emitter registry. The native prepared MSR reader checks actual CPUID
before worker startup; a requested model alone is not observed hardware evidence.

Q16c's explicit source arrays remain borrowed cold inputs until capture returns.
The producer owner copies both arrays into disjoint, checked, cache-line-aligned
slots in the records mapping before read-only protection and worker release.
Only those mapped arrays reach the scheduled driver. The layout includes their
exact counts and offsets; all arithmetic is checked before mapping. Publication
may expose prepared arrays after a failed capture, so lifecycle evidence must
separately establish which phase actually ran. This changes no schedule bytes,
clock coordinates, event arena order or package permutation at the warmup reset.
Q16a and Q16b allocate no schedule rows. Their cold control-object sizes remain
prospectively described by their native layout functions, not fixed historical
constants. All formal paths still publish after joining and before explicit map
release, then retain each actual cleanup outcome in the returned result.
