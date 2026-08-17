# Data Flow

## Overview

The planned flow preserves protocol/configuration evidence separately from timed observations and keeps producer and consumer data private until after the run.

```text
immutable protocol snapshot
        |
        v
decision records + platform evidence + seed namespaces
        |
        v
schema validation + semantic validation
        |
        v
schedule / arena / block-plan preparation ----> pre-run checks
        |                                           |
        +---------------- validated run image <-----+
                              |
                  start barrier and frozen t0
                              |
             +----------------+----------------+
             |                                 |
      producer data plane                consumer data plane
      private ordered rows               private ordered rows
             |                                 |
             +---------- drain/seal -----------+
                              |
                  accepted-ordinal join audit
                    | pass              | fail
                    v                   v
             joined-derived rows    failure record only
                    |
          validity / zero-loss / effective-tail gates
                    |
       role-aware access control and offline analysis
```

## Preparation flow

1. Resolve the imported protocol version and reject incompatible `1.x` records unless an explicit audited migration exists.
2. Load only accepted ADRs and freeze records applicable to the requested lifecycle stage.
3. Derive identities from explicit fields, never directory names: platform, build, block, role, run, factor cell, ordinal, schedule, namespaces, raw artifacts, and access records.
4. Generate schedules, event order, node order, payloads, block order, and all checksums outside the measurement path.
5. Allocate and first-touch persistent queue/event arenas and fixed-capacity worker-private buffers according to the verified placement record.
6. Validate schema shape and all currently decidable semantic invariants. A failure stops before worker launch and creates a failure record without fabricated raw streams.
7. Verify actual CPUs, cache ancestry, NUMA/page residency, persistent arena identity, requested versus verified HW-PF state, clock, schedule, build, and address-pattern evidence.

Warm-up uses a disjoint namespace. It drains, reaches a barrier, restores the protocol-defined logical origin without remapping or broad payload retouch, then releases both workers from a start barrier using the frozen clock protocol. This is a controlled warm start, not a cold-cache start.

## Measurement flow

### Producer stream

For every scheduled logical arrival, the producer retains `run_id`, logical sequence, record index, `scheduled_arrival`, `producer_handle_begin`, `record_lookup_completion`, `enqueue_invocation`, `enqueue_attempt_completion`, attempted status, and `ACCEPTED` or `FULL`. An accepted row also carries its queue-specific `enqueue_linearization` and accepted ordinal. A `FULL` row carries neither accepted ordinal nor enqueue linearization.

The producer appends only to its preallocated private stream. One `FULL` is retained, counted, and never retried.

### Consumer stream

For every successful dequeue, the consumer retains `run_id`, consumed ordinal, observed record index, `dequeue_invocation`, `dequeue_linearization`, `dequeue_completion`, and `consumer_action_completion`. The final boundary is taken only after immutable index/payload loads and the frozen private checksum update.

The consumer appends only to its preallocated private stream. It never writes producer observations or event records.

### Termination and drain

After attempting the last scheduled arrival, the producer release-publishes `arrivals_finished` on an isolated control line. The consumer continues until it acquire-observes the flag and the queue is empty. Events accepted within the half-open arrival horizon remain in scope when their consumer action completes during drain.

## Post-run reconciliation

1. Seal the producer and consumer raw artifacts with their envelopes and integrity references.
2. Prove `offered = attempted`, `attempted = accepted + full`, and after drain `accepted = consumed` with zero final occupancy.
3. Filter producer rows to accepted logical-arrival order and join consumer row `k` to accepted producer row `k` by `(run_id, accepted_ordinal)`.
4. Use record index only to validate the repeating frozen record sequence.
5. Reject mismatched identity/count/pointer/index, duplicate, omission, forbidden reorder, timestamp-order error, or interval-equation error.
6. Always emit a join audit. Emit joined-derived rows only when that audit passes.

For an accepted event, derive exactly:

```text
producer_lateness              = b - a
pointer_lookup_interval        = c - b
enqueue_service_time           = re - u
admission_delay                = p - a
queue_residence                = q - p
dequeue_service_time           = rd - v
post_dequeue_delivery_interval = f - q
consumer_action_interval       = f - rd
end_to_end_latency             = f - a
                               = admission_delay
                               + queue_residence
                               + post_dequeue_delivery_interval
```

The other intervals are nested or overlapping diagnostics and are never added to the final identity.

## Status and gate flow

Lifecycle, join status, run validity, count reconciliation, zero-loss, effective-tail status, confirmatory estimability, and block completeness are separate fields.

- Correctly reconciled `full > 0`: run may remain `VALID`; zero-loss is `FAIL`; no replacement is authorized.
- Genuine `N_eff < 200000`: run remains retained; effective-tail is `FAIL`; no repeat or extension is authorized.
- Correctness/measurement failure: run is invalid and the original block becomes incomplete.
- Failed join: failed audit and failure record exist; successful joined data do not.
- Valid completed Stage A run: both raw streams, passed audit, joined rows, complete counts, provenance, and phase/integrity evidence are mandatory.

## Block and access flow

Every original complete Stage A block has exactly 180 cells and one immutable role: `H3_TRAIN`, `H3_VALIDATION`, or `H1H2_SUPPLEMENTAL`. An invalid cell never receives an in-block repair. A permitted replacement is a new complete role-compatible block with a new identity, ordinal, seed subspace, and randomization; all original records remain.

Access progresses only through:

```text
PLANNED -> COLLECTED_SEALED -> TRAINING_OPEN -> SELECTION_FROZEN
        -> VALIDATION_UNSEALED -> H3_EVALUATED -> H1H2_RELEASED -> ARCHIVED
```

Validation content, summaries, and treatment-dependent diagnostics remain inaccessible through training selection. H1/H2 cannot consume the common block pool until the source-hashed H3 evaluation/access record permits release.

## Derived-data rule

Histograms, quantiles, CCDFs, models, tables, and figures are derived artifacts. Each must name immutable input artifact IDs/hashes and analysis provenance. Corrections append a new derived record and never mutate raw producer or consumer streams.
