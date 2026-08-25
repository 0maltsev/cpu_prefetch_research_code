# ADR-0096: Supersede terminal D-095 with one corrected P4-K-v2 action

- Status: `ACCEPTED_ONE_CORRECTED_P4_K_V2_ACTION_AUTHORIZED`
- Date: 2026-08-26
- Decision ID: D-096
- Accepted by: the owner's acceptance of the complete recommended D-096
  supersession and instruction to perform everything needed for the next gate
- Decision owners: protocol, security, custody, release, and audit owner acting
  as one owner under the D-095 waiver
- Protocol version: `2.0.0-pre.2`
- Supersedes: D-095 only for one new transaction; it never changes or resumes
  the terminal D-095 transaction
- Lifecycle gate: one corrected P4-K-v2 action followed by a mandatory stop
  before P4-K-R

## Context

D-095 created and independently verified one bootstrap SSHSIG but stopped
terminally before target-key generation because its Python wrapper supplied
both `stdin` and `input` to `subprocess.run`. The complete `p4-k-v1` partial
tree is immutable, the target private path is absent, and D-095 authorizes no
retry, repair, deletion, or continuation.

## Decision

Authorize a distinct `Q15-R-P4-K-A-D096-20260826-01` transaction:

- preserve the D-095 repository commit and external `p4-k-v1` tree unchanged;
- correct only the subprocess input seam and prove it first with disposable
  temporary Ed25519 sign/verify fixtures, including a wrong-message negative;
- bind the corrected tool, frozen D-095 helper, regression test, source commit,
  exact host tools, D-095 terminal evidence, paths, and UTC window;
- create one new bootstrap SSHSIG and independently verify it before target
  key generation;
- attempt exactly one create-exclusive unencrypted Ed25519 target key at
  `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/id_ed25519`;
- write public evidence create-exclusively below
  `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public`;
- never read or hash either private key in repository evidence;
- retain partial public evidence and stop on the first failure, with no retry,
  repair, overwrite, cleanup, deletion, or continuation; and
- stop after complete evidence capture before P4-K-R and every later phase.

The D-095 development-host, unencrypted, single-owner, no-recovery, and
distinct-review security waivers and critical risks remain accepted. D-096
does not reinterpret them as satisfying the stronger D-080 through D-085
recommendations.

## Scientific and compatibility effects

Scientific effect is none. The new transaction ID, `p4-k-v2` paths, corrected
tool/dependency/test hashes, authorization bytes/hash, signature, target public
bytes/fingerprint/trust bytes, receipts, and terminal disposition become
compatibility identity. D-095 remains an immutable failed predecessor.

## Authority boundary

This ADR authorizes repository records, tests, one new bootstrap signature,
one create-exclusive v2 target-key action, and public/private-metadata-only
evidence. It authorizes no mutation of D-095 evidence, second D-096 attempt,
P4-K-R, installation, stand access, P4-R, Q15-R/Q15-W, platform controls,
qualification, calibration, pilot, measurement, or confirmatory execution.

## Supersession

Any tool, dependency, test, owner, path, protection, review, UTC, signature,
fingerprint, attempt, failure, or authority change requires another prospective
ADR, transaction identity, and exact approval. Prior evidence is never edited.
