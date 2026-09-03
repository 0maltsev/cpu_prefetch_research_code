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

This ADR originally claimed `Q15PreparedProbeMemory` "necessarily knows
the byte ranges for each region" and that the gap was "narrower than
ADR-0148's." A first investigation pass retracted that: Q15-R's own
memory (`Q15PreparedProbeMemory`, `Q15PointerProbePreparation`) has no
producer/consumer/shared split at all -- it is one homogeneous buffer
probed by a single thread -- and proposed two paths: stand up the never-
run Pilot session action instead, or revisit the schema's three-region
shape.

A second, deeper investigation (this pass) checked the first path
concretely and found it is not simply "the same evidence, elsewhere":

- `PilotObservationPreparation::observe_during_measurement()`
  (`src/runner/stage17_fixed_action.cpp`) queries residency over the
  *whole* `EventArena` in one call (`platform_.query_residency(arena_.
  storage_address(), arena_.allocated_bytes(), ...)`) -- one flat
  snapshot, exactly like Q15-R's own pattern, not split by role.
  `PilotPersistentContext`'s `ring_`/`linked_` (the SPSC queue itself,
  separately allocated from the arena) are never residency-queried at
  all in this class. `workload::EventArena` (`include/cpu_prefetch/
  workload/records.hpp`, `EventArenaLayout`) has no internal producer/
  consumer-private byte-range concept either -- it is a single shared
  record store both roles read and write.
- The three-region vocabulary *does* have a real referent elsewhere:
  `platform::Placement` (`include/cpu_prefetch/platform/platform.hpp`)
  has real, unit-tested `producer_private_memory_policy`/`producer_
  private_nodes`/`consumer_private_memory_policy`/`consumer_private_
  nodes` fields, and `src/platform/platform.cpp` has real validation
  ("producer-private buffers must be producer-local", "consumer-private
  buffers must be consumer-local"). `docs/PLATFORM_CONTROL.md`
  confirms this is the intended source: "shared queue/node/event/
  schedule storage is bound to the producer node; producer-private and
  consumer-private buffers are bound to their worker nodes... Actual
  affinity, allocation policy, page residency, and migration
  observations are separate typed controls. **A later run controller
  must collect their before/during/after evidence** for the exact
  thread IDs and address extents" -- the project's own documentation
  already states this is future work, not something any current action
  performs.
- But `Placement`'s producer-private/consumer-private fields are, today,
  *policy only*: a repository-wide search found no real production code
  anywhere that constructs a `Placement` with these fields populated --
  `producer_private_memory_policy` is exercised exclusively by `tests/
  platform_model_test.cpp`. The real action this vocabulary belongs to
  is the Q16-family (`Q16a`/`Q16b`/`Q16c`, the "combined operation"
  benchmark runs `include/cpu_prefetch/runner/qualification.hpp`'s
  `RegionResidencyInput producer_private_pages` field was clearly
  designed around) -- and `config/stage17/stage17-fixed-phase-actions-
  v4.json` requires `S17-EXT-004`, `S17-EXT-005`, and `S17-EXT-006`
  already admitted before Q16a/b/c can even be authorized. Building a
  real Q16-family run to source `ADDRESS_RESIDENCY` would mean building
  the very evidence kind S17-EXT-004 needs as a *prerequisite* of
  S17-EXT-004 itself -- a real circularity, not just a larger lift.

So: no current real action -- Q15-R, the Pilot session, or (structurally)
Q16-family -- has genuine producer-private or consumer-private memory to
observe. The one real, already-proven primitive shared by every path
(`platform_.query_residency(...)`, used identically by both Q15-R and
the Pilot session for whole-buffer snapshots) only ever measures one
undifferentiated region; nothing in the repository has ever allocated a
producer-private or a consumer-private buffer for real. This is a gap in
real memory *architecture*, not only in measurement orchestration --
larger in kind than ADR-0150's clock-pairing gap, where the low-level
primitive (`read_monotonic_raw_absolute()`) was already real and simply
needed composing into a new measurement.

## Decision (proposed)

Still not resolved; now better specified. Three real options, none of
them wiring-only:

1. **Extend the Pilot session with real producer-private/consumer-
   private allocations.** Add two new, genuinely separate NUMA-local
   buffers to `PilotPersistentContext` (one bound to the producer's
   node, one to the consumer's, matching `Placement`'s already-validated
   policy), assign them some real per-role purpose (even a minimal one),
   and query residency on all three regions (`arena_`/`ring_`/`linked_`
   combined as "shared", plus the two new private buffers) separately.
   This is real new measurement *and* real new memory design, done
   against an action that has never run for real.
2. **Build the real Q16-family action far enough to source this
   directly**, accepting the circularity noted above by treating
   `ADDRESS_RESIDENCY` as satisfied from Q16's own first real run rather
   than as an S17-EXT-004 prerequisite -- which likely means this
   specific evidence kind cannot be part of S17-EXT-004 as currently
   scoped without a sequencing change elsewhere.
3. **Revisit `qualification-evidence-v1.schema.json`'s three-region
   shape for `ADDRESS_RESIDENCY`** given the project's own documentation
   already describes per-region residency as later, not-yet-built work
   -- possibly relaxing it for an Q15-R-only qualification path, or
   moving it to whichever gate actually corresponds to Q16's own
   qualification. Still a schema change, not something this ADR should
   decide unilaterally, but now supported by more concrete evidence
   that the current shape may not match where the project's own
   documentation places this measurement in the pipeline.

No implementation should proceed until one of these is chosen.

## Consequences

- This is now assessed as a larger and more structural gap than ADR-0150
  (SELECTED_PAIR_CLOCK), not smaller: SELECTED_PAIR_CLOCK's low-level
  primitive was already real; `ADDRESS_RESIDENCY`'s per-region memory
  model has never been built for any real action, only validated as
  policy and referenced in documentation as future work.
- Options 1 and 2 both require real, new engineering distinct from every
  other ADR in this family (0147/0148/0150/0152); option 2 additionally
  surfaces a real sequencing/circularity problem in how S17-EXT-004 is
  scoped relative to Q16-family's own prerequisites.
- Blocks S17-EXT-004 admission independent of ADR-0147/0148/0150/0152 --
  all five `QUALIFICATION_EVIDENCE` kinds are required together.
