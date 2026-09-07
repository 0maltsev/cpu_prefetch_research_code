# ADR-0020: Platform and validation custody separation

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Access control / sealing authority
- Decision owners: Repository owner; institutional security owner; validation custodian
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 boundary; named principals/enforcement due before Phase 16 and confirmation

## Context and scientific constraints

The imported access state machine requires H3 validation data to be technically inaccessible until permitted and requires authority segregation, predecessor identity/hash, append-only chronology, recovery, and audit.

## Options considered

1. One operator/account with convention-only hiding.
2. Separate OS principals/storage policy.
3. Cryptographic/offline custody with separate principals.
4. Another audited technical boundary satisfying the same state machine.

## Decision

Platform operation and validation custody use separate principals. Validation artifacts are technically inaccessible to implementation/platform operators until the imported state authorizes access. The implementation exposes a replaceable custody/store interface; the institution may realize it with separate accounts/storage, cryptographic/encrypted custody, controlled offline media, or another audited mechanism.

Named principals, accounts/keys/storage, negative-access evidence, recovery, and audit retention remain required operational inputs; Q3 allowed these facts to remain open until their later gates.

## Evidence

The repository owner accepted Q3 on 2026-08-17. The imported access/sealing protocol fixes state chronology and authority segregation but repository evidence cannot name institutional actors or mechanisms.

## Consequences and compatibility

Scientific effect: protects selection/validation chronology and prevents outcome leakage. Compatibility effect: deployment must provide an enforceable custody plugin/policy; convention-only secrecy is incompatible.

## Verification and acceptance tests

Negative-access tests cover every sealed state, wrong role, missing predecessor/hash, unauthorized branch/overwrite, leaked summary/log, recovery, key/account loss, and audit retention. Final records name actual authorities.

## Rollback or supersession

Authority/mechanism changes append new custody records and require repeated access/recovery tests. A weaker boundary requires protocol review and may require amendment.

## Protocol-amendment assessment

No amendment is required; this implements the fixed access model.
