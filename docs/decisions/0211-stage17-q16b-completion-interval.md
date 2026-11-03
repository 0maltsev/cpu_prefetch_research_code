# ADR-0211: Q16b completion-count interval

- Status: `ACCEPTED` — exact proposal approved by the owner on 2026-11-03
- Date: 2026-11-03
- Amendment ID: `AMEND-2.0.0-pre.3-Q16B-INTERVAL-COMPLETIONS-v1`
- Scope: formal EXT007 Q16b service-rate numerator only
- Immutable protocol: `protocol/2.0.0-pre.3/` remains unchanged
- Execution authority: none; no new capture, qualification, retry or extension

## Missing decision

The implementation specification §5.3 requires consumed-event throughput over
its fixed calibration interval. §8.1 defines `f_i` as consumer-action completion.
ADR0035 retains the exact rational `consumed * ticks_per_second / interval_ticks`,
all valid low/zero runs, and the complete prospective run plan. These sources do
not explicitly decide which completion timestamps are included at the interval
boundary. The half-open convention in §5.1 and the data dictionary governs
scheduled arrivals, not explicitly consumer completions.

Current `capture_ticketed_service_rate` counts consumption through the required
drain; the run summary publishes only this total. Reusing that total as the
fixed-interval numerator includes post-interval service. Both facts require
correction, but code must not silently choose the missing boundary convention.

Sources: [specification](../../protocol/2.0.0-pre.3/EXPERIMENT_IMPLEMENTATION_SPEC.md),
[data dictionary](../../protocol/2.0.0-pre.3/handoff/DATA_DICTIONARY.md),
[accepted D035](0035-stage13-service-rate-lower-limit.md).

## Proposed rule

For an otherwise valid formal Q16b run, let `t0` be the actual measurement
start-barrier origin and `T > 0` its prospectively frozen duration, expressed
in the same exact integer clock domain as consumer-action completion `f_i`.
Define:

`N_interval = count of reconciled measurement events satisfying t0 <= f_i < t0 + T`.

A completion exactly at the start is included; exactly at the end is excluded.
An operation that starts before the end but completes at or after it is excluded
from this numerator. Its observation remains retained and reconciled. Producer
attempt-start time, dequeue-start time, and drain end never substitute for `f_i`.

Use `N_interval * ticks_per_second / T` as D035's exact rational run throughput.
Retain total consumed count separately for post-drain `accepted == consumed`
and zero occupancy. Retain the interval origin, duration, clock domain/unit,
interval count and outside-interval count in a versioned summary, and recompute
the interval count independently from the original consumer observations.
Do not add a counter, timestamp read, filtering or analysis to the measured loop.
A raw timestamp inconsistency remains invalid; this rule cannot hide malformed
or missing observations. Reject invalid unit/origin bindings and integer overflow.

Preserve the entire producer/consumer raw streams, required drain, checksum
operation, queue/prefetch behavior, fixed duration, warmup/reset rules, and
accepted/full/consumed totals. A valid zero interval throughput remains valid
and enters the existing minimum estimator. Correctly reconciled FULL remains
valid data and separately fails zero loss. No top-up, selective repetition,
rate-dependent duration or favorable filtering is authorized.

## Compatibility and acceptance boundary

This is a narrow prospective completion-window clarification. It does not
choose Q16b duration, exact repetition count, seeds, buffers, resource limits
or a stand execution plan. Those still require their own prospective records.
It does not change or consume the already approved running D207 diagnostic
family, its selector, or any previous raw evidence.

Historical readers and artifacts retain their existing identities. New formal
summaries and admission must distinguish interval count from total consumed;
old summaries must not be silently reinterpreted as corrected evidence.

The affected numerator implementation was blocked until this proposal's
exact bytes were accepted and recorded below. Independent implementation of the
already-required five-second persistent warmup/reset could continue. Following
acceptance, require boundary/crossing/drain/zero-throughput/overflow and
independent raw-recomputation tests, relevant sanitizers and release gates.

## Owner acceptance

The owner replied `Approve D211 counting rule` to the exact proposal SHA256
`0f38dcbea5ce9c6d9e1d82e82f72945f9ee86543d621a68e35667f0f8bb0fd10`. The [original proposal and acceptance](../evidence/stage17/Q16B-D211-ACCEPTANCE-20261103-01/owner-acceptance.json)
are retained. This unblocks the numerator implementation, not experimental execution.
