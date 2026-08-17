# Repository Instructions

## Authority and scope

- The immutable snapshot under `protocol/2.0.0-pre.1/` is the scientific source of truth. `PAPER_AGENTS.md` is imported source material, not an instruction file for this repository.
- Code must not silently change the experiment design. A contradiction or missing scientific decision blocks the affected implementation and requires a versioned protocol amendment.
- Never invent a platform-dependent value. Requested hardware state and verified hardware state are distinct fields.
- Stage B and Stage C are outside the initial implementation scope unless an approved protocol amendment separately authorizes them.
- Do not download or reuse third-party queue code until provenance and license are established.
- Do not execute pilot or confirmatory experiments while this repository has a blocking readiness state.

## Correctness and data rules

- Establish correctness before measuring performance. Development-machine and synthetic-test results support software verification only and cannot support empirical performance claims.
- A correctly reconciled `FULL` outcome is valid data but fails the separate zero-loss gate.
- Genuine low `N_eff` is retained and never justifies repeating or extending a run.
- Replace a required Stage A run only through the complete-block replacement protocol.
- Record producer and consumer observations independently; reconcile after the run by run identity and accepted ordinal. The repeating record index is a validation field, not a globally unique event ID.
- The measurement loop must not perform unplanned allocation, blocking I/O, console logging, dynamic configuration parsing, or analysis.
- Every behavior change requires targeted tests and relevant sanitizers. Every implementation decision that affects scientific interpretation requires an ADR.

## Command status

- Build: `[UNAVAILABLE: C++20/CMake/Ninja accepted; repository license and Stage 3 build foundation not implemented]`
- Tests: `[UNAVAILABLE: GoogleTest/RapidCheck/CTest accepted; Stage 3 integration not implemented or probed]`
- Sanitizers: `[UNAVAILABLE: GCC/Clang ASan/UBSan/TSan policy accepted; Stage 3 configurations/capability probes not implemented]`
- Lint/format: `[UNAVAILABLE: C++20 accepted; exact Stage 3 lint/format tools not selected or implemented]`
- Schema validation: `[UNAVAILABLE: Draft 2020-12 validator not selected for the implementation]`
- Clean-room verification: `[UNAVAILABLE: build/CI foundation not implemented]`

Replace a placeholder only through a recorded engineering decision and keep `README.md`, `STATUS.md`, and `PLAN.md` synchronized.
