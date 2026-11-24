# ADR-0051: Split Q15 qualification tool and authorization boundary

- Status: `ACCEPTED`
- Date: 2026-08-24
- Decision ID: D-051
- Classification: security, platform, and qualification lifecycle boundary
- Decision owners: platform, security, controller, protocol, custody, and audit
  owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: prospective omnibus use of the `STAND_QUALIFICATION` phase in
  `cpu-prefetch-stage17-authorization/2`; immutable v1/v2 records remain
  readable
- Lifecycle gate: before any dynamic Q15 stand qualification

## Context and scientific constraints

The sealed measurement candidate is deliberately unprivileged and contains no
production MSR adapter. The exact complete MSR prestate required to authorize
H1 mutation cannot exist until it has been collected on the stand. Filling that
prestate after one omnibus authorization is signed would make the authorization
non-prospective and would defeat independent verification.

Qualification produces platform-eligibility evidence only. It may not consume
scientific schedules, calibration namespaces, queue outcomes, pilot data, or
confirmatory data. The registered H0/H1 meanings and the accepted Intel
06_55H/0x1A4 mapping remain unchanged.

## Options considered

1. Authorize one privileged session and insert the prestate after execution.
2. Treat the prior inventory as the complete MSR prestate.
3. Add qualification controls to and reseal the measurement candidate.
4. Preserve the candidate, release a separate no-measurement qualification
   tool, authorize read-only Q15-R acquisition, and then authorize a distinct
   prestate-bound Q15-W apply/probe/restore transaction.
5. Declare the stand ineligible.

## Decision

Select option 4, with option 5 as the fail-closed outcome whenever exact tool,
authority, evidence, probe, or restoration requirements cannot be met.

- The measurement candidate remains byte-for-byte immutable.
- The qualification-tool bundle has its own profile, source/binary hashes,
  SBOM, manifest, and checksum sidecar. Possession of the bundle grants no
  stand or execution authority.
- Q15-R may contain read-only acquisition and collectors only. It must be
  separately signed and must not permit MSR writes.
- Q15-W is a different immutable authorization. It must bind the sealed Q15-R
  evidence and the three complete prestates before signature.
- A Q15-W mutation is one exact CPU/control at a time, followed by independent
  complete-value readback. Restoration is in reverse order and is independently
  reread. Uncertain restoration quarantines the stand.
- The fixed adapter exposes only family 06/model 55H, MSR 0x1A4, CPUs 0/1/26,
  and complete-value transitions derived from the accepted mask. It exposes no
  arbitrary MSR-address or mask option.
- The tool does not validate its own operational authority. Exact argv,
  executable hash, role, OS privilege, limits, evidence targets, and detached
  signature are controlled by the prospective Q15-R/Q15-W record and external
  controller. A command's presence is not permission to run it.
- Prepared/incomplete records use a non-authorizing preparation schema and
  status. They cannot be represented as `AUTHORIZED`.

## Evidence

- Explicit owner acceptance of Q15-S1 on 2026-08-24.
- ADR-0045, ADR-0049, and ADR-0050.
- Clean measurement candidate revision
  `693f00b3878ed027dc09aea7916f149874fb12a1`, archive SHA-256
  `f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1`.
- Repository-local fake/file-boundary and schema tests; no stand or MSR device
  is accessed by those tests.

## Consequences and compatibility

Qualification tool source/binary/bundle hashes, candidate release hashes,
stand identity, roles, command vectors, limits, custody, Q15-R evidence,
complete prestates, probe definitions, restoration, authorization bytes, and
signatures become qualification identity. The v2 authorization schema remains
available for historical validation, but a new Q15 request cannot use its
omnibus `STAND_QUALIFICATION` phase after this ADR.

The split changes no treatment, estimator, timed operation, queue behavior, or
measurement artifact. It adds no authority to the measurement candidate.

## Verification and acceptance tests

- Fixed-path adapter tests reject wrong CPUs, short I/O, failed open/read/write,
  wrong current values, H0/H1 collapse, and unregistered transitions using a
  fake file-operation boundary.
- The production command surface has no arbitrary path, MSR address, mask,
  schedule, namespace, calibration, pilot, measurement, or confirmatory option.
- Authorization-schema tests reject Q15-R mutation, Q15-W without Q15-R/prestate
  binding, role overlap, wildcard/latest values, incomplete command identity,
  missing inverse/readback/probe commands, and authority-bearing preparation
  records.
- Bundle verification rejects a measurement runner, any authority flag, dirty
  release source, missing tool/hash/SBOM, or absent no-authority declarations.
- All local execution tests use fakes or pure self-tests and never open
  `/dev/cpu/*/msr`.

## Rollback or supersession

Do not rewrite either authorization or qualification evidence. A material tool,
mapping, role, command, limit, custody, stand, prestate, probe, or restoration
change requires new immutable bundles/records and full requalification. A
mapping or factor-semantics change also requires protocol-owner review and, when
scientific meaning changes, a versioned protocol amendment.

## Protocol-amendment assessment

No protocol amendment is required. This decision separates qualification
authority and tool custody without changing the imported scientific design.
