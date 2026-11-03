# ADR-0202: Native diagnostic execution and retained custody

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-202
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: implement the separately approved D-178 study; no stand authority from this decision

Connect the mapped R0 runtime to a native controller using the accepted raw
clock, actual owner stacks/mappings, retained TLS/thread/hardware/page
observations and prospectively enumerated monitoring. Compute native layout
from the exact compiled types and reject any serialized size that differs.
Platform geometry, controller placement, buffers, offsets, disturbance limits,
namespaces and prestate are explicit inputs. A missing readback remains missing;
successful syscall requests do not substitute for physical residency evidence.

Expose a read-only layout description command on the same production runner.
It accepts explicit geometry, budgets, monitoring and hardware prestate, and
returns recomputed sizes plus source/binary identity; it returns no runnable
plan or authority. Execution still rejects every mismatched declared size.

Preopen each prospectively listed environmental file and freeze its path,
six output buffers and finite advancing-read budgets in controller monitoring
memory. Read all requested sources within the existing control observation
brackets, even after another source fails. Positive short reads advance the
offset; failures are not retried. A bounded EOF probe distinguishes a complete
snapshot from a truncated one. Retain original bytes, every read and close
outcome, and the non-atomic nature of these observations. Incomplete required
reads fail closed. Raw delivery does not itself establish physical page policy
or environmental acceptance: independent smaps/control validation remains
required, and pilot-frozen environmental limits are not invented in advance.

Publish only after workers have joined and while their mappings remain alive.
Retain warmup and measurement producer/consumer streams in the existing raw
codec. Store the four independent demand/issue vectors as contiguous unsigned
64-bit little-endian values with explicit names, offsets and counts. Preserve
partial event/drain records, raw control readbacks, timestamps, failures and
arena integrity observations. Missing phase owners have empty payloads and
explicit unavailable metadata. No missing observation becomes a zero.

Cleanup is observable: join, destroy the mapped typed provider, then attempt
every owner-map/stack release. Retain first cleanup outcomes without retry.
Serialize the returned native result after cleanup separately from the control
document published before cleanup. A publication or cleanup failure prevents
successful study completion. An outer process watchdog still owns recovery
when a worker cannot return, including hardware restoration and quiescence.

Keep `capture_discovery_worker` out of line so its real four owner/phase
instantiations remain identifiable in the native production binary. This is
one call per phase, outside the attempt loop and timestamp brackets. Qualify
the actual measured-loop call graph with both accepted disassemblers; do not
substitute an isolated look-alike probe or the six older gates for this check.

Add only `Q16A-DURATION-DISCOVERY` to the compiled action surface. It uses a
distinct v5 request/context/result and dispatcher flag. Existing six actions
keep their earlier contracts. The diagnostic authority binds a clean current
release, actual predecessor resolutions, full plan and exact source document
bytes. Preserve historical JSON bytes, including their original newline
convention, rather than rehashing a reserialized document under an old identity.
Reuse signed authorization, sealed descriptors, exclusive attempt creation,
pinned output custody, process-group supervision and failure retention.
The compiled diagnostic worker independently checks the current UTC validity
window immediately before execution, including synthetic transport tests.

Derive finite per-capture and session deadlines from the approved plan; the
36 warmup/measurement intervals alone total 253.2 seconds. The controller,
executor and native boundary must agree. A shorter ordinary action cap cannot
authorize the study. Prepare finite process memory-lock limits under the actual
execution identity and retain their readbacks; no global unlimited limit is
required. Bound publication and metadata bytes before writing them.

The native action retains count sufficiency separately from mandatory validity.
Completed horizons with fewer than 100,000 observations in any required
sequence are insufficient and remain retained. Mandatory failures stop the
study, retain partial evidence and require restoration or quarantine. No retry,
top-up, extension or replacement is introduced. The full artifact-retention
report explicitly says `NOT_ASSESSED` and cannot itself select a duration or
contribute formal runs. Independent raw/control validation must precede the
existing D-178 count-only selection rule.

The independent validator streams primary records and demand vectors, joins by
run identity and accepted ordinal, replays the frozen Philox/HMAC arena and
checks checksums, actual control observations, page policy and final cleanup.
Large JSON drain arrays use bounded temporary spooling. A measurement attempt
admitted before the horizon can finish afterward; its consumer invocation is
not a second admission test. Likewise a peer-stopped worker can finish its last
in-flight action after its last admission-clock read. Preserve those valid
events and exclude drain from the four demand/advancing-issue sequences.
A software C++ session/backend publishes the actual seven files into Python
validation, including both boundary cases, without claiming native hardware
control evidence. Full native control validation remains a stand gate.

A measurement trace-capacity stop is also retained as insufficient and cannot
qualify a duration. It may continue the prescribed campaign only after verified
warmup, reset, reconciliation, all mandatory observations, drain and cleanup.
Warmup failure or any mandatory control/cleanup failure remains a study stop.
This preserves D-178's distinction; it does not authorize extending a capture.

The release successor binds the complete Python import closure, source/header
closure, schemas, profiles and worker identities. It preserves historical
verification paths while admitting the exact seventh action in new artifacts.
Actual stand qualification, phase-bound authority, current resources/custody and
successful scientific validation remain required. This implementation decision
does not declare Stage 17 complete or admit Stage 18.

The aggregate qualification-schema target runs its two policy-18 regressions
through D-185's existing frozen-source fixture, matching CTest. Directly mixing
those historical policy hashes with current schemas reproduces the already
recorded binding failure. Preserved historical bytes remain checked. Current
policy-55 closure and source bindings are independently verified before the new
release; a historical fixture pass does not qualify current operational use.

Verification is retained in
[`native-diagnostic-checks.json`](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261103-01/native-diagnostic-checks.json).
Both full development suites pass 631/631; supported sanitizer, independent
validator, compiled publisher/dispatcher and actual-worker codegen evidence are
separately identified there. These are software results, not a qualified stand
release, experimental captures, duration selection or EXT-007 completion.
