# ADR-0076: Select a separately authorized new offline Ed25519 ceremony

- Status: `ACCEPTED_REPOSITORY_LOCAL_POLICY_AND_TEMPLATE_PREPARATION_ONLY`
- Date: 2026-08-25
- Decision ID: D-076
- Accepted by: Q15-R-P4-K-D owner-delegated recommended choice
- Decision owners: security and custody owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; resolves only the source-mode choice left open by ADR-0066
- Lifecycle gate: before preparing, issuing, or executing any P4-K-A action

## Context and scientific constraints

ADR-0066 permits either a qualifying owner-controlled existing offline key or
a separately authorized new offline ceremony. No provenance, custody,
rotation, public-key, or fingerprint evidence establishes an existing key.
Treating absence of that evidence as an existing-key selection would fabricate
an external fact. The signing key authenticates governance artifacts and may
not select treatments, platform values, calibration inputs, or outcomes.

## Options considered

1. an existing owner-controlled offline Ed25519 key with complete evidence;
2. a new offline Ed25519 ceremony under a later separate exact authorization;
3. stand-local or repository private-key custody; or
4. remain blocked.

## Decision

Select
`NEW_OFFLINE_ED25519_KEY_CEREMONY_UNDER_LATER_SEPARATE_EXACT_AUTHORIZATION`.
This is a source-mode and template decision only. The ceremony does not yet
have an authorized tool, command, location, UTC window, bootstrap signer,
signature, or review record. No key is read, generated, imported, copied,
fingerprinted, or used, and no public artifact is constructed.

The private key must remain off the stand and outside the repository. A later
P4-K-A authorization must be source-mode-specific, exact, single-use, and
independently reviewed before execution.

## Evidence

- D-076 through D-079 proposal SHA-256:
  `cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5`.
- Q15-R-P4-K-D acceptance SHA-256:
  `11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`.
- Immutable predecessor P4-K preparation SHA-256:
  `c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f`.
- The owner delegated the recommended choices and then directed repository-
  local application; the acceptance record preserves both exact messages and
  the no-authority interpretation boundary.

## Consequences and compatibility

Scientific effect is none. Compatibility identity includes the new-ceremony
source mode, later tool and command identities, public bytes, fingerprint,
custody lineage, rotation identity, and all authorization/review hashes.

## Verification and acceptance tests

Repository checks reject an existing-key claim, a non-null key or artifact,
private-key custody in the repository or stand, silent ceremony authority,
gate issuance, or predecessor/acceptance drift.

## Rollback or supersession

Changing source mode or any later key, ceremony, tool, custody, or rotation
identity requires a prospective ADR, new authorization, and new evidence.
Partial public evidence is retained; private material is never recorded here.

## Protocol-amendment assessment

No protocol amendment is required. This resolves an engineering/security
source mode without changing scientific semantics.
