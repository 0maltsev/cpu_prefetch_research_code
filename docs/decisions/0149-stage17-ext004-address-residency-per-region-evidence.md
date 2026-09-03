# 0149. Stage 17 S17-EXT-004 per-region address-residency evidence

Status: ACCEPTED

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

Option 3 below revisits `qualification-evidence-v1.schema.json` itself.
`git log --diff-filter=A -- config/schemas/qualification-evidence-v1.
schema.json` shows the file was added in commit `b392af7` ("Close Stage
17 pilot-candidate release mapping"), authored by the project owner
directly, before any Stage 17 admission apparatus existed -- so unlike
most schemas this ADR family touches, its three-region shape is not an
inherited constraint from outside this decision's authority; the owner
is its original author and can authorize revising it directly.

## Decision

Option 3, chosen and implemented: relax `residency_details` from three
fixed named regions to a generic `regions` array, letting each real
action report however many real regions it genuinely has instead of
fabricating a producer/consumer/shared split no current action's memory
architecture possesses. See Implementation below. The three options as
originally scoped:

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

## Implementation

`qualification-evidence-v1.schema.json`'s `residency_details` now
requires `mechanism_id` plus a `regions` array (`minItems: 1`) of the
already-existing, already-general `$defs/region` object -- unchanged
itself: still `region` (self-naming) + `expected_node` + before/during/
after/unavailable/wrong-node/migrated page counts, so no per-region
rigor is lowered, only the outer shape (fixed field names -> array) is
relaxed. `AddressResidencyInput` (`include/cpu_prefetch/runner/
qualification.hpp`) now holds `std::vector<RegionResidencyInput>
regions` instead of three named fields; `make_address_residency_evidence`
(`src/runner/qualification.cpp`) requires every region to pass (`std::
all_of`) and emits a `regions` JSON array in the same order.

Q15-R (`src/runner/stage17_fixed_action.cpp`, `publish_q15_r`) now
publishes a real `Q15_R_ADDRESS_RESIDENCY_RAW` artifact: its
`regular_stream` and `pointer_dependent` probes share one physical
buffer but are two distinct temporal measurement windows, so each is
reported as its own honestly-named region (`regular_stream_probe_
buffer`, `pointer_dependent_probe_buffer`) derived from the
`Q15ResidencySnapshot`s already collected by `observation_passes`, using
the same `unavailable`/`wrong-node`/`migrated` derivation as ADR-0148's
`ACTUAL_CPU_MIGRATION` work. New schema `config/schemas/stage17-q15-r-
address-residency-raw-v1.schema.json` validates the raw artifact; the
role is registered in `stage17-operational-artifact-v4.schema.json`'s
closed enum and the matching output entry added to `stage17-fixed-
phase-actions-v4.json` (in the exact position `publish_all` emits it --
applied proactively this time, learned directly from the real Q15-R
session-19 `OutputAdmissionError: "fixed action output set differs from
registry"` production failure earlier in this project). Policy v39
re-rendered via `author_stage17_policy_v39.py --write` to pick up both
pinned schema changes; 0/413 binding drift confirmed, nested preflight
policy v27 unaffected.

Incidentally confirmed rather than caused by this change:
`src/qualification/q15_collectors.cpp`'s `collect_q15_address_residency`
(a separate, pre-existing, production-unused function reachable only
from `tests/q15_collectors_test.cpp`) already emitted its own JSON in a
`regions`-array wire shape via its own independent construction path,
not through `AddressResidencyInput` at all -- it needed no change and
compiled unmodified, but its pre-existing shape cross-validates that an
array-of-self-named-regions representation was already the direction
this codebase's own prior work anticipated for this evidence kind, not
an invention specific to this ADR. That function still hardcodes an
expectation of exactly three regions named `CONSUMER_PRIVATE`/
`PRODUCER_PRIVATE`/`SHARED_EVENT_AND_QUEUE` for its own "complete"
check, so it remains specific to a possible future producer/consumer
action and was not adapted for Q15-R's two-region case -- Q15-R's
artifact is built directly in `publish_q15_r`, following the same
pattern as ADR-0147/0148/0152, not routed through this collector.

Verified: `tools/check_qualification_schema.py` (5 positive, 4 negative
fixtures) passes with a `regions`-array `residency` fixture;
`tools/check_stage17_fixed_action_production.py` and `tools/check_
stage17_production_handoff_v4.py` (both had an identical three-key
`ADDRESS_RESIDENCY` synthetic fixture, both updated to a `regions` list)
pass; `tests/runner_model_test.cpp`'s two `make_address_residency_
evidence` call sites updated to the new shape; full `cmake --build
--preset dev-gcc` succeeds; `ctest --test-dir build/dev-gcc -L
"q15|timing"` -- 126/126 tests pass (110 q15, 16 timing), including
`cpu_prefetch_q15_collector_tests`, confirming no regression anywhere
that referenced the old three-fixed-field shape.

Not yet done, and out of scope without a separate, explicit decision:
rebuilding/resealing a new stand bundle with this change, or exercising
it for real on the accepted stand (a real Q15-R session publishing
`Q15_R_ADDRESS_RESIDENCY_RAW`); the Python authoring tool that would
wrap the raw artifact into the final schema-compliant `QUALIFICATION_
EVIDENCE` envelope (ADR-0151's pattern) -- not yet built for this or any
of the other four kinds in this family.

## Consequences

- Resolves S17-EXT-004's `ADDRESS_RESIDENCY` gap without fabricating a
  producer/consumer/shared memory split no current real action's
  architecture has, and without the circularity option 2 would have
  introduced against Q16-family's own S17-EXT-004/005/006
  prerequisites.
- The schema relaxation is structural (field names -> a self-describing
  array), not a lowered measurement bar: every existing per-region
  pass/fail rule is unchanged and still required for every region an
  action reports.
- Leaves `platform::Placement`'s producer-private/consumer-private
  fields exactly as they were -- real, validated, but still unused by
  any production action -- available unchanged for whichever future
  Q16-family work (or Pilot-session extension) eventually needs them;
  this ADR does not foreclose either.
- Was the last of the five `QUALIFICATION_EVIDENCE` kinds in this
  family; with ADR-0147/0148/0150/0152 already ACCEPTED, all five now
  have real, implemented, tested builders. S17-EXT-004 admission itself
  -- which additionally needs each kind's raw artifacts wrapped into
  final schema-compliant envelopes, and real stand execution for the
  kinds (ADR-0150, this ADR) not yet exercised for real -- remains a
  separate, not-yet-attempted step.
