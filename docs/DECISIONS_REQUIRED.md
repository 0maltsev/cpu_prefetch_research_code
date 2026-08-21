# Decisions Required

Protocol version: **`2.0.0-pre.1`**

Stage 2/11 disposition: **`COMPLETE; Q1_THROUGH_Q9_ACCEPTED`**

The repository still contains no authorized production benchmark or
measurement runner. Stage 11 contains the accepted physical observation
writer and post-run storage boundary, not an authorized scientific run path.
Stage 5 contains queue correctness-only production cores, Stage 6 contains
deterministic workload-construction components, and Stage 7 contains offline
schedule generation/validation. Q1 through Q6 were accepted by the repository
owner on 2026-08-17; Q7 was accepted on 2026-08-20. They are recorded in
ADR-0007 through ADR-0031. Exact scientific/platform/pilot facts remain open until their
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
| Q5 deterministic workload bundle | Independent Philox4x32-10/HMAC-SHA-256 stream suite; unbiased Fisher-Yates; separated purpose domains; fixed consumer mixer and canonical content/order/delta inputs; explicit record/package representations | ADR-0025 through ADR-0028 | Concrete seeds, platform facts/capacities, page-frame qualification, retaining prefetch instructions, and calibrated per-context `d2` |
| Q6 deterministic schedule bundle | Offline Python Decimal80 exponential transform; exact midpoint Philox mapping; picosecond cumulative-floor absolute deadlines; fail-closed overflow; versioned artifact/decoded/envelope identities | ADR-0029 | Stage 7 implementation evidence passes; concrete seed, namespace, rate, origin, and horizon values remain later lifecycle inputs |
| Q7 Stage 8 clock bundle | vDSO `CLOCK_MONOTONIC_RAW`; exact nanosecond-to-picosecond conversion; compiler-only read boundaries; bracketed publication/observation; no correction; explicit qualification limits | ADR-0030 | Stage 8 software/generated-code pass; dynamic traced-vDSO/full-count evidence and an explicit eligible worker pair remain required |
| Q9 Stage 11 storage bundle | Exact fixed u64le literal-run-ID rows; JCS envelope; no compression; one temporary and two verified durable copies in explicit distinct domains | ADR-0032/0033 | Stage 11 software passes; concrete run-plan capacity, worker-page residency, real domains/custody, and operational recovery remain Phase 16 evidence |

## Stage 3 through Stage 8 engineering baselines

ADR-0022 accepts the constrained compiler/build/test/dependency/CI baseline and
records it as D-029. ADR-0023 accepts the dependency-free typed-model and
record-local validation implementation as D-030. Neither approves a scientific
algorithm, a target stand, or an experiment. Coverage remains unselected because
it is not required to start Stage 5; adding a coverage gate requires a later
engineering decision.

ADR-0024 accepts the exact independent queue representation, memory-order,
layout-input, claim, and refinement boundary as D-032. Development-host
unit/property/stress and sanitizer evidence passes. GNU Binutils 2.46 and LLVM
22.1.6 generated-code checks, mutants, and human review pass, so Phase 5 is
complete. Eligible-stand runtime layout/lock-free qualification remains later
platform evidence rather than a Phase 6 blocker.

Q5 and ADR-0025 through ADR-0028 accept D-011 through D-013 and D-033. Stage 6
implements their deterministic primitives, immutable event arena, linked-node
order, exact footprint arithmetic, five statically bound package mechanisms,
no-allocation prepared path, integrity grammars, and generated-code checks.
No development fixture is a qualified stand value or scientific outcome.

## Accepted Q6 — Stage 7 deterministic schedule suite

State: **`ACCEPTED`**.

The repository owner answered `Q6 - accept the bundle` on 2026-08-17.
[`docs/STAGE7_DECISION_BUNDLE.md`](STAGE7_DECISION_BUNDLE.md) and
[ADR-0029](decisions/0029-stage7-schedule-generation-suite.md) therefore select the
offline suite `POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1`:
midpoint mapping of one Philox draw per candidate, a fixed Python 3.14
80-digit decimal inverse transform, cumulative-floor picosecond deadlines,
absolute unsigned-64 big-endian storage, fail-closed overflow, and versioned
artifact/decoded/envelope SHA-256 identities. It uses the already-approved
Python standard library and adds no dependency.

