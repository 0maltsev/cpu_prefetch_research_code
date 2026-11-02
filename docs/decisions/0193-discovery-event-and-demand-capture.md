# ADR-0193: Retain event boundaries alongside discovery demand brackets

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-193
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: event capture for the integrated diagnostic ring backend

The demand-only helpers retain the exact slot acquire brackets but cannot
produce the ordinary producer/consumer event-boundary observations. Add
diagnostic capture helpers that retain both around one real queue operation.
Expose the existing ring implementation's demand and publication/observation
observers together; retain its exact acquire/release mapping and member layout.
The old ordinary and formal helpers remain unchanged.

Use the existing event-boundary definitions and primary observation types.
Retain all actual partial clock readings separately from a complete primary
row. Never fill an unobserved clock with a successful status or fabricated
timestamp. Emit a complete primary row only when its required boundaries and
record action succeeded. A valid primary row is retained even if demand-trace
retention failed. Actual FULL and empty results remain independent facts.

Once a diagnostic queue call has started, its boundary clock observer records
failure without vetoing the ordinary queue operation. After an actual dequeue,
perform the ordinary record/checksum action exactly once even when a clock or
trace failed. Preserve its actual status and the queue result independently;
the run still fails and must drain/reconcile. Introduce an explicit record
failure outcome rather than calling corruption a clock or storage failure.

Distinguish failures before any queue call from failures after an operation.
The bounded worker must not count an attempt or advance for a pre-operation
failure, nor claim that demand clocks were read. Retain the actual failed
clock and boundary. Existing demand-only helpers default to their already
performed-operation contract.
Demand clock statuses are optional facts: absent means unobserved, while a
present failure status records an actual failed read. Guard every optional
boundary before dereferencing it, including the event observers' callbacks.

The backend owns persistent caller-placed current-row storage, immutable arena,
independent logical/accepted/consumed ordinals, preallocated primary streams,
and durable partial-failure publication. It must subsequently integrate these
helpers with the fixed warmup/drain/reset session, placement verification,
finite watchdog and admission. No formal data may precede a source-qualified
release and complete clock/overhead qualification for its exact boundary
sequence. This engineering decision changes no duration, estimator, working
set, hardware state, consumer action, or prospective discovery selection rule.

Verify exact successful boundary order and values, FULL/empty rows, every
clock failure before/after operation, retained event/checksum action and real
counts after failures, trace exhaustion without lost operations, and explicit
record corruption. Run relevant sanitizers, allocation checks and strict
provenance/codegen gates before qualification.
