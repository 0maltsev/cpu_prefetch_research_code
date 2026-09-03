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
ADR-0148's": just splitting an existing flat snapshot using layout
information already available. Investigation before implementing found
that claim wrong, not merely optimistic.

`Q15PreparedProbeMemory`, `Q15PointerProbePreparation`, and `prepare_
q15_pointer_probe_buffer` (`include/cpu_prefetch/platform/q15_probe.hpp`,
`src/platform/q15_probe.cpp` -- read in full, header and implementation)
contain no trace of "shared", "producer", "consumer", or "private" region
concepts anywhere. Q15-R's prepared buffer is one homogeneous array of
cache lines, accessed by a single thread, either linearly (`regular_
stream`) or via a permutation-ordered pointer chase (`pointer_dependent`,
`Q15PointerProbePreparation{start_index, order, prepared_sha256}`).
`Q15ResidencySnapshot` (`include/cpu_prefetch/platform/q15_runtime.hpp`)
is a flat `page_nodes` list sized to the whole buffer's page count, with
no internal ownership split -- there are no producer-private or
consumer-private byte ranges to expose, because Q15-R never constructs
any.

The schema's three region names instead describe a real SPSC producer/
consumer queue's memory layout: `PilotPersistentContext` (`src/runner/
stage17_fixed_action.cpp`, investigated for ADR-0152's Gap 1) actually
has this shape -- `arena_` (event storage), `ring_`/`linked_` (the SPSC
queue itself, "shared"), with separate producer- and consumer-owned
regions implied by its `AffinedObservationPreparation`-driven producer/
consumer thread model. That memory model belongs to the Pilot session
action (`--execute-stage17-pilot-session-v1`), not Q15-R -- the same
action ADR-0152's Gap 1 found real, compiled, and never run for real
anywhere.

Unlike ADR-0147/ADR-0148/ADR-0152, where one real Q15-R fact (one CPU,
one CPUID observation) honestly stood in for a producer/consumer-shaped
schema field because Q15-R genuinely has only one of that fact, this
kind asks for three distinct *address regions* distinguished by
ownership role. Q15-R's buffer has exactly one region, with no ownership
role at all. Reporting the same flat snapshot three times under three
different region labels would not be an honest simplification the way
the earlier ADRs' shared single-CPU/single-observation reporting was --
it would assert a producer/consumer/shared ownership structure inside
Q15-R's memory that does not exist, which this engagement's evidence
discipline does not permit.

## Decision (proposed)

Not resolved. `ADDRESS_RESIDENCY` cannot honestly be built from Q15-R's
real, current memory model under any wiring-only approach; the two real
paths are the same shape as ADR-0152's Gap 1 alternative it did *not*
take:

1. Stand up the never-executed pilot-session action for real (its own
   full authoring/admission/execution lifecycle, not yet built for any
   real session) and source `ADDRESS_RESIDENCY` from its real producer/
   consumer memory layout instead of Q15-R's.
2. Revisit, with whoever owns `qualification-evidence-v1.schema.json`,
   whether `ADDRESS_RESIDENCY`'s three-region shape is essential to what
   S17-EXT-004 needs to demonstrate for the Q15-R/H0-H1 qualification
   specifically, versus a schema variant honestly describable from a
   single undifferentiated region -- a schema change, not a wiring
   change, and (like ADR-0152's equivalent note) outside a single ADR's
   authority to decide unilaterally.

No implementation should proceed against Q15-R for this kind until one
of these is chosen.

## Consequences

- This ADR's original "smaller than ADR-0148" framing is retracted, along
  with its claim that `Q15PreparedProbeMemory` exposes region byte
  ranges -- it does not.
- Whichever path is chosen, this is real, separate scoping and
  engineering work, comparable to ADR-0150's clock-qualification gap
  rather than to ADR-0147/0148/0152's wiring-only pattern.
- Blocks S17-EXT-004 admission independent of ADR-0147/0148/0150/0152 --
  all five `QUALIFICATION_EVIDENCE` kinds are required together.
