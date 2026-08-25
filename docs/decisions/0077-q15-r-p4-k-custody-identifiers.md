# ADR-0077: Freeze logical P4-K custody-domain and custodian identifiers

- Status: `ACCEPTED_LOGICAL_IDENTIFIERS_ONLY_OPERATIONAL_EVIDENCE_ABSENT`
- Date: 2026-08-25
- Decision ID: D-077
- Accepted by: Q15-R-P4-K-D owner-delegated recommended choice
- Decision owners: security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0066 for the future P4-K transaction
- Lifecycle gate: before any P4-K-A authorization or public-artifact creation

## Context and scientific constraints

The future private key requires an owner-controlled off-stand custody domain
and a custodian distinct from the issuer and reviewer. A logical identifier is
not proof that storage, access control, recovery, retention, or operational
custody exists. No private-key path may enter repository evidence.

## Options considered

1. an explicit non-stand custody-domain ID and the accepted distinct custodian
   logical role, with operational evidence deferred;
2. repository or stand private-key custody, or an inferred path;
3. a shared issuer/reviewer/custodian identity; or
4. remain blocked.

## Decision

Freeze:

- custody domain ID `OWNER-OFFLINE-Q15-KEY-CUSTODY`; and
- custodian principal ID `cpu-prefetch-q15-custodian`.

These are non-secret logical identifiers only. This ADR does not assert that a
custody location, device, account, credential, access rule, backup, or recovery
mechanism exists or has been verified. It does not select or serialize a
private-key path. The create-exclusive absolute public allowed-signers source
path remains a later P4-K-A output and is null.

## Evidence

- ADR-0058 already freezes `cpu-prefetch-q15-custodian` as the distinct logical
  custody role.
- D-076 through D-079 proposal SHA-256:
  `cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5`.
- Q15-R-P4-K-D acceptance SHA-256:
  `11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`.

## Consequences and compatibility

Scientific effect is none. The domain ID, custodian ID, later public-artifact
path, access/retention/recovery policy, and custody receipts become evidence
identity. No compatibility claim exists until operational evidence is supplied.

## Verification and acceptance tests

Checks require the exact two identifiers, their logical-only status, false
operational verification, null private/public artifact evidence, and no
private-key path. They reject role collapse, repository/stand custody, path
fabrication, or action authority.

## Rollback or supersession

Changing either ID or any later custody/path/access/retention/recovery fact
requires prospective supersession and a new unused artifact identity. Existing
records remain immutable.

## Protocol-amendment assessment

No protocol amendment is required. This names a security/custody boundary and
does not alter scientific semantics.
