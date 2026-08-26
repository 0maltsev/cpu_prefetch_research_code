# Q15-R-P4-R-C D-100 through D-103 decision/input bundle

Status: **`PROPOSED_EXACT_OWNER_ACCEPTANCE_REQUIRED_NO_ACTION_AUTHORITY`**

Machine record SHA-256:
`faa4c377a3261b35422a9cc7699f674458d55a364083a06f42441cc4abcc60d6`.

## Entry evidence

- Clean D-099 closure commit:
  `909b698a071203adb97746511b97a9316dd55f07`.
- D-099 complete-evidence SHA-256:
  `afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241`.
- Accepted identity/review SHA-256:
  `774aca6d192a9adaeeb3daf7bc357c61e957c5b2e6169c9db82cf7722cc3dab6`
  and
  `f01e14303f305210819d633345cf454eb6985e394ab36b30e167491374b3b037`.
- Immutable v3 archive SHA-256:
  `f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`;
  current local size and safe-member audit pass.
- P4-K target fingerprint:
  `SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM`.
- Pinned stand Ed25519 host fingerprint:
  `SHA256:HZMyUcQIuSQIodYGxXGQ3RCoqR8UcOWPPzuTDhXKtS4`.

D-099 is eligible only as the fresh predecessor for preparing P4-R-C. It is
not P4-R-C authority and cannot be reused for another observation or signature.

## Why the blanket acceptance cannot execute P4-R-C

Four exact conflicts were not presented when the owner sent the blanket
acceptance. Treating that message as a retrospective choice would fabricate
material security and compatibility decisions:

1. ADR-0074 still requires an independent auditor, while the available owner
   has collapsed the roles only for earlier gates.
2. D-099 correctly created the frozen custody root, but the predecessor P4-R-C
   template broadly says custody paths must be absent.
3. OpenSSH remote execution necessarily crosses the account's login-shell
   command-string boundary; literal remote `execve` argv is unavailable without
   a preinstalled agent or subsystem.
4. Creation behavior for the namespace parent
   `/root/cpu-prefetch-q15-r-p4-r` was not explicit.

These are engineering/security decisions, not scientific choices. They still
require prospective acceptance because they alter the previously frozen
governance and compatibility boundary.

## Recommendations

### D-100 — single-owner P4-R-C waiver

Accept one owner acting as operator, custodian, and auditor for exactly one
P4-R-C transaction. Accept the lack of independent misuse and tamper detection,
development-host/account compromise exposure, unencrypted signer/transport-key
impact, and no independent recovery. Do not describe the review as independent.

### D-101 — append-only custody compatibility

Permit only the exact already verified D-099 custody root and its five retained
predecessor files. Every P4-R-C stdout, stderr, sidecar, receipt, review, and
failure destination must remain absent and be created exclusively. Any other
pre-existing entry stops. No overwrite, rename, reuse, cleanup, or deletion is
allowed.

### D-102 — fixed OpenSSH transport boundary

Permit only repository-hashed, precomputed constant remote command strings,
invoked by local subprocess argv with `shell=False`, no user-controlled input,
strict token/path validation, pinned host and transport keys, one attempt, and
zero retry. Explicitly accept the remote login shell as part of the trusted
boundary. Any command construction drift requires a new decision and tool hash.

### D-103 — namespace-parent rule

Permit the exact namespace parent to be created once with mode `0700` if it is
absent. If it exists, require a root-owned, nonsymlink directory with the exact
accepted mode and no conflicting transaction root. Any partial creation is
retained and consumes this transaction identity.

## Action that remains closed

Acceptance of these recommendations would authorize only repository-local
implementation and verification of the fail-closed executor, schemas, and
still-unissued authorization/review records. It would not authorize key use,
signature creation, stand access, path creation, transfer, extraction, stand
self-tests, collector execution, P4-R-C, P5, Q15, controls, calibration, pilot,
measurement, or confirmatory work.

After the executor bytes and hashes are frozen, the later exact action gate must
separately authorize:

- one fresh 1,800-second canonical authorization;
- one P4-K v2 SSHSIG;
- one single-owner pre-execution public review under the accepted waiver;
- one create-exclusive namespace/transaction tree;
- one archive and one sidecar transfer;
- one extraction and complete internal verification;
- one `--self-test`, one `--describe-contract`, and one `--collect` attempt;
- append-only local stdout/stderr/sidecar/receipt/review evidence; and
- zero retries with stop-retain-no-delete behavior.

That action must stop before P5 and every Q15/scientific phase.

## Exact approval required now

> Q15-R-P4-R-C-D100 — accept D-100 through D-103 exactly as recommended in
> decision-input SHA-256
> faa4c377a3261b35422a9cc7699f674458d55a364083a06f42441cc4abcc60d6,
> bound to commit 909b698a071203adb97746511b97a9316dd55f07, D-099
> complete-evidence SHA-256
> afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241,
> and v3 archive SHA-256
> f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a.
> Accept the single-owner review/custody/security downgrade and risks, exact
> verified pre-existing D-099 custody root with create-exclusive P4-R-C
> outputs, fixed hash-bound OpenSSH remote-command boundary, and exact
> namespace-parent rule. Authorize repository-local implementation and
> verification of the fixed fail-closed P4-R-C executor, schemas, and
> authorization records only. Do not use keys, sign or issue authorization,
> access or modify the stand, transfer or extract artifacts, execute self-tests
> or the collector on the stand, or perform P4-R-C/P5/Q15/platform-control/
> calibration/pilot/measurement/confirmatory work. The exact one-shot P4-R-C
> action requires a later separately signed and explicitly approved
> authorization.

Until that statement is accepted exactly, D-100 through D-103 remain proposed,
the executor must not be implemented as an operational tool, and P4-R-C remains
blocked.
