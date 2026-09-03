# 0148. Stage 17 S17-EXT-004 actual-CPU-migration evidence instrumentation

Status: PROPOSED

## Context

S17-EXT-004's `ACTUAL_CPU_MIGRATION` qualification-evidence kind requires
(`config/schemas/qualification-evidence-v1.schema.json`'s `cpu_details`):
`producer_sample_count`, `consumer_sample_count`, `producer_first_cpu`,
`producer_last_cpu`, `consumer_first_cpu`, `consumer_last_cpu`, `producer_
migration_count`, `consumer_migration_count`, `producer_singleton_
affinity`, `consumer_singleton_affinity`. The typed builder for this kind,
`make_actual_cpu_migration_evidence` (`include/cpu_prefetch/runner/
qualification.hpp`), already exists, is schema-validated, and is unit-
tested in `tests/runner_model_test.cpp` -- but only against hand-supplied
synthetic values, never real ones.

Real Q15-R's own `Q15ProbePassObservation` struct (`include/cpu_prefetch/
platform/q15_runtime.hpp`) currently carries a *single* `entry_cpu`,
`exit_cpu`, and `singleton_affinity` per probe pass -- one observation
covering the whole pass, not separated by producer/consumer role, and
with no multiple-sample migration tracking within the pass. This is a
real, structural gap, not a serialization gap: the `ActualCpuMigration
Input` fields ADR-0147 could satisfy by reading already-computed data
cannot be honestly populated from what `Q15ProbePassObservation` records
today.

## Decision (proposed)

Extend the real Q15-R probe-pass measurement loop (`run_q15_probe_pass`,
`src/runner/stage17_fixed_action.cpp` and/or `include/cpu_prefetch/
platform/q15_runtime.hpp`) to sample CPU affinity multiple times during
each pass, separately for the producer and consumer threads, recording:

- a per-thread sample count,
- first/last observed CPU per thread,
- a migration count (transitions between distinct CPUs across samples),
- whether singleton affinity held for the whole pass per thread.

This is new measurement code inside the timed/measured path, so it must
go through the same dual-disassembler codegen-audit discipline
(`docs/PRODUCTION_RUNNER.md`'s "Affined preparation and static
specialization boundary") the rest of the runner's measured path
already requires -- affinity sampling must not itself perturb the
measurement it is meant to characterize, which needs careful placement
(likely only inside the already-existing pre/post-measurement affinity
checks, not inside the hot inner loop) and its own scoping session
before implementation.

## Consequences

- Requires new C++ instrumentation in the runner's own measured path,
  with the same strict audit requirements (no allocation, no blocking
  calls, exact instruction accounting) the rest of that path already
  meets -- a real, nontrivial implementation task, not a wiring fix.
- Requires a real Q15-R re-run on the stand after the change to produce
  real evidence with the new fields; the three already-captured real
  sessions (`-16E`/`-17`/`-18`) cannot retroactively supply this data.
- Should be scoped and implemented separately from ADR-0147, which needs
  no new measurement code at all.
