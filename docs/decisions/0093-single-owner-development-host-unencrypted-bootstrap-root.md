# ADR-0093: Allow one development-host unencrypted bootstrap-root action

- Status: `ACCEPTED_SECURITY_DOWNGRADE_ONE_CREATE_EXCLUSIVE_ACTION_AUTHORIZED`
- Date: 2026-08-25
- Decision ID: D-093
- Accepted by: the owner's exact D-093 authorization
- Decision owners: protocol owner and security/custody/audit owner acting as one
  owner under this explicit waiver
- Protocol version: `2.0.0-pre.2`
- Supersedes: the unaccepted D-087 through D-092 proposal; ADR-0080, ADR-0081,
  ADR-0083, and ADR-0085 only where they govern bootstrap-root genesis
- Lifecycle gate: one bootstrap-root creation action only

## Context and options

The accepted prior policy required distinct roles, a dedicated offline host, an
encrypted Ed25519 key, independent recovery, and separate review. No such
people, host, custody, or signer evidence exists. Options were to remain
blocked, establish those controls, or accept a material security downgrade for
bootstrap-root genesis. The owner explicitly selected the downgrade and
accepted the impersonation and key-loss risks.

## Decision

Authorize exactly one create-exclusive action with these exact properties:

- the single owner principal `cpu-prefetch-bootstrap-owner`, local POSIX account
  `omaltsev`, performs operator, custodian, and auditor functions;
- the current development host is allowed for this bootstrap action;
- `/usr/bin/ssh-keygen`, SHA-256
  `f5a191e91589ab689c93caccc09d827a3a9d4ab28f950dc94ae05351c1389e11`,
  creates one unencrypted OpenSSH Ed25519 key;
- the private key is create-exclusive at
  `/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/id_ed25519`
  with mode `0600` and no independent recovery copy;
- public artifacts are create-exclusive beneath
  `/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public`;
- the action tool may verify file existence and permissions but must never read,
  hash, print, import into the repository, transfer, or otherwise emit private
  key bytes;
- failure retains partial evidence and permits no retry, overwrite, repair,
  cleanup, rotation, or automatic continuation; and
- success stops before P4-K-A.

The exact authorization record SHA-256 is
`271584663d21718357b6fcf013ca0a83a842410cae24d9463b4723217cdb954e`.
The action-tool SHA-256 is
`b98032e7353b37a10257603dc28b5e78d050440ff5090058f890c9bdbb2549ad`.

## Supersession boundary and effects

The D-087 through D-092 proposal remains byte-preserved but is superseded
before acceptance. This ADR waives ADR-0080's offline-host requirement,
ADR-0081's encryption/recovery requirements, ADR-0083's distinct genesis-role
requirements, and ADR-0085's separate genesis review only for creating the
bootstrap root. ADR-0082's create-exclusive public-output boundary remains.
ADR-0084 and every P4-K-A/P4-K-R requirement remain unchanged.

Scientific effect is none. Security compatibility changes materially: one
unencrypted exportable private key on the development host becomes the root of
later authorization trust. Host compromise or accidental key loss can enable
impersonation or permanently invalidate this authorization lineage.

## Authority boundary

This ADR authorizes its repository-local record, schema, action tool, tests,
development-host inventory, and one exact bootstrap-root generation/public
artifact action. It does not authorize private-byte output or repository
import, a second attempt, P4-K-A, P4-K-R, stand access, Q15-R, Q15-W, platform
controls, qualification, calibration, pilot, measurement, or confirmatory
execution.

## Verification and supersession

Before execution, checks must bind the immutable predecessor hashes, exact
paths, environment, tool and action-tool hashes, one-attempt/zero-retry state,
and the bounded authority. After execution, independent read-only checks must
verify private mode without reading the private file, public-key/fingerprint/
allowed-signers consistency, public hashes, and absence of automatic
continuation.

Any path, owner, algorithm, tool, host, retry, overwrite, private-output,
public format, trust scope, or downstream-authority change requires a new
prospective ADR. Existing action and evidence records are append-only.

No protocol amendment is required because this changes authorization-key
security and custody mechanics without changing experimental semantics.
