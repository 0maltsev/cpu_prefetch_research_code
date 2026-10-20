# ADR-0173: Stage 17 cpu-prefetch-v5 CPU-pair identity

- Status: `ACCEPTED`
- Date: 2026-10-20
- Decision ID: D-173
- Classification: platform-dependent topology mapping
- Decision owners: repository owner; platform, controller, timing, queue-correctness, storage, security, and custody owners at their later gates
- Protocol version: `2.0.0-pre.3`
- Supersedes: none; extends ADR-0043's pair-identity approach to a second, independently topology-verified stand. ADR-0043's own pair identity (`XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1`) remains valid under its own identity for the decommissioned stand it was verified against; it is not reused or relaxed here.
- Lifecycle gate: software topology proposal only; does not itself populate any CPU set or authorize any real MSR operation

## Context and scientific constraints

ADR-0172 (accepted, `docs/decisions/0172-...md`) registered a new hardware-prefetch-control mapping for CPUID family 6 model `0x3E` (Ivy Bridge-EP, the current real stand `cpu-prefetch-v5`), but deliberately left its CPU set unassigned (`std::nullopt` in `kHardwarePrefetchMappings`), fail-closing every code path that would need one. That ADR's own authority boundary is explicit that ADR-0043's pair-identity decision governs the CPU set separately, and that reusing ADR-0043's own `{0, 1, 26}` triple on different silicon without fresh topology evidence would be inventing a platform-dependent value. This ADR supplies that fresh evidence and proposes the resulting pair identity for `cpu-prefetch-v5`.

Real, read-only topology evidence gathered directly on `cpu-prefetch-v5` (94.126.205.83) this session, not assumed, and captured as the hashed, append-only evidence bundle `docs/evidence/stage17/STAND-TOPOLOGY-CPU-PREFETCH-V5-20261020-01/` (manifest SHA-256 `d1a1234d9b195a17e7765bfbf6100a3f62a1828ad94440df4ef5b5600da8af4c`, independently re-verified file-by-file against `SHA256SUMS` after transfer, not just trusted from the remote capture): `lscpu -e --json`, `lscpu --caches --json`, `numa-node{0,1}-cpulist`, and per-CPU `thread_siblings_list`/`physical_package_id`/`core_id`/LLC `shared_cpu_list` for CPUs 0, 1, and 8. Findings: the stand is dual-socket, 2 NUMA nodes (node 0 = CPUs 0-7,16-23; node 1 = CPUs 8-15,24-31), 16 physical cores with hyperthreading (32 logical CPUs total), one L3 (LLC) domain per socket. CPU 0's hyperthread sibling is CPU 16 (not CPU 1); CPU 0 and CPU 1 are distinct physical cores (`core_id` 1 and 2 respectively) sharing the same L3 `shared_cpu_list` (`0-7,16-23`) and the same `physical_package_id` (0) -- same NUMA/LLC/package domain. CPU 8 has a different `shared_cpu_list` (`8-15,24-31`) and a different `physical_package_id` (1) -- crosses package, NUMA, and LLC domains relative to CPU 0. `numactl --hardware` (captured separately, consistent with the bundle) confirms asymmetric NUMA distance (local 10, remote 21). CPUID identity re-confirmed from `/proc/cpuinfo`: family 6, model 62 (`0x3E`), stepping 4, matching ADR-0172's registered model exactly.

This provides no dynamic qualification or performance result, and authorizes no code change or real hardware operation.

## Options considered

- Worker pair: `(0,1)` near and `(0,8)` far, mirroring ADR-0043's own "keep producer home fixed, vary only the consumer by placement" convention; a different producer CPU; a different far CPU elsewhere in node 1; remain unresolved pending a dedicated topology study.
- Reuse ADR-0043's own pair identity unchanged (`{0,1,26}`) on the assumption the same logical CPU numbers mean the same thing on different silicon. Rejected: CPU 26 on `cpu-prefetch-v5` is a real, valid, online CPU (package 1, core_id 3, independently re-checked directly via `/sys/devices/system/cpu/cpu26/topology/{core_id,physical_package_id}` and `/sys/devices/system/cpu/cpu26/online`), so this wouldn't even fail loudly -- it would silently run a "far" measurement on a CPU chosen without this stand's own topology evidence behind it, precisely the hazard ADR-0172 was written to avoid.
- Block entirely pending a more exhaustive topology study (e.g. microbenchmark-validated cache-latency confirmation beyond sysfs topology). Rejected as the default path: sysfs topology evidence (NUMA node, physical package, LLC `shared_cpu_list`, core id, hyperthread siblings) is the same class of evidence ADR-0043 itself relied on for the original stand ("hashed read-only topology evidence"), not a lower standard.

## Decision

Propose pair identity `CPU-PREFETCH-V5-P0-NEAR-0-1-FAR-0-8-v1`: producer CPU 0 for both placements, consumer CPU 1 for `NEAR`, and consumer CPU 8 for `FAR`. This mirrors ADR-0043's own structure exactly (fixed producer home, placement-driven consumer) and changes only the concrete CPU numbers, backed by this stand's own real topology evidence rather than the prior stand's.

