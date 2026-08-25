# ADR-0078: Split one-shot P4-K acquisition from independent review

- Status: `ACCEPTED_REPOSITORY_LOCAL_POLICY_AND_TEMPLATE_PREPARATION_ONLY`
- Date: 2026-08-25
- Decision ID: D-078
- Accepted by: Q15-R-P4-K-D owner-delegated recommended choice
- Decision owners: security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; refines future P4-K governance under ADR-0070
- Lifecycle gate: before preparing or issuing P4-K-A or P4-K-R

## Context and scientific constraints

Canonical allowed-signers bytes and public-key fingerprints require independent
verification. Combining key acquisition, self-review, installation, and later
authorization signing would collapse trust boundaries. Retrying or repairing
an in-place ceremony would also destroy the one-attempt evidence identity.

## Options considered

1. one source-mode-specific P4-K-A acquisition/public-artifact construction
   attempt, mandatory stop, then a distinct P4-K-R review;
2. an omnibus key action, review, installation, and signing transaction;
3. retry or repair in place; or
4. remain blocked.

## Decision

Freeze two non-collapsible future gates:

- `Q15-R-P4-K-A` may later authorize exactly one new-offline-ceremony and
  public-artifact construction attempt. It must stop with append-only complete
  or partial public evidence. Retry count is zero.
- `Q15-R-P4-K-R` may later authorize only independent verification of the exact
  P4-K-A public bytes, SHA-256 values, Ed25519 fingerprint, custody evidence,
  and canonical allowed-signers artifact. It cannot create/use private key
  material, install the artifact, or sign Q15 authorizations.

Installation remains P4-K/P5 setup work under later separate authority. The
two repository records produced now are still-unissued templates.

## Evidence

- ADR-0070 requires independent public-artifact and fingerprint verification.
- D-076 through D-079 proposal SHA-256:
  `cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5`.
- Q15-R-P4-K-D acceptance SHA-256:
  `11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`.

## Consequences and compatibility

Scientific effect is none. Gate split, source mode, tools, fixed commands,
attempt counts, artifact IDs, public bytes, hashes, fingerprint, custody
receipt, and review receipt become transaction identity.

## Verification and acceptance tests

Checks reject collapsed gates, automatic continuation, retry, repair,
overwrite, cleanup, installation/signing authority, fabricated P4-K-A
evidence, non-distinct review, and any non-null issuance fields.

## Rollback or supersession

Any graph, tool, command, attempt, canonicalization, review, retention, or
rollback change requires prospective supersession. Partial public evidence is
retained; cleanup requires separate exact authority.

## Protocol-amendment assessment

No protocol amendment is required. This strengthens security governance
without changing scientific semantics.
