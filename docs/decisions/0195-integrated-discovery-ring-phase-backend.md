# ADR-0195: Integrate real event streams and observed drain in discovery phases

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-195
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: the R0 diagnostic phase backend, not an execution authorization

Compose the existing demand/event capture, caller-owned primary streams and
persistent warmup/reset session around a real immutable arena and ring. The
preparation provider owns mapped storage, actual worker placement, object
construction and bounded readiness/cancellation. Keep producer logical and
accepted ordinals and consumer consumed ordinals in separate owner states.
Forward the worker's already-observed pre-attempt tick to continuously-ready
producer capture as its arrival observation; preserve legacy no-argument
callbacks. No arrival timestamp or successful clock status is synthesized.
Keep candidate attempt/consumed identities even when a complete primary row
cannot be formed, distinguishing supplied candidates from actual accepted or
consumed events. Read the first handling/invocation clock before clearing
current-row bookkeeping so that bookkeeping cannot precede that boundary.

Read prepared, quiescent primary snapshots without allocating or changing the
raw codec. This reader is not external artifact admission: the existing
hash/envelope/semantic decoder remains required after publication. Validate
row geometry, literal run IDs, canonical flags/absence, ordered logical and
consumed ordinals, deterministic record mapping and timestamp order. Join the
consumer prefix to producer-accepted rows by run identity and accepted ordinal;
repeat record indices are validation fields. Independently replay the ordinary
checksum from the immutable producer sequence and compare the consumer state.
After drain require the full accepted sequence, exact counts and empty audit.

Drain through real consumer event capture so its ordinary boundary clocks and
record action are retained. Preserve actual operations and counts after failure,
including a failure after dequeue; pre-operation failures count no queue call.
Retain partial capture/drain facts in caller-owned storage. Never renumber a
real consumed ordinal to hide a missing primary row. Keep complete primary
prefixes separate from forensic partial/drain evidence on invalid phases.
An exact final join must pass before any warmup reset. Failure retains state
without repair, reallocation, retry, top-up, or extension.

Keep warmup and measurement mappings, owner threads and immutable arenas
persistent. Prepare every buffer once, retain separate phase identities/raw
evidence, and verify the untouched measurement state before release. FULL is
retained correct data when counts/sequence reconcile, separate from zero loss.
Trace exhaustion is incomplete horizon evidence, not authority to grow it.

Verify the real arena/ring/primary-stream session, independent repeated-index
joins, accepted/FULL/empty and drain paths, malformed/timestamp/ordinal/checksum
failures, no reset on failed final integrity, partial evidence after clock or
storage failure, and no allocations in capture/drain/join/reset. Run relevant
sanitizers and release checks. Actual Linux preparation/monitoring, durable
publication, finite outer watchdog, versioned diagnostic admission and complete
source/exact-boundary qualification remain separate prerequisites.
