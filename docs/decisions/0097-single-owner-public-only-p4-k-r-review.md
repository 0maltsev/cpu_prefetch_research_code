# ADR-0097: Perform one single-owner public-only P4-K-R review

- Status: `ACCEPTED_ONE_PUBLIC_ONLY_P4_K_R_REVIEW_AUTHORIZED`
- Date: 2026-08-26
- Decision ID: D-097
- Accepted by: the owner's acceptance of every recommendation in the prepared
  D-097 bundle and instruction to complete the next gate
- Decision owners: protocol, security, custody, release, and audit owner acting
  as one owner under the D-095/D-096 waiver
- Protocol version: `2.0.0-pre.2`
- Lifecycle gate: one read-only P4-K-R review followed by a mandatory stop
  before P5

## Context

D-096 created one target Ed25519 identity and retained complete public evidence.
It did not authorize review, installation, trust activation, signing with that
identity, stand access, or scientific work. The accepted D-097 bundle fixes a
separate review gate over public evidence only.

## Decision

Accept D-097A through D-097D exactly as recommended:

- extend the accepted single-owner waiver to reviewer
  `cpu-prefetch-bootstrap-owner`, accepting the lack of independent detection;
- use create-exclusive review output root
  `/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/review-v1`;
- use a repository-owned fixed tool that reads only the D-095/D-096 repository
  lineage and D-096 public artifacts;
- prohibit reading, hashing, copying, using, or probing either private key;
- verify public hashes, the Ed25519 SHA-256 fingerprint, the single-entry
  allowed-signers grammar, principal, and public-key byte equality;
- issue one canonical 1,800-second bootstrap SSHSIG authorization;
- perform one review attempt, zero retries, and append-only complete or partial
  evidence; and
- stop after the review receipt before P5 and every later phase.

## Scientific and compatibility effects

Scientific effect is none. The waiver, tool bytes/hash, authorization
bytes/hash, signature, UTC window, public source hashes, output path, review
receipt, and reviewed public trust identity become compatibility inputs. The
review does not install or activate trust.

## Authority boundary

This ADR authorizes repository-local implementation/tests/records, one
bootstrap authorization signature, one create-exclusive public-only review,
and evidence capture. It authorizes no private-key access or presence probe,
installation, trust activation, signing with the target key, P5, stand access,
P4-R, Q15-R/Q15-W, platform controls, qualification, calibration, pilot,
measurement, or confirmatory execution.

## Supersession

Any reviewer, waiver, source, tool, path, public bytes, principal, fingerprint,
UTC, signature, retry, output, or authority change requires a prospective ADR
and exact authorization. D-095 and D-096 evidence remains immutable.
