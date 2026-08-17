# Decisions Required

Protocol version: **`2.0.0-pre.1`**

Stage 2 disposition: **`BLOCKED_PENDING_EXPLICIT_ACCEPTANCE`**

Nothing in this file is a default. The repository contains no production benchmark code, and Stage 3 must not start until the Stage 3-entry questions below have explicit answers and accepted ADRs. Target/pilot questions may remain open while build infrastructure is developed, but they block the stated later gate.

## Smallest decision set needed to finish Stage 2

### Q1 — Accept or revise the software foundation bundle

May the repository freeze this bundle?

- C++20 for the data plane and controller-facing core.
- Linux x86-64 as the only initial Stage A target family; other systems are correctness/development-only until port-qualified.
- GCC 16.x with libstdc++ as primary and Clang 22.x with libc++ as secondary; no mixed-standard-library object link; exact patch versions, linker, flags, and presets pinned in Stage 3.
- CMake plus Ninja with network-disabled builds and hash/license-locked dependencies.
- GoogleTest for unit tests, RapidCheck after a compatibility probe for property tests, CTest orchestration, and repository-owned refinement/stress executables.
- No Google Benchmark or other framework control loop for the scientific harness; such tools may only support clearly labeled developer microtests.
- GoogleTest/RapidCheck are test-only dependencies; no third-party code enters the timed data plane.

**Recommended answer:** accept the bundle, or list edits by D-001 through D-005.

**Owner:** repository owner.

**Gate:** blocks Stage 3 build/CI and all production source.

### Q2 — Accept or revise the queue, process, atomic, integrity, and correctness bundle

May the repository freeze this bundle?

- Independently implement both protocol queue packages from the cited Torquati report plus frozen protocol, with no FastFlow queue source imported, adapted, or mechanically translated.
- Record the author-maintained FastFlow repository as an official-artifact search result only; do not claim it is the exact historical paper artifact. Reuse/adaptation remains prohibited unless a later provenance ADR establishes the exact artifact, hash, applicable license, and semantic map.
- Select a repository source license before files are created. This license is not inferable from protocol evidence; supply the SPDX identifier.
- One unprivileged measurement process, a quiescent controller main thread, and exactly one producer plus one consumer worker; privileged control and validation custody remain out of process.
- Compile/link-time or separate-binary queue binding with no measured-path virtual dispatch or treatment-dependent selection branch; generated-code evidence must prove the accepted realization.
- C++ `std::atomic` pointer/control handoffs using the protocol's release/acquire mapping, with relaxed operations only where a written ownership/happens-before proof permits them; platform-derived cache-line separation; compile-time and runtime lock-free rejection; no lock-free/wait-free claim beyond the reviewed SPSC try operations and fixed-arena recycler.
- OpenSSL 3 EVP SHA-256/HMAC-SHA-256 for artifact identity and seed derivation, with the proposed exact-integer `JCS-I64-v1` canonical suite and cross-tool vectors.
- Source-linked dual-disassembler generated-code evidence, zero unresolved ASan/UBSan/TSan findings on supported matrices, and no suppression without a scoped reviewed record and compensating evidence.

**Recommended answer:** accept, provide a repository SPDX license, or list edits by D-006 through D-008 and D-014/D-016/D-017.

**Owner:** repository owner, then named queue/correctness owners.

**Gate:** queue/process/identity decisions block Stage 3 production architecture; provenance/memory details also block Phase 5 queue work. The exact consumer mixing formula remains a separate pre-pilot decision because it changes measured instructions.

### Q3 — Accept or revise the platform and custody boundary, then identify evidence owners

May the repository freeze this boundary?

- The measurement process is unprivileged.
- A replaceable Linux adapter uses affinity plus actual-CPU verification; NUMA placement plus independent residency evidence; base-page/THP request plus `smaps`-style verification; cpufreq request/readback; and vendor-specific HW-PF controls only after the exact target manual/register map, least-privilege authorization, readback, behavioral probes, and rollback are recorded.
- Requested and verified hardware state remain independent. Missing capability or authority blocks; it never silently degrades.
- Platform operation and validation custody use separate principals. Validation artifacts are technically inaccessible until the imported access state permits them.

Also identify, now or as an explicitly open Phase 9 input:

1. the intended multi-NUMA target CPU/system and Linux distribution/kernel;
2. the platform-control/operator owner and allowed privilege mechanism;
3. the validation custodian and storage/access enforcement boundary.

The local development host (`x86_64`, AMD Ryzen 5 5500U, one NUMA node as observed on 2026-08-17) is correctness-only and cannot establish near/far placement eligibility.

**Recommended answer:** accept the interface boundary; provide known owner/stand facts and mark genuinely unavailable facts open for Phase 9.

**Owner:** repository owner, institutional platform owner, validation custodian.

**Gate:** interface/separation acceptance blocks Stage 3 completion; the actual eligible stand and enforcement proof block Phase 9 platform control and Phase 16/17 pre-pilot/pilot readiness.

## Pre-pilot decisions that may remain open after Stage 2

| Decision IDs | Required choice/evidence | Owner | Blocking gate |
|---|---|---|---|
| D-009 | Qualified clock source, conversion, serialization, skew/drift/read-cost bounds, and code evidence | Timing/platform owner | Select for Phase 8; pass by Phase 16 pre-pilot readiness |
| D-010, D-020 | Physical raw format, exact row/envelope sizes, endianness, codec, compression/copy policy, capacity and corruption evidence | Storage owner | Select for Phase 11; pass by Phase 16 |
| D-011, D-012, D-027 | Exact RNG, derivation, unbiased permutation, exponential transform, tick rounding/overflow, and golden vectors | Reproducibility/statistical/timing owners | Select for Phases 6-7; pass by Phase 16 |
| D-013 | Exact consumer mixing and rolling/content/index/delta checksum byte formulas plus vectors and generated code | Consumer/protocol/integrity owners | Select for Phase 6; pass by Phase 16 |
| D-018 | Exact eligible-stand API mapping, processor relax instruction, capability/readback/probe/rollback evidence | Platform owner | Select for Phase 9; pass by Phase 16 |
| D-019 | Named operator/custodian, accounts/keys/storage, negative access, recovery, and audit retention | Security/custody owners | Architecture names before Stage 3 completion; operational proof by Phase 16; final authority before confirmation |

These choices must be treatment-blind. Clock, schedule, mixing, storage, and platform choices cannot be selected or revised because a performance result is convenient.

## Confirmatory and submission gates

The protocol-defined open values listed at the end of `docs/IMPLEMENTATION_DECISIONS.md` remain Stage 6-8 work. They do not block Stage 3 and must not be fabricated during Stage 2. Submission identities, venue rules, accessibility, archive, and publication license remain submission-only.

## Response and supersession rule

An answer may accept a whole bundle or cite individual D-IDs with replacements. Acceptance will be captured in new ADRs without rewriting the six accepted architectural ADRs. Any replacement that changes protocol-fixed scientific behavior stops the affected work and requires a versioned protocol amendment. Until Q1-Q3 are answered, the exact next safe activity is **Stage 2 decision review/acceptance only**.
