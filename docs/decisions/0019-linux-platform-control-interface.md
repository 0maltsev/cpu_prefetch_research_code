# ADR-0019: Linux platform-control interface

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Platform API architecture
- Decision owners: Repository owner; platform owner; operator
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 interface; exact stand mapping/evidence due in Phase 9

## Context and scientific constraints

Stage A requires commanded and independently verified CPU affinity, near/far page residency, page mode, frequency state, and one documented changed HW-prefetcher state. Platform-dependent values and vendor registers cannot be invented.

## Options considered

1. Direct platform calls scattered through controller/data-plane code.
2. External shell commands without structured evidence.
3. A replaceable Linux adapter with separate request, readback, probe, and rollback operations.

## Decision

Adopt option 3. Candidate mappings are affinity through `pthread_setaffinity_np`/`sched_setaffinity` plus actual-CPU verification; NUMA placement through `mbind`/`set_mempolicy` or libnuma plus `move_pages`/`/proc` residency evidence; base-page/THP request plus `smaps`-style verification; cpufreq sysfs request/readback; and vendor-specific HW-PF controls only after exact target manuals, fields, authority, readback, behavioral probes, and rollback are recorded.

The exact target CPU/system, kernel, API availability, register mapping, values, and permissions remain Phase 9 evidence.

## Evidence

The repository owner accepted Q3 on 2026-08-17. Official Linux documentation establishes candidate APIs; the local one-node development host does not establish near/far eligibility.

## Consequences and compatibility

Scientific effect: provides the interface for treatments/placement without claiming actual state. Compatibility effect: Linux-specific adapters are replaceable, while capability failure blocks rather than silently degrades.

## Verification and acceptance tests

Phase 9 tests capability/permission negatives, requested/verified separation, actual CPU, before/during/after residency, topology, page mode, frequency, exact HW-PF readback/probes, environmental state, and rollback.

## Rollback or supersession

A platform adapter or target mapping change requires a superseding ADR and full capability/readback/probe/rollback requalification. No generic “disabled” or “local” label may substitute for evidence.

## Protocol-amendment assessment

No amendment is required for the replaceable mapping; changing scientific state semantics would require review/amendment.
