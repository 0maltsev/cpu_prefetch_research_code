# Stage 12 reconciliation and run-status contract

Protocol version: **`2.0.0-pre.2`**. This is post-run software correctness
machinery. Every test fixture is synthetic; no result is a latency or throughput
observation.

## Exact ordered join

`reconcile()` accepts four prepared inputs: an explicit `run_id`, the immutable
producer stream, the immutable consumer stream, and the Stage 6
logical-sequence-to-record-index mapping. It never parses identity from a path
and never accepts a serialized pointer.

The validator performs these steps in order:

1. require producer row `i` to carry this run ID and `logical_sequence=i`;
2. require its `record_index` to equal the independently constructed Stage 6
   mapping at `i`;
3. build the accepted sequence in producer logical order, requiring contiguous
   accepted ordinals and exact `ACCEPTED`/`FULL` optional-field shapes;
4. require consumer count to equal accepted count;
5. require consumer row `k` to carry this run ID, `consumed_ordinal=k`, and the
   record index of accepted producer event `k`;
6. only if every preceding check passes, invoke the Stage 8 interval derivation
   for every pair.

Record indices may repeat. They validate the expected address construction and
k-th pairing but never identify an event. Loss of the first, last, or an
internal event; duplicate or malformed ordinals; forbidden reordering;
unexpected record mapping; record corruption; run mismatch; or timestamp-order
failure produces `FAILED`, a classified issue list, and zero joined rows. A
failed audit cannot name a joined artifact.

## Derived intervals

The post-join implementation reuses the accepted Stage 8 equations:

```text
producer_lateness             = producer_handle_begin - scheduled_arrival
pointer_lookup_interval       = record_lookup_completion - producer_handle_begin
enqueue_service_time          = enqueue_attempt_completion - enqueue_invocation
admission_delay               = enqueue_linearization - scheduled_arrival
queue_residence               = dequeue_linearization - enqueue_linearization
dequeue_service_time          = dequeue_completion - dequeue_invocation
post_dequeue_delivery         = consumer_action_completion - dequeue_linearization
consumer_action_interval      = consumer_action_completion - dequeue_completion
end_to_end_latency            = consumer_action_completion - scheduled_arrival
```

Only `admission_delay + queue_residence + post_dequeue_delivery` is the additive
partition of end-to-end latency. The other intervals are nested diagnostics and
are not summed into it. `FULL` producer rows never receive latency fields.

## Audit and artifact relationships

The implementation-owned `cpu-prefetch-join-audit/1` document is canonical
`JCS-I64-v1` JSON with a zero-self SHA-256. It records protocol/run identity,
producer/accepted/`FULL`/consumer counts, ordered producer and consumer source
references, classified failures, and an optional joined reference. Its schema
is [`join-audit-v1.schema.json`](../config/schemas/join-audit-v1.schema.json).

`Stage12CrossRecordSemanticValidator` combines the Stage 4 record-local pass
with immutable artifact lookup and verifies:

- one internally consistent `2.0.0-pre.2` graph and unique artifact IDs/
  relationships;
- manifest, failure-evidence, and artifact hashes plus source relationships;
- manifest queue-provenance identity against the accepted historical
  `cpu-prefetch-queue-provenance/1` artifact suite;
- exact raw decoding, exact reconciliation, and equality of every stored
  joined field to the independently derived row;
- raw, accepted, `FULL`, consumed, joined, manifest, and measurement-schedule
  counts;
- failure IDs, run identity, and invalidating evidence;
- schedule references/version/count;
- phase/integrity report identity, source binding, content-match result, and
  all five algorithm/version/value triples;
- lifecycle-dependent presence and absence without fabricated streams.

For every attempted join, the validator independently regenerates the entire
canonical audit—including ordered sources, exact counts, classified issues,
conditional joined reference, and zero-self hash—and requires byte equality
with the stored audit.

Unknown or mixed versions, missing bytes, checksum mismatches, or relationship
disagreement fail closed. Historical `2.0.0-pre.1` records remain readable by
the typed loader, but Stage 12 final disposition is available only for
`2.0.0-pre.2`; there is no implicit conversion.

## Independent status gates

`evaluate_run_status()` returns distinct lifecycle-completion, validity, join,
count-reconciliation, zero-loss, effective-tail, block-completeness, and
confirmatory-estimability states.

- Exact completed counts require
  `offered=attempted=accepted+full`, `consumed=accepted`, final occupancy zero,
  and `raw_sample_count=accepted`.
- A correctly reconciled `FULL` count leaves the run `VALID` and makes only
  zero-loss `FAIL`.
- Genuine `N_eff<200000` leaves the run `VALID` and makes only effective-tail
  `FAIL`.
- `INVALID` is rejected unless an invalidating failure record exists.
- None of these states authorizes a hidden retry, run extension, selective
  removal, or block replacement.

Under D-031, final `confirmatory_blockers` contains every applicable cause in
UTF-8 token order. One cause maps to its singular summary and multiple causes
map to `BLOCKED_MULTIPLE`. Until authoritative block-completeness and access
evidence is injected, the summary remains `NOT_EVALUATED` and the array empty,
even while independent run-level gate facts remain visible.

## Deferred block-level obligations

Stage 12 does not calculate the exact 180-cell block product, original/
replacement completeness across runs, selection/unseal chronology, custody, or
access leakage. Stage 14 now supplies the separate exact-product and
block/access/freeze cross-record validator, but it does not fabricate
authoritative counts, seeds, budgets, principals, or custody evidence. Stage 15
must integrate the passed gate outputs into analysis records, and Stage 16
still owns real-stand storage, custody, and operational evidence. No scientific
run is authorized by either implementation.
