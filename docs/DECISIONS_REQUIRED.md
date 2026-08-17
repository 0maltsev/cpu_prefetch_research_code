# Decisions Required

Protocol version: **`2.0.0-pre.1`**

Stage 2 disposition: **`Q1_Q2_Q3_ACCEPTED; SPDX_LICENSE_IDENTIFIER_PENDING`**

The repository still contains no production benchmark code. Q1, Q2, and Q3 were accepted by the repository owner on 2026-08-17 and are recorded in ADR-0007 through ADR-0020. Exact platform/pilot facts may remain open until their listed phases. One owner value is still required before Stage 2 can be marked complete.

## Remaining Stage 2 question

### Q4 — Repository source-license SPDX identifier

Q2 included and accepted this requirement: select the repository source license before production files are created. The protocol cannot supply that owner/legal decision, and the repository has no root license file.

**Required response:** provide the intended SPDX identifier, or explicitly choose a private/no-distribution posture and the text/record that should govern repository source.

**Owner:** repository owner.

**Gate:** sole blocker to Stage 2 completion and Stage 3 production files.

No license is recommended or inferred because licensing intent and ownership are external to the repository evidence.

## Accepted Stage 2 bundles

| Bundle | Accepted decisions | ADRs | Later evidence that remains validly open |
|---|---|---|---|
| Q1 software foundation | C++20; Linux x86-64; GCC 16.x/libstdc++ primary; Clang 22.x/libc++ secondary; CMake/Ninja offline builds; GoogleTest/RapidCheck/CTest/custom stress; no generic scientific-loop framework | ADR-0007 through ADR-0011 | Exact compiler/linker/flags/dependency pins and capability probes in Stage 3 |
| Q2 queue/process/atomic/integrity/correctness | One unprivileged process and two workers; non-dispatch binding; independent queues with no FastFlow source use; C++ atomic envelope; OpenSSL SHA/HMAC and `JCS-I64-v1`; generated-code and sanitizer policy | ADR-0012 through ADR-0017 | D-028 license now; exact atomic representation/proof Phase 5; exact consumer mixer Phase 6 |
| Q3 platform/custody boundary | External authorized control; replaceable Linux request/readback/probe/rollback interface; separate platform and validation principals with technical sealing | ADR-0018 through ADR-0020 | Exact stand/operator/API/register facts Phase 9; custody principals/enforcement by Phase 16/final confirmation |

## Pre-pilot decisions that may remain open after Stage 2

| Decision IDs | Required choice/evidence | Owner | Blocking gate |
|---|---|---|---|
| D-009 | Qualified clock source, conversion, serialization, skew/drift/read-cost bounds, and code evidence | Timing/platform owner | Select for Phase 8; pass by Phase 16 |
| D-010, D-020 | Physical raw format, exact row/envelope sizes, endianness, codec, compression/copy policy, capacity and corruption evidence | Storage owner | Select for Phase 11; pass by Phase 16 |
| D-011, D-012, D-027 | Exact RNG, derivation, unbiased permutation, exponential transform, tick rounding/overflow, and golden vectors | Reproducibility/statistical/timing owners | Select for Phases 6-7; pass by Phase 16 |
| D-013 | Exact consumer mixing and rolling/content/index/delta checksum byte formulas plus vectors and generated code | Consumer/protocol/integrity owners | Select for Phase 6; pass by Phase 16 |
| D-008 | Exact termination/control atomic width, complete happens-before/refinement proof, layout and lock-free platform evidence | Queue correctness/platform owners | Phase 5 queue acceptance |
| D-018 | Exact eligible-stand API mapping, processor-relax instruction, capability/readback/probe/rollback evidence | Platform owner | Select for Phase 9; pass by Phase 16 |
| D-019 | Named operator/custodian, accounts/keys/storage, negative access, recovery, and audit retention | Security/custody owners | Operational proof by Phase 16; final authority before confirmation |

These choices must be treatment-blind. Clock, schedule, mixing, storage, and platform choices cannot be selected or revised because a performance result is convenient.

## Confirmatory and submission gates

The protocol-defined open values listed at the end of `docs/IMPLEMENTATION_DECISIONS.md` remain later work. They do not block Stage 3 and must not be fabricated during Stage 2. Submission identities, venue rules, accessibility, archive, and publication license remain submission-only.

## Supersession rule

Accepted bundles can change only through new ADRs and full compatibility/requalification evidence. Any replacement that changes protocol-fixed scientific behavior stops the affected work and requires a versioned protocol amendment. Until D-028 is answered, the exact next safe activity is **Stage 2 repository-license selection only**.
