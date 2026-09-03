# 0150. Stage 17 S17-EXT-004 selected-pair-clock real invocation

Status: PROPOSED

## Context

S17-EXT-004's `SELECTED_PAIR_CLOCK` qualification-evidence kind requires
(`config/schemas/qualification-evidence-v1.schema.json`'s `clock_
details`) real per-core and cross-core clock-pairing measurements:
`producer_prime_read_count`, `consumer_prime_read_count`, `producer_
delta_count`, `consumer_delta_count`, `traced_call_count`, `traced_
syscall_count`, `producer_to_consumer_window_count`, `consumer_to_
producer_window_count`, `exchanges_per_window`, `per_core_evaluator_
passed`, `cross_core_evaluator_passed`, `before_block_repeat`.

This is the deepest gap of the five kinds. `include/cpu_prefetch/
runner/qualification.hpp`'s `make_selected_pair_clock_evidence` (`src/
runner/qualification.cpp`) does not itself measure anything: it only
checks that a *supplied* `SelectedPairClockInput` matches frozen
constants (`timing::kQualificationPrimeReadCount`, `kQualificationDelta
Count`, `kCrossCoreWindowCount`, `kCrossCoreExchangeCountPerWindow`) --
the same pure-validator pattern as the `cpu_prefetch_qualification` CLI
tool (`docs/PRODUCTION_RUNNER.md`: "It validates only supplied values
... It cannot read or write an MSR, collect stand evidence, or grant
authority").

The actual measurement machinery is Stage 8's separate `timing::
qualification` subsystem (`include/cpu_prefetch/timing/qualification.hpp`,
`src/timing/qualification.cpp`: `PerCoreQualificationInput/Evidence`,
`CrossCoreWindowInput/Evidence`, `CrossCorePairInput/Evidence`). Its
*only* caller anywhere in the repository is `tests/timing_model_test.cpp`
-- no production binary, no CLI tool, and no path from the real Q15-R
worker ever invokes it. This subsystem has never run against real stand
hardware; it exists purely as unit-tested library code against synthetic/
mock backends.

Unlike ADR-0147/0148/0149, this is not primarily a C++ change to the
Q15-R worker's own measured path -- it is standing up an entirely new,
first-ever real invocation of a previously test-only subsystem, tied to
the already-frozen CPU-pair selection (`XEON-CPU-FETCH-P0-NEAR-0-1-FAR-
0-26-v1`, `docs/PRODUCTION_RUNNER.md`).

## Decision (proposed)

Before any implementation: determine, as its own scoping question, (a)
whether this clock-pairing qualification is meant to run once per
selected pair (i.e. a one-time qualification of the frozen `NEAR`/`FAR`
pair, independent of any specific Q15-R session) or per Q15-R session,
and (b) what real backend (perf counters, `clock_gettime`, a dedicated
IPC/tracing mechanism) `PerCoreQualificationInput`/`CrossCoreWindowInput`
are meant to be populated from on real hardware -- `src/timing/
qualification.cpp`'s own real backend requirements need auditing before
any real-stand time is spent. Only after that scoping should a real
invocation path (new CLI tool, or integration into the Q15-R worker
itself) be designed and built.

## Consequences

- This is real, separate scientific/engineering work -- not a wiring
  task like ADR-0147, and larger than the instrumentation work in
  ADR-0148/0149. It should not be scheduled as a quick follow-up to the
  other three.
- Requires new real-stand time distinct from a normal Q15-R session,
  once the invocation path exists.
- Blocks S17-EXT-004 admission independent of whether ADR-0147/0148/0149
  are completed -- all five `QUALIFICATION_EVIDENCE` kinds are required,
  so S17-EXT-004 cannot be built until this is resolved too.
