# ADR-0021: No repository license grant

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Repository licensing and distribution
- Decision owners: Repository owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 completion / Stage 3 entry

## Context and scientific constraints

The protocol does not authorize a source-code license. The repository owner was
therefore asked to select an SPDX license or explicitly retain a private,
no-license posture before production files were created.

## Options considered

1. An owner-selected SPDX license.
2. No license grant, with no `LICENSE` file and no SPDX license declaration on
   repository-authored source.

## Decision

The repository owner selected **no license** on 2026-08-17. Repository-authored
material is not offered under an open-source license. No `LICENSE` file or SPDX
license identifier will be added. This decision grants no permission to copy,
modify, or distribute the repository.

Third-party dependencies retain their own licenses. Their notices and license
identities are provenance records only and do not license this repository.

## Evidence

The owner answered Q4 with “no license.” The imported protocol is silent on the
legal disposition of implementation source, so no scientific decision is
affected.

## Consequences and compatibility

Scientific effect: none. Compatibility effect: public or third-party
distribution is not authorized by this repository; packaging is for an
authorized stand transfer only. Dependency use must remain compatible with a
private/no-grant repository, and packages must not imply that dependency terms
apply to repository-authored material.

## Verification and acceptance tests

- The root has no `LICENSE` file.
- Repository-authored files do not claim an SPDX source license.
- The dependency inventory records each third-party license separately.
- Package documentation states that the bundle carries no repository license
  grant.

## Rollback or supersession

A later license grant requires a superseding ADR from the repository owner,
ownership review, dependency-compatibility review, and the corresponding legal
text. It applies only as stated by that later record.

## Protocol-amendment assessment

No protocol amendment is required because licensing does not change scientific
semantics.
