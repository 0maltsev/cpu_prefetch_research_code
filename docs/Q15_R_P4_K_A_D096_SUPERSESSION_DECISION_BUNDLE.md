# Q15-R P4-K-A D-096 supersession decision bundle

## Current terminal state

D-095 produced exactly one valid bootstrap SSHSIG over authorization SHA-256
`e1a8934198dd2a581ff97564dfc33e4830750c18184893a18f37d80067a94728`
and then stopped before target-key generation because the action wrapper passed
both `stdin` and `input` to `subprocess.run`. The append-only partial evidence
is retained. The target private path is absent. D-095 permits no retry, repair,
overwrite, cleanup, deletion, or continuation; P4-K-R is ineligible.

## Recommended prospective D-096 decision

Use a new transaction identity and create-exclusive `p4-k-v2` tree. Preserve
the complete D-095 partial tree unchanged. Fix only the subprocess verification
wrapper, add a regression test that performs SSHSIG sign/verify with disposable
test keys in a temporary directory, bind the fixed tool and test hashes, issue
a new exact 1,800-second authorization, make exactly one new bootstrap
signature, verify it, and attempt exactly one unencrypted target-key generation
at:

- private: `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/id_ed25519`;
- public evidence: `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public`.

The accepted D-095 security downgrade remains otherwise unchanged. D-096 would
authorize no deletion of D-095 evidence and would again stop before P4-K-R.

## Options

1. Accept the recommended new `p4-k-v2` transaction with one new signature and
   one target-key attempt.
2. Remain blocked with D-095 terminal and no target key.
3. Propose a different prospective path or custody/security policy; this
   requires a revised decision bundle before action.

## Exact approval statement

> D-096 — accept the recommended D-095 terminal-failure supersession. Preserve
> the complete `p4-k-v1` partial tree unchanged. Authorize repository-local
> defect correction and regression tests, then exactly one new bootstrap
> SSHSIG authorization and exactly one create-exclusive unencrypted Ed25519
> target-key generation under `p4-k-v2`, with the same single-owner security
> downgrade and accepted critical risks as D-095. Require a new canonical
> 1,800-second authorization, fixed tool hashes, independent public signature
> verification, append-only evidence, zero retries, and a mandatory stop before
> P4-K-R. Do not authorize stand access, installation, Q15-R/Q15-W,
> qualification, calibration, pilot, measurement, or confirmatory execution.