The acceptance and implementation gates for Stage 7 are satisfied. Full
golden, decoder, semantic, corruption, namespace/common-family, append-only
publication, and completion-independence evidence passes. The decision does
not select concrete lifecycle inputs or authorize an experiment.

## Accepted Q7 — Stage 8 clock suite

State: **`ACCEPTED`**.

The repository owner answered `Q7 - accept the bundle` on 2026-08-20. The
final [D-009 bundle](STAGE8_CLOCK_DECISION_BUNDLE.md) and
[ADR-0030](decisions/0030-stage8-clock-suite.md) therefore select qualified vDSO
`CLOCK_MONOTONIC_RAW`, exact integer nanosecond-to-picosecond conversion,
compiler-only read boundaries, bracketed enqueue-publication/dequeue-observation
timestamps, no overhead correction, and fixed monotonicity, resolution,
read-cost, skew, drift, migration, syscall, and generated-code gates. Direct
TSC remains diagnostic-only for v1 because the supplied stand is dual-socket
and its CPUID ratio does not enumerate a crystal frequency.

Q7 supplies no worker CPU pair and does not treat static inventory as clock
qualification. Stage 8 implements the accepted reader, boundary map, exact
equations, no-correction diagnostic interface, qualification evaluators, and
dual-disassembler/source-mutant rules. Dynamic traced-vDSO, full-count,
affinity/source, selected-pair, and before-block evidence still must pass at
the applicable Phase 9/16 gates.

## Pre-pilot decisions that may remain open after Stage 2

| Decision IDs | Required choice/evidence | Owner | Blocking gate |
|---|---|---|---|
| D-009 | Software/codegen slice passes; supply exact release/stand identities, explicit pair, 10-million-call traced vDSO evidence, per-core full-count streams, bidirectional three-window streams, and before-block repetition | Timing/platform/queue-correctness/code-generation owners | Phase 9 platform qualification; repeat and bind by Phase 16/every block |
| D-010, D-020 | Decisions and Stage 11 software pass under Q9/ADR-0032/0033; remaining inputs are the concrete run plan, available bytes/reserve, actual worker-page residency, real two-domain durability/custody, and exact-release recovery proof | Storage/data-integrity/custody owners | Operational capacity/domain/residency/recovery proof by Phase 16 |
| D-008 | Queue pointer width/order/refinement and u32 release/acquire termination mapping are implemented; repeat runtime lock-free/layout probes and integrated generated-code checks on the eligible measured release. | Queue correctness/controller/platform owners | Controller mapping accepted in ADR-0031; stand/release evidence by Phase 16 |
| D-018 | Exact eligible-stand API mapping, processor-relax instruction, watchdog/failure bounds, capability/readback/probe/rollback evidence | Platform/controller owners | Supply treatment-blind operational evidence by Phase 16 |
| D-019 | Named operator/custodian, accounts/keys/storage, negative access, recovery, and audit retention | Security/custody owners | Operational proof by Phase 16; final authority before confirmation |
| D-031 | Q10 accepted the [Stage 12 decision bundle](STAGE12_D031_DECISION_BUNDLE.md); publish/supply the versioned protocol amendment containing the exhaustive blocker array and non-priority `BLOCKED_MULTIPLE` summary, then import and hash-verify it without modifying `2.0.0-pre.1` | Protocol/statistical owners for publication; repository owner for import | Amended snapshot import and traceability before Phase 12 final run-disposition validation |

These choices must be treatment-blind. Clock, remaining schedule inputs,
mixing, storage, and platform choices cannot be selected or revised because a
performance result is convenient.

## Confirmatory and submission gates

The protocol-defined open values listed at the end of
`docs/IMPLEMENTATION_DECISIONS.md` remain later work. They do not invalidate the
completed Stage 5/6 correctness evidence and must not be fabricated.
Submission identities, venue rules, accessibility, archive, and publication
license remain submission-only.

## Supersession rule

Accepted bundles can change only through new ADRs and full
compatibility/requalification evidence. Any replacement that changes
protocol-fixed scientific behavior stops the affected work and requires a
versioned protocol amendment. Stage 11's software slice is complete under
accepted D-010/D-020. The protocol and statistical owner accepted the
D-031/Q10 bundle on 2026-08-21. The exact next safe action is to publish or
supply the versioned amended protocol snapshot, then import and hash-verify it
before Stage 12 final-disposition work. Measurement, pilot, and confirmatory
execution remain prohibited.
