# Q15-R-P4-R-I D-099 exact authorization decision bundle

Status: **`COMPLETE_VALID_READ_ONLY_IDENTITY_REVIEWED_STOPPED_BEFORE_P4_R_C`**

## Entry evidence

- Clean repository predecessor commit:
  `15e0c852a10092feab456b4233b46837912f10d4`.
- D-097 complete public-review evidence SHA-256:
  `b7c6125d216e01e4207ce54872b2fdb02fd7bf41bb97f99f495006ee28ce4a90`.
- P4-K target signer fingerprint:
  `SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM`.
- Pinned stand Ed25519 host-key fingerprint:
  `SHA256:HZMyUcQIuSQIodYGxXGQ3RCoqR8UcOWPPzuTDhXKtS4`.
- Local transport public-key fingerprint:
  `SHA256:mtIlJWQzNackGLwexvC6bTnmLb8yJtdUQdC/k+FxKRo`.
- Frozen stand and transport identity: `root@185.184.131.153`, where root is
  transport only and not scientific authority.

At acceptance time no private-key use, signature, stand connection, identity
command, capture artifact, P4-R-C action, or downstream activity had occurred.

## Completion evidence

The accepted action completed once inside its nonrenewable UTC window:

- canonical authorization SHA-256:
  `def07da593ffa6b90fc9fb14263e426766a84fe738b59fbdc6c2edbc232cc310`;
- target-key SSHSIG SHA-256:
  `09a75c98895dfa04974e2b2183a9b235c2aaed13f2e3f0cd34a3b78b58f7ff21`;
- identity capture SHA-256:
  `774aca6d192a9adaeeb3daf7bc357c61e957c5b2e6169c9db82cf7722cc3dab6`;
- single-owner review SHA-256:
  `f01e14303f305210819d633345cf454eb6985e394ab36b30e167491374b3b037`;
- complete-evidence SHA-256:
  `afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241`.

All four observations returned status zero with empty stderr. The reviewed
identity is hostname `xeon-cpu-fetch`, kernel/machine
`Linux 7.0.0-27-generic x86_64`, and the exact captured read-only filesystem
identity for `/`, `/root`, and `/dev/md3`. The capture started at
`2026-08-26T08:15:57Z` and completed at `2026-08-26T08:16:03Z`. It performed
no stand filesystem mutation and exposed no automatic continuation.

The combined verifier passes the four schemas, canonical bytes and hashes,
SSHSIG/public identities, four exact observation vectors, bounded outputs,
sidecars/manifest, semantic review, eight negative mutations, and the mandatory
P4-R-C stop. These bytes may be used only as the fresh-identity input to a
separately prepared and explicitly authorized P4-R-C.

## Exact accepted action

1. Accept D-099's single-owner operator/custodian/auditor waiver and the stated
   impersonation, misuse-detection, misuse, and permanent-key-loss risks.
2. Mint a fresh canonical authorization with exactly 1,800 seconds of UTC
   validity and every P4-R-C/later authority flag false.
3. Use the active unencrypted P4-K v2 private key exactly once to create an
   OpenSSH SSHSIG over that authorization. Never print, hash, copy, transfer,
   or commit private bytes.
4. Independently verify the signature using the D-097-reviewed allowed-signers
   artifact before opening transport.
5. Connect using the pinned Ed25519 host key, fixed local transport identity,
   batch public-key authentication, no agent/password/keyboard interaction,
   one connection attempt per observation, and zero retries.
6. Execute exactly once each, in order:

   - `/usr/bin/hostname`
   - `/usr/bin/uname --kernel-name --kernel-release --machine`
   - `/usr/bin/stat --format=%n|%F|%a|%u|%g|%s|%d|%i -- / /root /dev/md3`
   - `/usr/bin/findmnt --json --target / --output TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION`

7. Store bounded stdout/stderr bytes, hashes, fixed argv, and return codes in
   the create-exclusive D-073 identity path; emit its sidecar.
8. Perform one public single-owner review under the explicit waiver and stop.

## Stop and authority boundary

Any mismatch, expired window, host-key or authentication failure, nonzero
command status, output-limit breach, existing destination, signature/hash
failure, or review failure stops with partial evidence retained and no retry,
delete, overwrite, repair, reuse, or cleanup.

The proposed action authorizes no stand filesystem mutation, transfer,
extraction, collector self-test or execution, P4-R-C, P5, Q15-R/Q15-W,
platform control, qualification beyond the four identity observations,
calibration, pilot, measurement, confirmatory work, or automatic continuation.

## Exact accepted statement

> Q15-R-P4-R-I-D099 — accept D-099 and its single-owner security downgrade and
> risks. Authorize exactly one use of the active P4-K v2 private key to SSHSIG
> one fresh 1,800-second canonical D-099 authorization, followed by exactly
> four fixed read-only SSH observations on root@185.184.131.153 using the
> pinned Ed25519 host key, one create-exclusive local identity capture, and one
> single-owner public review. Use one attempt per observation, zero retries,
> retain partial evidence, and stop before P4-R-C. Do not authorize stand
> filesystem mutation, transfer, extraction, collector execution, P5,
> Q15-R/Q15-W, platform controls, calibration, pilot, measurement, or
> confirmatory work.
