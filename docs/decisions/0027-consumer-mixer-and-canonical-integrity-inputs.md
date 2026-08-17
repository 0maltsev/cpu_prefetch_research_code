# ADR-0027: Consumer mixer and canonical integrity inputs

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Measured consumer action / integrity identity
- Decision owners: Repository owner; consumer owner; integrity owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 6 implementation; accepted as Q5

## Context and scientific constraints

The protocol fixes one branch-free private consumer update after immutable index
and payload loads and separate SHA-256 identities for record content, ordered
indices, and address deltas. Because the mixer is measured work, it cannot be
selected from performance results or replaced with a convenient checksum.
Pointer values cannot be persistent identities.

## Options considered

1. A cryptographic hash on every consumed record.
2. An xxHash-style rolling operation.
3. A fixed SplitMix-style 64-bit operation plus separately canonical SHA-256
   integrity inputs.

## Decision

Select option 3. Arithmetic is modulo `2^64` and the exact update is:

```text
x = state + 0x9e3779b97f4a7c15
x ^= record_index
x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9
x ^= payload
x = (x ^ (x >> 27)) * 0x94d049bb133111eb
state = x ^ (x >> 31)
```

SHA-256 inputs are domain-separated, length-delimited, and use big-endian
canonical integers. Content input contains line size and capacity followed by
every physical record's index, payload, padding length, and exact padding bytes.
Ordered-index input contains the complete cyclic permutation. Address-delta
input contains signed within-arena byte deltas, including cycle closure. It
never contains an absolute pointer value. The algorithm IDs and versions are
recorded separately from SHA-256 artifact identities.

## Evidence

- Owner acceptance of Q5 on 2026-08-17.
- Imported implementation specification Sections 3.1, 11.1, 16, and 20.
- ADR-0015 OpenSSL SHA-256 and exact-integer identity boundary.

## Consequences and compatibility

Scientific effect: the exact consumer instructions and checksum relationship
are prospectively frozen without treatment evidence. Compatibility effect:
constants, operation order, overflow behavior, domains, field order, lengths,
endianness, delta sign/closure, and padding bytes are identity-bearing.

## Verification and acceptance tests

Known-answer mixer/SHA inputs, changed-content detection, pre/post equality,
index and delta reorder detection, compiler generated-code review, immutable
record loads, private-only state mutation, and no pointer serialization are
required.

## Rollback or supersession

Any changed mixer or byte grammar requires a new algorithm version and
prospective requalification. Existing hashes and consumer results are never
reinterpreted.

## Protocol-amendment assessment

No amendment is required. The protocol explicitly delegates selection of the
fixed consumer operation and physical integrity byte grammar before pilot.
