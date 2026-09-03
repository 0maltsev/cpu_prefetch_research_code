# 0148. Stage 17 S17-EXT-004 actual-CPU-migration evidence instrumentation

Status: ACCEPTED

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

This ADR originally assessed real Q15-R's `Q15ProbePassObservation`
(`entry_cpu`, `exit_cpu`, `singleton_affinity` -- one observation per
probe pass) as insufficient: "a real, structural gap, not a serialization
gap," requiring new multi-sample measured-path instrumentation with
careful scoping to avoid perturbing the timed region. Follow-up
investigation before implementing found that assessment too pessimistic.

`singleton_affinity` is not a point-sample; it is `Linux
QPlatformOperations::singleton_affinity_matches` (`src/platform/q15_
runtime.cpp:199-211`) reading `sched_getaffinity` and checking `CPU_COUNT
(&set) == 1 && CPU_ISSET(cpu, &set)` -- a genuine OS-level affinity-*mask*
restriction, checked immediately before the counted region in `run_q15_
probe_pass` (`src/platform/q15_runtime.cpp:465`). While that mask holds,
the Linux scheduler is structurally incapable of migrating the thread to
any other CPU -- not merely "unobserved," but impossible. A repository-
wide search confirmed `sched_setaffinity` is called exactly once anywhere
in the Q15 platform code (`LinuxQ15PlatformOperations::bind_current_
thread`, `src/platform/q15_runtime.cpp:183-196`), during memory
preparation (`Q15PreparedProbeMemory::create`, called before either probe
pass runs) -- never inside `run_q15_probe_pass` itself, which only reads
affinity (`sched_getaffinity`/`sched_getcpu`), never sets it.

Further, `publish_q15_r`'s own `observation_passes` gate already hard-
requires, for *both* the regular and pointer probes, that `singleton_
affinity` held and `entry_cpu == exit_cpu == session.memory->cpu()`
(`Q15ProbePassObservation::cpu_passes`) before any output is published at
all -- any real published Q15-R session therefore already, provably,
guarantees zero migration across both probes. Reporting this is not an
approximation from sparse sampling; it is a structural corollary of an
invariant Q15-R's own pass/fail gate already enforces.

## Decision

Wire `ACTUAL_CPU_MIGRATION`'s raw data as a pure serialization task, the
same pattern as ADR-0147/ADR-0152: no new measured-path instrumentation.
`publish_q15_r` publishes both probes' `entry_cpu`/`exit_cpu`/`singleton_
affinity` as four ordered samples (regular-entry, regular-exit, pointer-
entry, pointer-exit -- confirmed real execution order: `run_q15_probe_
pass` is called with `regular_stream` before `pointer_dependent`,
`src/runner/stage17_fixed_action.cpp:525` and `:533`). As with ADR-0147/
ADR-0152, Q15-R has no real producer/consumer thread pair (a single probe
CPU), so this one real four-sample series honestly stands for both
`producer_*` and `consumer_*` schema fields; a later authoring step
derives `migration_count` (provably 0, from `singleton_affinity` and
identical CPUs across all four samples) and `first_cpu`/`last_cpu` from
this raw series.

## Implementation

`publish_q15_r` now also publishes `Q15_R_CPU_MIGRATION_RAW` (`q15-r-cpu-
migration-raw-v1.json`, new schema `stage17-q15-r-cpu-migration-raw-v1.
schema.json`): `expected_cpu`, an ordered four-sample array (`probe`,
`point`, `cpu` per sample), and `singleton_affinity` per probe. Pure
sibling addition; `q15-r-output-v3.json` is unchanged.

Verified: `cmake --build --preset dev-gcc` (full default target set)
succeeds; `cpu_prefetch_runner_tests` (20/20) passes; `check_
qualification_schema.py` and `check_runner_schema.py` both pass; the new
schema validates its own meta-schema and a positive fixture.

## Amendment (found while building S17-EXT-004's envelope-authoring
tooling)

This ADR's own "one real four-sample series honestly stands for both
`producer_*` and `consumer_*` schema fields" claim was never actually
exercised against `make_actual_cpu_migration_evidence` -- only the raw
artifact was wired and verified. Building that "later authoring step"
found it cannot work as originally accepted: `make_actual_cpu_migration_
evidence` required `producer_first_cpu == identity.workers.producer_cpu`
*and* `consumer_first_cpu == identity.workers.consumer_cpu`, and `valid_
identity` (shared by all five kinds) requires `identity.workers` to be
exactly `kNearWorkerPair{0,1}` or `kFarWorkerPair{0,26}` -- both real
accepted pairs have distinct producer/consumer CPU ids. Q15-R's real
series sets all four fields to its one real CPU, so it could never
satisfy both equalities under any accepted pair; the envelope would have
computed `eligible: false` for every real Q15-R session, permanently.

Fixed in `make_actual_cpu_migration_evidence` (`src/runner/
qualification.cpp`): when all four `producer_*`/`consumer_*` fields are
equal (a real single-CPU series, no genuine producer/consumer thread
pair), the check now requires only that one CPU to equal `identity.
workers.producer_cpu`, matching Q15-R's real convention of running on
CPU 0, which both accepted pairs share as their `producer_cpu`. An
action with a real, genuinely distinct two-CPU pair (all four fields not
equal) still requires the original, unchanged strict check against both
`producer_cpu` and `consumer_cpu`. New unit test `RunnerQualification.
ActualCpuMigrationAcceptsSingleCpuSeriesBoundToProducerRole` covers both
the accepted single-CPU-on-producer-role case and a single-CPU-off-pair
negative case; `cpu_prefetch_runner_tests` (21/21, including all prior
cases) passes.

## Consequences

- No real hardware time is required beyond what a normal Q15-R session
  already uses -- this wires already-computed, already-real data, with no
  perturbation risk since nothing new was added to the measured path.
- Required a new C++ change to the compiled worker (recompiled release
  binary, new bundle profile, the reachability-lockstep dance this
  session has repeatedly had to complete for every new outer-policy
  generation) before this can be exercised for real on the stand -- not
  yet done, deferred pending explicit direction.
- Does not by itself unblock S17-EXT-004 admission: `ADDRESS_RESIDENCY`
  (ADR-0149) and `SELECTED_PAIR_CLOCK` (ADR-0150) remain unstarted, larger
  gaps. `RUNTIME_ATOMIC_LAYOUT` (ADR-0147) and `SOFTWARE_PREFETCH_MAPPING`
  (ADR-0152) are already implemented at the wiring level.
- This ADR's original "requires careful measured-path scoping" framing
  should not be assumed to generalize to ADR-0149/ADR-0150 without its
  own investigation; the favorable outcome here came specifically from
  `singleton_affinity`'s mask semantics, which do not obviously apply to
  residency or clock-pairing measurement.
