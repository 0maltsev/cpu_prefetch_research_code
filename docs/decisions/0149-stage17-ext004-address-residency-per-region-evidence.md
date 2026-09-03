# 0149. Stage 17 S17-EXT-004 per-region address-residency evidence

Status: PROPOSED

## Context

S17-EXT-004's `ADDRESS_RESIDENCY` qualification-evidence kind requires
(`config/schemas/qualification-evidence-v1.schema.json`'s `residency_
details`) a `mechanism_id` plus three named regions --
`shared_event_and_queue_pages`, `producer_private_pages`, `consumer_
private_pages` -- each with `expected_node`, and before/during/after/
unavailable/wrong-node/migrated page counts. The typed builder, `make_
address_residency_evidence`, already exists and is schema-validated and
unit-tested (synthetic values only, as with the other four kinds).

Real Q15-R's `Q15ResidencySnapshot` (`include/cpu_prefetch/platform/
q15_runtime.hpp`) is currently a single, flat `page_nodes: vector<int32_t>`
covering the *entire* prepared probe buffer, taken once before, during,
and after each probe pass (`Q15ProbePassObservation.before_residency`/
`during_residency`/`after_residency`) -- it does not distinguish which
pages belong to the shared event/queue region versus the producer- or
consumer-private regions the schema requires separately.

`Q15PreparedProbeMemory` (same header) manages the buffer's own layout
internally and necessarily knows the byte ranges for each region (it
constructs the shared queue and both private regions within one prepared
mapping) -- this is a real, existing internal fact, not something that
needs new hardware measurement to discover. The gap is narrower than
ADR-0148's: the raw per-page node data already exists for the whole
buffer; what's missing is splitting `page_nodes` by region using layout
information the memory-preparation code already has, and deriving the
per-region unavailable/wrong-node/migrated counts by comparing each
region's before/during/after node lists against the mechanism's expected
node.

## Decision (proposed)

Extend `Q15PreparedProbeMemory` (or a thin wrapper around it) to expose
its own region byte-range boundaries, and extend residency snapshotting
to record `page_nodes` per region rather than as one flat list for the
whole buffer. Derive the schema's six per-region counts by comparing
each region's before/during/after snapshots against the buffer's
expected NUMA node. Add the glue (mirroring ADR-0147) to build an
`AddressResidencyInput` from this per-region data and call the already-
implemented `make_address_residency_evidence`.

## Consequences

- Smaller in scope than ADR-0148 (no new hardware sampling, just
  splitting an existing snapshot by already-known region boundaries),
  but still a real C++ change to `Q15PreparedProbeMemory`/residency
  snapshotting, with the same measured-path audit discipline to confirm
  the change doesn't perturb the timed probe passes.
- Requires a real Q15-R re-run on the stand after the change; the three
  already-captured real sessions cannot retroactively supply per-region
  data.
- Should be scoped and implemented separately from ADR-0147 and
  ADR-0148.
