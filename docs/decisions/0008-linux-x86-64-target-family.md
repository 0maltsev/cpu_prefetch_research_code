# ADR-0008: Linux x86-64 initial target family

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Platform scope
- Decision owners: Repository owner; platform owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 target-family choice; eligible stand due before Phase 9

## Context and scientific constraints

The target must support evidenced affinity, NUMA placement/residency, page policy, frequency state, qualified cross-core timing, and documented hardware-prefetcher control. A development machine may support correctness tests without qualifying for empirical work.

## Options considered

1. Linux x86-64 as the initial Stage A target.
2. Another evidenced NUMA OS/ISA target.
3. A portable multi-OS target from the outset.

## Decision

Support Linux x86-64 as the only initial Stage A target family. Other systems are development/correctness-only until a port ADR and equivalence suite are accepted. The exact eligible CPU/system, kernel, topology, and capabilities remain Phase 9 evidence; the observed one-NUMA-node development host is not eligible.

## Evidence

The repository owner accepted Q1 and Q3 on 2026-08-17. Linux exposes candidate affinity, NUMA, page, frequency, and timekeeping APIs. No eligible target inventory has yet been supplied.

## Consequences and compatibility

Scientific effect: establishes the prospective platform family without claiming a target population or verified state. Compatibility effect: non-Linux/non-x86 release artifacts are unsupported until separately qualified.

## Verification and acceptance tests

Stage 3 records compile/ABI assumptions; Phase 9 must reject an ineligible topology or missing control/readback capability and keep requested and verified state independent.

## Rollback or supersession

A later target-family ADR requires full capability, atomic, clock, generated-code, artifact, and platform-control requalification. Changing the frozen empirical platform population may also require protocol review.

## Protocol-amendment assessment

No amendment is required for this prospective initial target choice.
