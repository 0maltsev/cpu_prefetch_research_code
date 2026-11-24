# ADR-0053: Freeze Q15 pointer-probe construction and integrity

- Status: `ACCEPTED_AND_IMPLEMENTED_SOFTWARE_ONLY`
- Date: 2026-08-24
- Decision ID: D-053
- Classification: deterministic qualification-probe construction and integrity
- Decision owners: repository owner; protocol, platform, reproducibility,
  compiler, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: the ambiguous `seed_derivation` interpretation in ADR-0052 only;
  every other D-052 contract and authority boundary remains unchanged
- Lifecycle gate: Q15 qualification-tool implementation before Q15-R

## Context and scientific constraints

ADR-0052 froze a 256-bit `seed_hex`, a named permutation algorithm, and a
single dependent cycle, but its prose did not say unambiguously whether that
value was an ADR-0025 master seed or an already-derived stream seed. A Philox
key is only 64 bits, so silently truncating or rehashing the frozen value would
create incompatible probe orders. Integrity also needed an exact boundary so
checksum work could not contaminate the counted traversal.

This is qualification-only software. It cannot use treatment outcomes, select
a scientific setting, access a stand, execute a PMU/MSR command, or authorize
Q15-R/Q15-W, calibration, pilot, or confirmatory work.

## Options considered

1. Truncate `seed_hex` directly into a Philox key.
2. Hash the namespace literal and treat the hash as the permutation seed.
3. Treat `seed_hex` as the ADR-0025 256-bit master seed, derive the stream with
   the exact namespace and `node-order` purpose, then use ADR-0026.
4. Leave the order and integrity boundary unresolved.

For integrity, the considered choices were a checksum accumulator inside the
counted loop, partial sampled hashes, or complete pre/post buffer SHA-256 plus
exact cycle closure outside the counted loop.

## Decision

Select option 3 and complete-buffer integrity outside the counted traversal.
The normative companion record is
`config/q15/q15-probe-implementation-profile-v1.json`, profile ID
`Q15-PROBE-IMPLEMENTATION-PROFILE-v1`.

- Parse the frozen 64-hex-digit value as an ADR-0025 `MasterSeed`.
- Derive the Philox key with suite `PHILOX4X32-10-HMAC-SHA256-v1`, ADR-0025's
  frozen derivation-domain protocol label `2.0.0-pre.1`, namespace
  `Q15-POINTER-PROBE-PERMUTATION-v1`, and purpose `node-order`. The resulting
  key bytes are `2a805cfaa4038e43`.
- Apply ADR-0026's descending Fisher-Yates order with unbiased unsigned 64-bit
  rejection sampling. `permutation[0]` is the traversal start; every cache
  line stores the next line's `uint32_t` index at offset zero, and the final
  line links back to the start. The remaining bytes are zero. This physical
  encoding is limited to the already accepted little-endian Linux x86-64 Q15
  target.
- Hash the complete initialized buffer with raw SHA-256 before and after the
  traversal. After exactly `line_count` dependent loads, require the final
  index to equal the start index. Perform no SHA/checksum work inside either
  counted traversal.
- The regular counted body has one volatile 64-bit load per ascending line.
  The pointer body has one dependent volatile 32-bit load per line. Both return
  only a load-retention/integrity value; no time or performance result is
  produced.
- Pointer H0 count zero remains the accepted D-052
  `NOT_DISTINGUISHABLE_WHERE_NOT_POSSIBLE` classification. It is not silently
  promoted to distinguished and does not invalidate an otherwise accepted
  regular probe.

## Evidence

- Explicit Q15-S2 owner acceptance on 2026-08-24.
- ADR-0025 and ADR-0026 deterministic bit-level contracts.
- Frozen D-052 contract SHA-256
  `c5a13646ea5e413239337e1b83b3162578c35591a54d6002f656a78acfd3d531`.
- Independent HMAC/Philox calculation: key `2a805cfaa4038e43`, eight-line order
  `5,2,6,3,0,7,4,1`, and complete 512-byte buffer SHA-256
  `7cefdcad16f83055ae3a1b3219ebfcfe8b131a82afa959fe0fc348818724d540`.
- Local unit, negative, sanitizer, and dual-disassembler evidence; no stand,
  PMU, MSR, calibration, or scientific execution.

## Consequences and compatibility

Scientific effect: none beyond making D-052's prospective behavioral probe
reproducible and auditable. The decision does not alter Stage A packages,
workloads, factors, outcomes, or analysis.

Compatibility effect: the master-seed interpretation, ADR-0025 field grammar,
namespace, purpose, key bytes, Fisher-Yates direction/rejection behavior, start
index, line encoding, complete buffer bytes/hash, exact load count, closure,
and checksum boundary are probe identity. Any change requires a new profile and
fresh qualification evidence.

## Verification and acceptance tests

Tests pin the derived key, golden order, full-buffer hash, alignment/zero-fill,
single-cycle bijection and closure, invalid counts and corrupt cycles, pre/post
hash equality, fault/multiplex/H0/H1 classifications, and both pointer-H0
classes. Release generated code must pass GNU and accepted LLVM disassembly:
each accepted traversal exposes exactly one static demand-load instruction, no
call or prefetch/fence/system instruction, and negative mutants expose an extra
load or forbidden prefetch. Sanitizers remain mandatory.

The source implementation deliberately exposes no dynamic PMU command. Thus
successful local tests do not satisfy Q15-R or Q15-W and do not qualify the
candidate stand.

## Rollback or supersession

Never reinterpret an executed profile. A bit-level or integrity-boundary
change requires a new profile ID, superseding ADR, clean tool release, new
generated-code evidence, and full requalification. D-052 remains the source
contract for every unaffected field.

## Protocol-amendment assessment

No amendment is required. The imported protocol delegates exact deterministic
probe implementation and requires behavioral distinction only prospectively;
this decision resolves an implementation ambiguity without changing that
scientific requirement.
