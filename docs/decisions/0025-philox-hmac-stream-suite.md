# ADR-0025: Philox/HMAC deterministic stream suite

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Deterministic generation / seed derivation
- Decision owners: Repository owner; reproducibility owner; integrity owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 6 implementation; accepted as Q5

## Context and scientific constraints

The protocol requires treatment-blind, reproducible event and node orders,
payload initialization, consumer state, and later schedule generation. Standard
library random distributions do not define a cross-implementation bit stream.
Master-seed values and their namespace roles remain prospective run inputs and
must not be invented by the implementation.

## Options considered

1. A standard-library engine and distributions.
2. PCG or an AES counter stream.
3. Random123 source reuse.
4. An independent local Philox4x32-10 core with OpenSSL HMAC-SHA-256
   derivation.

## Decision

Select option 4 and identify the suite as
`PHILOX4X32-10-HMAC-SHA256-v1`. No Random123 source, generated output, or
dependency is imported.

The master seed is exactly 256 bits. OpenSSL 3 HMAC-SHA-256 derives a stream
key over length-prefixed UTF-8 fields, in this order: protocol version, suite
ID, namespace, and purpose. Every length is an unsigned 64-bit big-endian
integer. The first eight derived bytes form two Philox key words in big-endian
order. A 64-bit block ordinal occupies counter words zero and one, most
significant word first; counter words two and three are zero. The four output
words form two unsigned 64-bit draws in big-endian word order.

Separate purpose labels are mandatory for event order, node order, event
payload initialization, and initial consumer state. Unknown suite IDs fail
closed. Concrete master seeds and namespace IDs remain immutable external
inputs and are not defaulted here.

## Evidence

- Owner acceptance of Q5 on 2026-08-17.
- Imported implementation specification Sections 3.1, 3.3, 6, and 20.
- Salmon et al., *Parallel Random Numbers: As Easy as 1, 2, 3*, defining
  Philox counter-based generators and the 10-round safety variant.
- ADR-0015 accepting OpenSSL 3 SHA-256/HMAC-SHA-256.

## Consequences and compatibility

Scientific effect: the suite prospectively fixes all bits used for Stage 6
record/order construction; values cannot be revised from treatment outcomes.
Compatibility effect: field order, length encoding, key/counter mapping, word
order, purpose labels, and known-answer vectors are part of the suite identity.
OpenSSL is a runtime/build dependency for derivation and integrity, while the
Philox core remains repository-authored under the repository's no-license-grant
posture.

## Verification and acceptance tests

Known-answer Philox and HMAC vectors, stream/block boundaries, purpose-domain
separation, compiler/library parity, deterministic repeated construction, and
unknown/malformed input rejection are required. Tests must not use empirical
performance observations.

## Rollback or supersession

A bit-level change requires a new suite ID, a superseding ADR, new vectors, and
prospective regeneration. Existing orders and artifacts remain tied to this
suite and are never reinterpreted.

## Protocol-amendment assessment

No amendment is required. The protocol delegates the exact deterministic
primitive while requiring it to be frozen before pilot use.
