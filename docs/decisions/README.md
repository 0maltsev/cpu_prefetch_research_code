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
| [ADR-0031](0031-stage10-lifecycle-and-termination-mapping.md) | `ACCEPTED` | Project explicit controller phases onto the unchanged imported lifecycle enum and use a dedicated lock-free u32 release/acquire termination word. |
| [ADR-0032](0032-stage11-physical-raw-observation-format.md) | `ACCEPTED` | Use exact little-endian physical rows with literal length-prefixed run IDs, raw/relative clock pairs, and a JCS external-artifact envelope. |
| [ADR-0033](0033-stage11-compression-copy-and-durability-policy.md) | `ACCEPTED` | Use no compression, one temporary raw work image, and two byte-identical verified durable instances in distinct explicit domains. |
| [ADR-0034](0034-stage12-d031-amendment-and-exact-reconciliation.md) | `ACCEPTED` | Import D-031 as protocol 2.0.0-pre.2, preserve frozen derivation domains, and implement exact ordered reconciliation plus exhaustive independent run gates. |
| [ADR-0035](0035-stage13-service-rate-lower-limit.md) | `ACCEPTED` | Use a distribution-free 95%/95% sample-minimum lower tolerance limit over prospectively enumerated independent service-calibration runs. |
| [ADR-0036](0036-stage13-matrix-zero-loss-feasibility.md) | `ACCEPTED` | Use simultaneous independent-run-cluster weighted Hoeffding bounds, `pi_matrix=0.95`, and the accepted five-scale global load action. |
| [ADR-0037](0037-stage13-ring-distance-calibration.md) | `ACCEPTED` | Use ring-off advancing-slot p99.9/p0.1 run-tail calibration, conservative marginal H0/H1 merges, and exact line/minimum/cap rules. |
| [ADR-0038](0038-stage13-calibration-records-arithmetic-and-invalidation.md) | `ACCEPTED` | Use versioned canonical calibration records, exact arithmetic plus outward-rounded Decimal margins, and append-only invalidation. |
| [ADR-0039](0039-stage13-decimal-and-record-profile.md) | `ACCEPTED` | Freeze the concrete Decimal80/guard160 upward-enclosure profile and five Stage 13 record-schema identities. |
| [ADR-0040](0040-stage14-planning-access-and-replacement-profile.md) | `ACCEPTED` | Freeze the deterministic full-factorial planning, precision registry, access-ledger, and complete-block replacement compatibility profile. |
| [ADR-0041](0041-stage15-offline-analysis-profile.md) | `ACCEPTED` | Freeze the synthetic offline-analysis execution, complete-block max-T, H3 chronology, and canonical-report compatibility profile. |
| [ADR-0042](0042-stage16-verification-and-stand-bundle-profile.md) | `ACCEPTED` | Freeze the deterministic preflight-only source/release/protocol/schema/SBOM/provenance/checksum bundle and read-only inventory boundary. |

Open later-gate scientific and platform decisions are kept in `docs/IMPLEMENTATION_DECISIONS.md` and `docs/DECISIONS_REQUIRED.md`; they do not become frozen merely by being documented. Q7 accepted ADR-0030 on 2026-08-20; its implementation and qualification evidence remain later gates. ADR-0031 implements protocol-fixed Stage 10 behavior and the previously open termination mapping without selecting watchdog, recovery, relax, or stand values.
Q9 accepted ADR-0032 and ADR-0033 on 2026-08-21. Stage 11 codec, corruption,
checked-budget, no-allocation, sanitizer, code-generation, append-only store,
and local crash-recovery evidence passes. Concrete run-plan capacity, page
residency, real independent durability domains/custody, and exact-release
operational recovery remain Phase 16 gates.
Q10 and Q11 accepted D-031 and authorized the immutable `2.0.0-pre.2`
snapshot plus Stage 12 implementation. ADR-0034 records the version boundary,
exact join, and non-priority blocker semantics; Stage 14 still owns block and
access-history validation.

Q12 accepted D-035 through D-038 on 2026-08-21. The exact Stage 13 calibration
methods and record boundary are documented in
`../STAGE13_CALIBRATION_DECISION_BUNDLE.md` and ADR-0035 through ADR-0038.
ADR-0039 records the delegated concrete arithmetic/schema implementation
profile, whose synthetic conformance suite passes. Q12 supplies no stand,
duration, count, seed, capacity, authority, budget, `mu_ref`, `d2`, or final
matrix exposure and authorizes no calibration or performance execution.

ADR-0040 implements only protocol-fixed/delegated Stage 14 software seams. It
does not freeze external block counts, seed values, authorities, budget, stand
identity, or any pilot output and grants no execution authority.

ADR-0041 implements the Stage 15 synthetic analysis profile without supplying
`delta_star`, bootstrap/count/seed values, authorities, platform evidence, or
outcomes. Its compact fixtures and reports are not empirical artifacts and
grant no pilot or confirmatory authority.

ADR-0042 records the deterministic Stage 16 verification and stand-preflight
bundle profile. It packages source, release foundations, protocol, schemas,
validators, provenance, SBOM/licenses, checksums, and the runbook while
explicitly granting no platform mutation, pilot, or confirmatory authority.
