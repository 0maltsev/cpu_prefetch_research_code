# ADR-0055: Use fixed direct Linux acquisition mechanisms for Q15

- Status: `ACCEPTED_AND_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-055
- Classification: platform implementation and raw-observation acquisition
- Decision owners: platform, timing, compiler, security, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no accepted decision
- Lifecycle gate: before dynamic probe implementation and generated-code audit

## Context and options

D-052 fixes the event, scope, memory formula/policy, residency checks, fault
rule, timing role, and counted traversals. Considered implementations were
shell tools, new libpfm/libnuma dependencies, fixed direct Linux interfaces,
and runtime-selectable mechanisms.

## Decision

Select fixed direct Linux interfaces behind injected test seams, exactly as
specified in the [Q15-S3 bundle](../Q15_DYNAMIC_IMPLEMENTATION_DECISION_BUNDLE.md):

- exact pinned per-thread user-only raw `perf_event_open` event `0xf824`;
- singleton `sched_setaffinity` plus independent affinity/current-CPU reads;
- overflow-checked working-set formula, private anonymous `mmap`, exact
  `mbind(MPOL_BIND)`, `MADV_NOHUGEPAGE`, and target-CPU first touch;
- exhaustive `move_pages` snapshots before, between prime/count, and after;
- conservative `RUSAGE_THREAD` fault deltas around counter/traversal lifecycle;
- raw `CLOCK_MONOTONIC_RAW` diagnostics with no correction; and
- D-053 integrity outside the counted traversal.

There is no new runtime dependency, retry, fallback, arbitrary PMU event,
arbitrary CPU/node/policy selector, or empirical acceptance threshold.

## Evidence and effects

Evidence is D-052, the accepted Linux x86-64/dependency policy, and Q15-S3
owner acceptance. Scientific effect is only execution of the frozen
observation model. Every request field/order, mapping, fault/residency/timing
boundary, failure category, and generated instruction becomes compatibility
identity.

## Verification and supersession

Fake system-call tests pass every registered request field, order, failure, and
no-retry rule. GCC and Clang release objects pass both accepted disassemblers;
the registered extra-work mutants fail as required. Any mechanism or semantic
change requires a new ADR, clean release, and requalification; D-052 semantic
changes require formal supersession.
