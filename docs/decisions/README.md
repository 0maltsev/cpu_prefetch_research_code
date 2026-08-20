# Architecture Decision Records

Use an ADR for every engineering decision that can affect scientific interpretation, reproducibility, compatibility, data identity, the measured path, or a lifecycle gate. Recommendations in `docs/IMPLEMENTATION_DECISIONS.md` are not decisions until an approved ADR records them.

## Naming and status

Name records `NNNN-short-title.md`. Never rewrite the history of an accepted decision. If a decision changes, add a new ADR that supersedes the old one and identify whether a protocol amendment is also required.

Allowed statuses are `PROPOSED`, `ACCEPTED`, `REJECTED`, and `SUPERSEDED`. Only `ACCEPTED` freezes a choice.

## Template

```text
# ADR-NNNN: Title

- Status:
- Date:
- Decision owners:
- Protocol version:
- Supersedes:
- Lifecycle gate:

## Context and scientific constraints
## Options considered
## Decision
## Evidence
## Consequences and compatibility
## Verification and acceptance tests
## Rollback or supersession
## Protocol-amendment assessment
```

An ADR must not use confirmatory outcomes to settle an open decision. If the choice changes a protocol-fixed behavior, stop implementation and obtain a versioned protocol amendment first.

## Index

| ADR | Status | Decision |
|---|---|---|
| [ADR-0001](0001-plane-separation-and-timed-boundary.md) | `ACCEPTED` | Separate the benchmark data plane, experiment controller, and offline analysis; keep non-measurement work outside the timed loop. |
| [ADR-0002](0002-logical-model-and-replaceable-physical-storage.md) | `ACCEPTED` | Preserve the imported logical data model behind replaceable codec and storage interfaces. |
| [ADR-0003](0003-semantics-preserving-queue-adapters.md) | `ACCEPTED` | Use queue adapters without erasing algorithm-specific semantics. |
| [ADR-0004](0004-artifact-versioning-and-compatibility.md) | `ACCEPTED` | Version physical formats and reject unknown or incompatible artifacts. |
| [ADR-0005](0005-append-only-partial-failure-lifecycle.md) | `ACCEPTED` | Make append-only artifacts and partial failures first-class. |
| [ADR-0006](0006-structural-and-semantic-validation.md) | `ACCEPTED` | Separate Draft 2020-12 structural validation from cross-record semantic validation. |
| [ADR-0007](0007-cpp20-implementation-language.md) | `ACCEPTED` | Use C++20 for the data plane and controller-facing core. |
| [ADR-0008](0008-linux-x86-64-target-family.md) | `ACCEPTED` | Limit the initial Stage A target family to Linux x86-64. |
| [ADR-0009](0009-primary-and-secondary-toolchains.md) | `ACCEPTED` | Use GCC/libstdc++ primary and Clang/libc++ secondary toolchain families. |
| [ADR-0010](0010-cmake-ninja-and-offline-dependencies.md) | `ACCEPTED` | Use CMake/Ninja with offline, hash/license-locked dependencies and no generic framework scientific loop. |
| [ADR-0011](0011-test-frameworks-and-scientific-harness-boundary.md) | `ACCEPTED` | Use GoogleTest, RapidCheck, CTest, and repository-owned concurrency/stress harnesses. |
| [ADR-0012](0012-process-thread-and-queue-binding-model.md) | `ACCEPTED` | Use one unprivileged process, two workers, a quiescent controller, and non-dispatch queue binding. |
| [ADR-0013](0013-independent-queue-implementation-and-provenance.md) | `ACCEPTED` | Independently implement both queues without importing/adapting FastFlow source. |
| [ADR-0014](0014-cpp-atomic-and-memory-order-envelope.md) | `ACCEPTED` | Use the C++ release/acquire and lock-free/layout evidence envelope. |
| [ADR-0015](0015-sha-hmac-and-exact-integer-canonicalization.md) | `ACCEPTED` | Use OpenSSL SHA/HMAC and exact-integer `JCS-I64-v1` canonicalization. |
| [ADR-0016](0016-generated-code-evidence-policy.md) | `ACCEPTED` | Require dual-disassembler generated-code rules, review, hashes, and negative mutants. |
| [ADR-0017](0017-sanitizer-and-correctness-acceptance.md) | `ACCEPTED` | Require zero unresolved sanitizer/correctness findings with controlled exceptions. |
| [ADR-0018](0018-unprivileged-measurement-and-control-boundary.md) | `ACCEPTED` | Keep measurement unprivileged and platform control externally authorized/audited. |
| [ADR-0019](0019-linux-platform-control-interface.md) | `ACCEPTED` | Use a replaceable Linux request/readback/probe/rollback platform interface. |
| [ADR-0020](0020-platform-and-validation-custody-separation.md) | `ACCEPTED` | Separate platform operation from technically enforced validation custody. |
| [ADR-0021](0021-no-repository-license-grant.md) | `ACCEPTED` | Record the owner's no-license posture without adding a `LICENSE` or SPDX grant. |
| [ADR-0022](0022-stage3-tooling-and-dependency-baseline.md) | `ACCEPTED` | Constrain the offline Stage 3 tool, dependency, test, CI, metadata, and package baseline. |
| [ADR-0023](0023-stage4-typed-model-and-validation-boundary.md) | `ACCEPTED` | Use imported-schema structural validation plus a strict typed C++ model, record-local semantic rules, and shared `JCS-I64-v1` fixtures. |
| [ADR-0024](0024-stage5-queue-representation-and-refinement.md) | `ACCEPTED` | Independently map the fixed ring and linked/recycler algorithms to direct C++20 adapters with exact release/acquire, layout, lock-free, and refinement boundaries. |
| [ADR-0025](0025-philox-hmac-stream-suite.md) | `ACCEPTED` | Use independent Philox4x32-10 streams with length-prefixed OpenSSL HMAC-SHA-256 domain derivation. |
| [ADR-0026](0026-unbiased-permutation-and-payload-domains.md) | `ACCEPTED` | Use descending Fisher-Yates with unbiased rejection and separate order, payload, and consumer-state domains. |
| [ADR-0027](0027-consumer-mixer-and-canonical-integrity-inputs.md) | `ACCEPTED` | Freeze the branch-free 64-bit consumer mixer and domain-separated canonical SHA-256 inputs. |
| [ADR-0028](0028-stage6-record-and-package-representation.md) | `ACCEPTED` | Use explicit line-strided immutable records and distinct statically bound Stage A package policies while leaving platform facts unresolved. |
| [ADR-0029](0029-stage7-schedule-generation-suite.md) | `ACCEPTED` | Use an offline Python-decimal exponential schedule suite with exact Philox mapping, picosecond cumulative-floor deadlines, absolute encoding, and fail-closed identities. |
| [ADR-0030](0030-stage8-clock-suite.md) | `ACCEPTED` | Use qualified vDSO `CLOCK_MONOTONIC_RAW`, exact nanosecond-to-picosecond conversion, bracketed queue boundaries, no correction, and explicit clock acceptance limits. |

Open later-gate scientific and platform decisions are kept in `docs/IMPLEMENTATION_DECISIONS.md` and `docs/DECISIONS_REQUIRED.md`; they do not become frozen merely by being documented. Q7 accepted ADR-0030 on 2026-08-20; its implementation and qualification evidence remain later gates.