This ADR does not itself populate `kHardwarePrefetchMappings`'s `06_3EH` entry's `control_cpus`, nor authorize any real MSR read, write, probe, or restoration on `cpu-prefetch-v5`. Per ADR-0172's own authority boundary, that requires this ADR (or a revision of it) to be formally accepted first, followed by the exact hash-bound Q15 authorization ADR-0049/ADR-0172 already require.

## Evidence

- Hashed topology bundle `docs/evidence/stage17/STAND-TOPOLOGY-CPU-PREFETCH-V5-20261020-01/` and its verified manifest SHA-256, `d1a1234d9b195a17e7765bfbf6100a3f62a1828ad94440df4ef5b5600da8af4c` (every individual file independently re-verified against `SHA256SUMS` after transfer).
- ADR-0043 (prior stand's own pair-identity decision and methodology, extended here, not superseded).
- ADR-0172 (the mapping this pair identity would complete, once accepted).

No queue outcome, latency, throughput, calibration, pilot, or confirmatory observation selected this decision -- consistent with ADR-0043's own rule.

## Consequences and compatibility

The producer home remains fixed (CPU 0) while the placement factor changes the consumer context (CPU 1 near, CPU 8 far), exactly as ADR-0043 established. Pair-specific clock, affinity, address-residency, atomic, and platform qualification remain mandatory and have not been performed -- this ADR provides topology identity only, not dynamic qualification. Changing either CPU changes the pair identity and invalidates all pair-bound evidence, same as ADR-0043's own rule.

If accepted, the real code change this enables is narrow and already anticipated by ADR-0172's design: populate `kHardwarePrefetchMappings`'s `06_3EH` entry's `control_cpus` with `{0, 1, 8}`, removing the `HWP-CPU-SET-UNASSIGNED`/`S17-Q15R-CPU-SET` fail-closed gates for this model. No other code changes are implied -- the mapping ID, MSR address, mask, and H0/H1 semantics are already registered and unchanged.

## Verification and acceptance tests

- Exact near/far pair test for `cpu-prefetch-v5` (analogous to the existing `HardwarePrefetchMapping.RegistersIvyBridgeEpAsDistinctSiblingMapping`/`IvyBridgeEpFailsClosedOnMissingCpuSet` tests, which would need updating once a CPU set is populated).
- A real Q15-R/Q15-W qualification run on `cpu-prefetch-v5` using this pair is the actual dynamic evidence that would validate it, exactly as ADR-0043's own pair was validated by the original stand's first real Q15-R/Q15-W run, not by topology review alone.

## Rollback or supersession

Stop before any real MSR operation on any topology mismatch and retain diagnostic evidence. Never substitute another CPU on this stand without fresh topology evidence. A change needs a prospective superseding ADR, new identity, and complete pair-/runner-bound requalification; ADR-0043's own evidence remains valid under its own identity for the stand it was verified against.

## Protocol-amendment assessment

This selects a platform/engineering mapping at a delegated gate without changing the imported logical schedule, queue, timestamp, storage, lifecycle, or analysis semantics. No protocol amendment is required, consistent with ADR-0043's own assessment.

## Authority boundary

This document proposes a pair identity and the real topology evidence gathered to support proposing it; it does not itself approve the identity, authorize any code change, or authorize any real prestate read, privileged write, probe, or restoration on `cpu-prefetch-v5`. Acceptance by the real repository/platform/controller/security owners, followed by the real code change described under "Consequences and compatibility" and a real Q15-R/Q15-W qualification run, remain necessary before any real hardware operation under this mapping may proceed.

## Implementation note (post-acceptance)

Accepted and implemented: `include/cpu_prefetch/platform/platform.hpp` gained `kHardwarePrefetchControlCpusV5{0, 1, 8}`, and the `06_3EH` entry in `kHardwarePrefetchMappings` now carries it instead of `std::nullopt` -- the `HWP-CPU-SET-UNASSIGNED`/`S17-Q15R-CPU-SET` fail-closed paths no longer trigger for this model. No other file needed editing: the mapping ID, MSR address, mask, and H0/H1 semantics were already registered by ADR-0172, and `platform.hpp` is not hash-pinned by any historical admission-policy generation (confirmed by direct check before editing), so this change needed no re-pin ceremony. `tests/platform_model_test.cpp`'s two tests that asserted the prior unassigned state were updated to assert the real `{0,1,8}` set instead, and a new test exercises a full H0/H1 plan on this CPU set (mirroring the existing `06_55H` coverage) plus confirms a `06_55H`-shaped prestate (CPU 26 instead of 8) is still rejected for `06_3EH`. All pre-existing tests re-verified passing unmodified; full `qualification-schema-check` sweep and `protocol-check`/`schema-fixture-check`/`canonical-check`/`runner-schema-check` re-verified clean.

Still not done, matching this ADR's own authority boundary: no real Q15-R/Q15-W authorization or real MSR operation exists for `cpu-prefetch-v5` yet. A real Q15-R/Q15-W qualification run using this pair -- the actual dynamic evidence that would validate it -- remains a separate, not-yet-started piece of work, gated by the same exact hash-bound Q15 authorization and owner signature this engagement has required for every real hardware action.
