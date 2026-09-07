# ADR-0042: Stage 16 verification and stand-bundle profile

- Status: `ACCEPTED`
- Date: 2026-08-22
- Classification: Engineering verification / reproducible stand transfer
- Decision owners: Repository owner; implementation owner; build and verification owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: None
- Lifecycle gate: Stage 16 software verification; no pilot or confirmatory authority

## Context and constraints

Stages 1--15 provide component and synthetic correctness evidence, while the
accepted protocol still requires a clean independent verification pass and a
traceable transfer to an eligible stand. Platform identity, controls, runtime
qualification, calibration inputs, and the production measurement executable
remain unresolved. A package that embedded convenient stand values or implied
pilot readiness would violate that boundary.

## Options considered

1. Reuse the generic Stage 3 CPack archive as a pilot bundle.
2. Distribute an unrecorded directory of binaries and source.
3. Create a deterministic, append-only stand-preflight archive containing an
   exact source archive, release foundation binaries/libraries, schemas,
   protocol, validators, SBOM/licenses, checksums, provenance, and runbook while
   explicitly prohibiting measurement.

## Decision

Select option 3 and profile `STAGE16-STAND-BUNDLE-v1`. The bundle is generated
offline from the current source tree and accepted `release-gcc` build. It has a
complete internal SHA-256 inventory and an external outer-archive SHA-256
sidecar, never overwrites an existing path, and can be verified after clean
extraction using only read-only/nonprivileged operations.

Runtime dependency resolution retains library identities and paths but removes
`ldd`'s per-process load addresses. Those addresses are neither dependency
identity nor reproducible provenance; retaining them made equal-input archives
vary across invocations. The repeat-build hash check is therefore normative for
this profile.

The safe preflight executable has two modes: build-identity self-test and
read-only Linux inventory with caller-supplied snapshot identity/time. Its
canonical output always states `INVENTORY_ONLY_NOT_QUALIFIED` and enumerates
unresolved gates. It has no apply, MSR, sysfs-write, service, boot, calibration,
pilot, or measurement path.

The bundled release binaries are unstripped outputs of the accepted release
preset; Stage 16 does not alter compiler flags for debugging. The exact source
archive and compile commands accompany them. A future production measurement
binary and debug/symbol policy remain one release-bound qualification decision.

## Evidence and effects

The direct Stage 16 task authorizes repository infrastructure, safe software
verification, and bundle creation. It authorizes no scientific value or stand
mutation. Scientific effect is none: the profile packages existing contracts
and preserves every external value as unresolved. Compatibility effect is that
bundle layout, manifest schema, source-archive construction, SBOM mapping, and
checksum rules are versioned profile identity.

## Verification

Require both clean compiler matrices, full tests and sanitizer matrices,
strict generated-code checks, release policy, static/format/schema/document/
dependency/CI checks, deterministic source/archive construction, external and
internal hash verification, clean extraction, smoke/preflight self-tests, and
review proving that examples contain no frozen-looking value.

## Supersession

Any bundle-layout, manifest, hash, source-selection, binary, debug, dependency,
or validator change needs a new profile or superseding ADR and fresh full
verification. Scientific behavior or a pilot authorization cannot be supplied
by superseding this engineering record; it follows the protocol freeze and
amendment rules.
