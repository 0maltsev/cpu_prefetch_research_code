# ADR-0065: Select the exact adapter-bearing no-authority Q15-R release

- Status: `ACCEPTED_NO_STAND_OR_EXECUTION_AUTHORITY`
- Decision ID: D-065
- Accepted by: Q15-R-P3 on 2026-08-25
- Classification: Q15-R operational-release identity
- Owners: repository, build, controller, security, and audit owners
- Supersedes: no artifact; advances ADR-0061 and ADR-0062 with a new immutable release identity
- Lifecycle gate: before stand-setup authorization and Q15-R issuance

## Decision

Select clean commit `c8b69abf0c6aec7b740efe78d998a93545302a94` and
no-authority archive SHA-256
`8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01`
as the exact operational-release evidence input for a later separately
authorized stand-setup transaction. The selection resolves only the release
artifact group. The five external path, custody, prestate, and signer/trust
groups remain unresolved.

## Evidence and effects

The outer sidecar, 133-file clean extraction, source archive, manifest, SBOM,
controller/tool binaries, adapter-bearing library, version metadata, all three
strict code-generation reports, and five non-authorizing self-tests pass. The
manifest and controller scope grant authority `NONE`.

Scientific effect is none: no schedule, treatment, outcome, calibration,
measurement, analysis, or confirmatory value is selected. Compatibility effect
is exact: every bound byte, hash, profile, and report is release identity.

## Rejected interpretations and supersession

This ADR does not authorize stand access, transfer/install, account/key/path or
permission changes, access probes, Q15-R/Q15-W issuance or execution, real
PMU/MSR/affinity/NUMA operations, calibration, pilot, measurement, or
confirmatory work. A successful build, root access, or SSH permission is not
phase authority.

Any byte, source revision, build profile, authority field, adapter/controller
contract, dependency, toolchain, or report change requires a new clean release,
complete verification, and prospective acceptance. The predecessor preparation
and this release identity remain immutable.
