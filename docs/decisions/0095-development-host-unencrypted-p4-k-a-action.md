# ADR-0095: Permit one development-host unencrypted P4-K-A action

- Status: `ACCEPTED_SECURITY_DOWNGRADE_ONE_SIGNED_P4_K_A_ACTION_AUTHORIZED`
- Date: 2026-08-25
- Decision ID: D-095
- Accepted by: the owner's exact D-095 approval of the P4-K-A security
  downgrade, one bootstrap signature, and one target-key generation action
- Decision owners: protocol, security, custody, release, and audit owner acting
  as one owner under this explicit waiver
- Protocol version: `2.0.0-pre.2`
- Supersedes: ADR-0080, ADR-0081, ADR-0082, and ADR-0085 only for this exact
  target-key action
- Lifecycle gate: one signed P4-K-A action followed by a mandatory stop before
  P4-K-R

## Context and options

The D-094 successor resolves bootstrap trust but preserves six target-key
inputs. The accepted policy recommends a dedicated offline host, an encrypted
key with an uncaptured secret and KDF value, an unrecorded private path,
distinct audit review, and independent recovery custody. The owner explicitly
selected a development-host, unencrypted, single-owner action and accepted its
critical impersonation, misuse-detection, and permanent key-loss risks.

## Decision

Authorize exactly one P4-K-A transaction with these properties:

- the development host and POSIX account `omaltsev` perform operator,
  custodian, release, and auditor functions;
- `/usr/bin/ssh-keygen` creates one unencrypted OpenSSH Ed25519 target key at
  `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/id_ed25519`;
- no passphrase, KDF work value, recovery copy, or independent custody exists;
- the private path may appear in the authorization contract, but private bytes
  and their content hash may never be read, emitted, transferred, or recorded;
- create-exclusive public evidence is written below
  `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/public`;
- the exact JCS-I64-v1 authorization is signed once by the active D-093/D-094
  bootstrap root under principal and namespace
  `cpu-prefetch-q15-authorization`, then verified with the accepted public
  `allowed_signers` bytes before target-key generation;
- distinct review is waived and the same owner supplies the pre-action review;
- the authorization window is nonrenewable and exactly 1,800 seconds;
- signature, generation, public extraction, fingerprinting, trust construction,
  and evidence sealing each occur at most once with no retry, overwrite,
  repair, cleanup, or deletion; and
- success or failure stops before P4-K-R and every later phase.

## Effects and compatibility

Scientific effect is none. Security compatibility changes materially. An
unencrypted exportable target key and the unencrypted bootstrap root coexist on
one development host under one owner. Host/account compromise can authorize or
impersonate later governance, misuse lacks independent detection, and loss of
either key has no independent recovery.

The exact source commit, tool and interpreter hashes, OpenSSH version, paths,
authorization bytes/hash, UTC instants, bootstrap signature/trust, target
public bytes/fingerprint/trust bytes, review receipt, action receipt, and public
sidecar become immutable transaction identity.

## Authority boundary

This ADR authorizes its repository records, schema, tool, tests, one bootstrap
SSHSIG action, one create-exclusive target-key action, and public/private-
metadata-only evidence capture. It authorizes no private-byte output, second
attempt, P4-K-R, installation, stand access, P4-R, Q15-R/Q15-W, platform
control, qualification, calibration, pilot, measurement, or confirmatory work.

## Failure, verification, and supersession

Preflight binds the clean D-094 commit, active-root state and public evidence,
exact toolchain and paths, one-attempt/zero-retry graph, canonical
authorization, UTC window, single-owner review waiver, and bounded authority.
The action retains partial public evidence and stops on the first failure.
Post-action verification may hash public artifacts and inspect private-file
metadata only.

Any owner, host, tool, path, key protection, recovery, review, window,
canonical bytes, signer, fingerprint, retry, failure policy, P4-K-R, or later
authority change requires a new prospective ADR and append-only record. No
protocol amendment is required because scientific semantics do not change.
