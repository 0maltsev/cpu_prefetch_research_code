# Decisions Required

Protocol version: **`2.0.0-pre.1`**

Stage 2 disposition: **`COMPLETE; Q1_Q2_Q3_Q4_ACCEPTED`**

The repository still contains no production benchmark or measurement code.
Stage 5 contains queue correctness-only production cores. Q1 through Q4 were
accepted by the repository owner on 2026-08-17 and are recorded in ADR-0007
through ADR-0021. Exact scientific/platform/pilot facts remain open until their
listed phases; they were not replaced by Stage 3 or Stage 4 engineering
defaults.

## Resolved Stage 2 question

### Q4 — Repository source-license posture

The repository owner selected **no license**. ADR-0021 records no license grant, no `LICENSE` file, and no repository-authored SPDX license claim. Third-party dependency licenses remain separate provenance records.

**Gate result:** resolved before Stage 3 source was created. Use, copying, modification, and distribution remain unauthorized unless a later owner-approved ADR grants a license.

## Accepted Stage 2 bundles

| Bundle | Accepted decisions | ADRs | Later evidence that remains validly open |
|---|---|---|---|
| Q1 software foundation | C++20; Linux x86-64; GCC 16.x/libstdc++ primary; Clang 22.x/libc++ secondary; CMake/Ninja offline builds; GoogleTest/RapidCheck/CTest/custom stress; no generic scientific-loop framework | ADR-0007 through ADR-0011 | Stage 3 baseline/probes are D-029; exact measured-release lock remains pre-pilot |
| Q2 queue/process/atomic/integrity/correctness | One unprivileged process and two workers; non-dispatch binding; independent queues with no FastFlow source use; C++ atomic envelope; OpenSSL SHA/HMAC and `JCS-I64-v1`; generated-code and sanitizer policy | ADR-0012 through ADR-0017 | Exact atomic representation/proof Phase 5; exact consumer mixer Phase 6 |
| Q3 platform/custody boundary | External authorized control; replaceable Linux request/readback/probe/rollback interface; separate platform and validation principals with technical sealing | ADR-0018 through ADR-0020 | Exact stand/operator/API/register facts Phase 9; custody principals/enforcement by Phase 16/final confirmation |
| Q4 repository license | No repository license grant; no `LICENSE` file or repository SPDX claim | ADR-0021 | Any later license grant needs owner/legal/compatibility review |

## Stage 3 through Stage 5 engineering baselines

ADR-0022 accepts the constrained compiler/build/test/dependency/CI baseline and
records it as D-029. ADR-0023 accepts the dependency-free typed-model and
record-local validation implementation as D-030. Neither approves a scientific
algorithm, a target stand, or an experiment. Coverage remains unselected because
it is not required to start Stage 5; adding a coverage gate requires a later
engineering decision.

ADR-0024 accepts the exact independent queue representation, memory-order,
layout-input, claim, and refinement boundary as D-032. Development-host
unit/property/stress and sanitizer evidence passes. Phase 5 nevertheless
remains open because the provisioned toolset lacks ADR-0016's accepted LLVM 22
`llvm-objdump`; GNU evidence alone is retained as partial, not accepted as a
substitute.

## Pre-pilot decisions that may remain open after Stage 2

| Decision IDs | Required choice/evidence | Owner | Blocking gate |
|---|---|---|---|
| D-009 | Qualified clock source, conversion, serialization, skew/drift/read-cost bounds, and code evidence | Timing/platform owner | Select for Phase 8; pass by Phase 16 |
| D-010, D-020 | Physical raw format, exact row/envelope sizes, endianness, codec, compression/copy policy, capacity and corruption evidence | Storage owner | Select for Phase 11; pass by Phase 16 |
| D-011, D-012, D-027 | Exact RNG, derivation, unbiased permutation, exponential transform, tick rounding/overflow, and golden vectors | Reproducibility/statistical/timing owners | Select for Phases 6-7; pass by Phase 16 |
| D-013 | Exact consumer mixing and rolling/content/index/delta checksum byte formulas plus vectors and generated code | Consumer/protocol/integrity owners | Select for Phase 6; pass by Phase 16 |
| D-008 | Queue pointer width/order/refinement is implemented; repeat runtime lock-free/layout probes on the eligible stand. Termination/control atomic width remains a later controller mapping. | Queue correctness/platform owners | Eligible stand/controller acceptance; queue core mapping accepted in ADR-0024 |
| D-018 | Exact eligible-stand API mapping, processor-relax instruction, capability/readback/probe/rollback evidence | Platform owner | Select for Phase 9; pass by Phase 16 |
| D-019 | Named operator/custodian, accounts/keys/storage, negative access, recovery, and audit retention | Security/custody owners | Operational proof by Phase 16; final authority before confirmation |
| D-031 | Protocol-authorized representation or precedence when two or more validity/zero-loss/effective-tail/completeness/access blockers coexist | Protocol/statistical owners | Resolve before Phase 12 final run-disposition validation |

These choices must be treatment-blind. Clock, schedule, mixing, storage, and platform choices cannot be selected or revised because a performance result is convenient.

## Confirmatory and submission gates

The protocol-defined open values listed at the end of
`docs/IMPLEMENTATION_DECISIONS.md` remain later work. They do not block Stage 5
queue-only correctness work where that phase can remain independent of them,
and must not be fabricated. Submission identities, venue rules, accessibility,
archive, and publication license remain submission-only.

## Supersession rule

Accepted bundles can change only through new ADRs and full
compatibility/requalification evidence. Any replacement that changes
protocol-fixed scientific behavior stops the affected work and requires a
versioned protocol amendment. The exact next safe activity is to provision the
accepted LLVM 22 `llvm-objdump`, rerun and review `queue-codegen-check`, and
close Stage 5. Phase 6 must not start while that accepted gate is missing.
