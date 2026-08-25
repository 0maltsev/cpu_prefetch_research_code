# Q15-R P4-K-R D-097 decision bundle

## Entry evidence

D-096 completed exactly once and stopped before P4-K-R. The immutable inputs
to a future read-only review are:

- D-095 terminal evidence SHA-256:
  `ccfe61af14b8aca872a9fd0f4ab4371fb3e74cf445846c8b1a8b30e660f2fa2d`;
- D-096 complete evidence SHA-256:
  `8c30c1fb941179f0498943fd6ac34264ba185a318661513802fd1b2e29dfa4c8`;
- D-096 action receipt SHA-256:
  `36db7093c7e8854c6307707883e856864ff58db0c48d69ee89a89f917e92f4d0`;
- target public-key SHA-256:
  `41cf7aab4c512c38dc0c3f802fdc0e3265cb3327828b5d3bcc0ba2cacf273b21`;
- target allowed-signers SHA-256:
  `b08f32720b7987218a5c51f31f822f2ea1d22ff948beb41382518927d815c718`;
- target fingerprint:
  `SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM`.

The target private key exists outside the repository at the accepted v2 path.
P4-K-R must not read, hash, copy, use, or even probe that private path. It
reviews only the immutable public and repository evidence.

## Decisions required

| ID | Decision | Recommended option | Alternative | Effect |
|---|---|---|---|---|
| D-097A | Reviewer separation | Explicitly extend the accepted single-owner waiver to this read-only review, naming `cpu-prefetch-bootstrap-owner` | Establish a distinct reviewer before review | The recommendation is operationally available but preserves the critical lack of independent detection |
| D-097B | Review output | Create-exclusive `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/review-v1` | Another unused exact non-stand path | Path and basenames become immutable review identity |
| D-097C | Review mechanism | Repository-owned fixed read-only tool; public hashes, fingerprint, allowed-signers equality, D-095/D-096 lineage; one attempt, zero retry | Remain blocked | No private access, installation, or signing through the target key |
| D-097D | Authorization | New canonical 1,800-second bootstrap SSHSIG plus single-owner pre-review waiver receipt | Establish distinct reviewer and then issue | Exact bytes/signature/UTC/tool/output become transaction identity |

## Recommended graph

1. preserve both action trees and repository evidence;
2. implement and test a no-private-access review tool;
3. freeze its source/tool hashes and create-exclusive output path;
4. issue one exact bootstrap-signed 1,800-second review authorization;
5. verify that authorization using public bootstrap trust;
6. execute one read-only public-evidence review;
7. retain complete or partial review evidence and stop;
8. prepare, but do not execute, the separate P5 installation/trust-activation
   gate.

## Exact approval statement

> D-097 — accept D-097A through D-097D recommendations. Extend the D-095/D-096
> single-owner security waiver to one read-only P4-K-R review by
> `cpu-prefetch-bootstrap-owner`; accept the lack of independent detection.
> Authorize repository-local review-tool implementation and disposable/public
> tests, then exactly one new bootstrap SSHSIG authorization and exactly one
> create-exclusive public-only review under
> `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/review-v1`. Prohibit
> reading, hashing, copying, using, or probing either private key; preserve
> D-095 and D-096 evidence; use one attempt and zero retry; stop after the
> review receipt before P5. Do not authorize installation, stand access,
> P4-R, Q15-R/Q15-W, platform controls, qualification, calibration, pilot,
> measurement, or confirmatory execution.
