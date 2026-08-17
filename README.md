# CPU Prefetch Research Code

This repository is the implementation-planning foundation for protocol **`2.0.0-pre.1`** of *Prefetching and Tail Latency in Lock-Free Inter-Core Queues: Effects of Access Pattern, Placement, and Offered Load*.

The repository currently contains no benchmark, queue implementation, hardware-control program, experiment runner, or analysis pipeline. Stage 1 has been reverified and the Stage 2 architecture boundaries are documented, but the recommended implementation stack has not been accepted. Its state is:

```text
STAGE_2_DOCUMENTED_AWAITING_ACCEPTANCE
BLOCKED_BEFORE_IMPLEMENTATION
```

The paper repository declares its structural handoff ready for implementation. This code repository is more conservative: initial coding remains blocked until Q1-Q3 in `docs/DECISIONS_REQUIRED.md` are explicitly accepted (or revised) and recorded as ADRs without inventing protocol behavior.

## Source of truth

The immutable imported protocol is in [`protocol/2.0.0-pre.1/`](protocol/2.0.0-pre.1/). Start with:

1. [`EXPERIMENT_IMPLEMENTATION_SPEC.md`](protocol/2.0.0-pre.1/EXPERIMENT_IMPLEMENTATION_SPEC.md);
2. [`PROTOCOL_FREEZE_CHECKLIST.md`](protocol/2.0.0-pre.1/PROTOCOL_FREEZE_CHECKLIST.md);
3. [`handoff/README.md`](protocol/2.0.0-pre.1/handoff/README.md) and its stated reading order;
4. [`docs/TRACEABILITY_MATRIX.md`](docs/TRACEABILITY_MATRIX.md) for implementation ownership and gates.

`protocol/2.0.0-pre.1/PAPER_AGENTS.md` records the paper repository's rules at import time. It is evidence, not an instruction file for this repository. The import manifest records source identity, byte sizes, hashes, compatibility, and verification results. No Git commit is recorded because the supplied source tree had no `.git` metadata.

## Planning documents

- [`STATUS.md`](STATUS.md): separate readiness states and immediate blockers.
- [`PLAN.md`](PLAN.md): dependency-ordered Stage A implementation plan.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): component boundaries and timed-path constraints.
- [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md): planned control, measurement, reconciliation, and access flows.
- [`docs/TRACEABILITY_MATRIX.md`](docs/TRACEABILITY_MATRIX.md): normative requirement ownership and validation gates.
- [`docs/IMPLEMENTATION_DECISIONS.md`](docs/IMPLEMENTATION_DECISIONS.md): fixed and open decisions by lifecycle boundary.
- [`docs/DECISIONS_REQUIRED.md`](docs/DECISIONS_REQUIRED.md): the minimum owner questions and later evidence gates.
- [`docs/TEST_STRATEGY.md`](docs/TEST_STRATEGY.md): future correctness and verification layers.
- [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md): scientific and engineering risks with stop conditions.
- [`docs/STAND_RUNBOOK.md`](docs/STAND_RUNBOOK.md): non-executable future stand procedure.
- [`docs/decisions/README.md`](docs/decisions/README.md): ADR policy, accepted Stage 2 ADR index, and template.

## Commands

The C++20/CMake/Ninja/toolchain/test matrix is a recommendation awaiting acceptance, so build, test, sanitizer, lint, implementation schema-validation, and clean-room commands intentionally remain explicit placeholders in `AGENTS.md`. Protocol-import integrity can be checked today with standard SHA-256 and JSON tools, but those ad hoc bootstrap checks are not presented as the future implementation commands.

## Scope boundary

Stage A is the only planned implementation scope. Stage B and Stage C are deferred future work and cannot fill a Stage A cell. The exact next safe activity is Stage 2 decision acceptance; no pilot or confirmatory execution is authorized.
