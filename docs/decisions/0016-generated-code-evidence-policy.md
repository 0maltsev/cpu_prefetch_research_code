# ADR-0016: Generated-code evidence policy

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Compiled-behavior verification
- Decision owners: Repository owner; code-generation reviewer; build owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 policy; tooling/rules implemented in Stage 3 and passed before pilot

## Context and scientific constraints

Correct source is insufficient if compilation removes/moves timestamp boundaries, record loads, checksum updates, prefetch hints, relaxation, atomics, or binding boundaries, or introduces prohibited calls.

## Options considered

1. Manual spot checks only.
2. Single-disassembler signatures.
3. Source-linked GNU and LLVM disassembly, machine rules, human review, and negative mutants.

## Decision

Adopt option 3. For every release queue/package specialization, bind source, object, executable, compiler, flags, standard library, linker, GNU objdump, llvm-objdump, rule set, human review, and report hashes. Machine checks and negative mutants must demonstrate detection capability.

## Evidence

The repository owner accepted Q2 on 2026-08-17. The protocol requires generated-code evidence for queue ordering, timestamp boundaries, prefetch sites, record work, and absence of distorting measured-path mechanisms.

## Consequences and compatibility

Scientific effect: detects compiled deviations without changing measured code. Compatibility effect: evidence is build-specific and must be regenerated after compiler/flag/source changes.

## Verification and acceptance tests

Rules cover queue publication/observation, prefetch site/target/form/distance, relax, termination, immutable loads, private mix, timestamp boundaries, binding, and prohibited calls. Mutants must move/remove/add representative operations and be rejected.

## Rollback or supersession

Tool migration requires a superseding record and negative-fixture parity. It cannot waive an unverified boundary.

## Protocol-amendment assessment

No amendment is required.
