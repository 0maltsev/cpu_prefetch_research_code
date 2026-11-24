# ADR-0071: Select the exact collector-bearing no-authority P4-R release

- Status: `ACCEPTED_NO_STAND_OR_EXECUTION_AUTHORITY`
- Decision ID: D-071
- Accepted by: Q15-R-P4-E on 2026-08-25
- Classification: Q15-R-P4-R collector-release identity
- Owners: repository, build, platform, security, and audit owners
- Supersedes: no artifact; advances ADR-0069 with an immutable clean collector release
- Lifecycle gate: before literal collector-root selection, transfer/install,
  Q15-R-P4-R issuance, or stand-prestate collection

## Decision

Select clean commit `34da95d002e912069c959bfef8e88a23b4880cea` and
no-authority `Q15-QUALIFICATION-TOOL-BUNDLE-v3` archive SHA-256
`f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`
as the exact collector-release evidence input for a later separately
authorized Q15-R-P4-R transaction. The selection resolves only the clean
collector source/archive/manifest/SBOM/binary/contract-hash group. Seven P4-R
external inputs remain unresolved. P4-K remains byte-preserved, unissued, and
has all eight inputs unresolved.

Options considered were selecting the exact clean `34da95d` v3 release,
retaining the collector-free v2 release, building a different clean release,
or stopping. Only the exact v3 identity is accepted.

## Evidence and effects

The outer sidecar, 154-file clean extraction, complete internal inventory,
source archive, manifest, SBOM, collector, offline validator, accepted
collector contract, P4-D acceptance, controller/tool binaries, qualification
library, version metadata, all three strict code-generation reports, full
97-translation-unit static analysis, smoke, and nonprivileged preflight
self-test pass. The collector was not executed. The manifest grants authority
`NONE`.

Scientific effect is none: no platform value, schedule, treatment, outcome,
calibration, estimator, pilot, measurement, analysis, or confirmatory value is
selected. Compatibility effect is exact: every bound byte, hash, profile,
contract, and report becomes collector-release identity.

## Authority and supersession

This ADR authorizes only the versioned repository-local P4-R preparation. It
does not authorize stand access, literal-path selection, transfer/install,
filesystem mutation, collector execution, account/key/signature activity,
Q15-R-P4-R, Q15-R-P4-K, Q15-R, Q15-W, PMU/MSR/affinity/NUMA operations,
calibration, pilot, measurement, or confirmatory work.

Any changed byte, source revision, bundle profile, authority field, collector
contract, dependency, toolchain, validator, or report requires a new clean
release, complete verification, and prospective acceptance. The D-071
proposal, acceptance, original P4-R/P4-K preparations, and selected release
identity remain immutable.
