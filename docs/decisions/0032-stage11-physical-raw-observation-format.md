# ADR-0032: Stage 11 physical raw-observation format

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Physical data representation / measured-path / compatibility
- Decision owners: Repository owner; storage owner; data-integrity owner; timing and code-generation reviewer
- Protocol version: `2.0.0-pre.1`
- Supersedes: None; selects the physical format left open by ADR-0002 and D-010
- Lifecycle gate: Accepted before Stage 11 implementation; implementation, capacity, and generated-code evidence before pilot

## Context and scientific constraints

The protocol fixes the logical producer, consumer, and joined rows, exact
integer timestamps, literal per-row `run_id`, independent ordered worker
streams, external immutable production artifacts, and fail-on-overflow
behavior. It deliberately leaves the physical format open. The timed path may
write only to prepared thread-private storage and cannot allocate, grow, lock,
format, perform I/O, compress, aggregate, or analyze.

ADR-0002 requires a replaceable codec rather than an ABI layout. ADR-0030's
clock samples retain absolute raw nanoseconds and exact relative picoseconds.
The physical row write footprint is measured-path behavior, so its exact
prospective form requires owner acceptance and final generated-code evidence.

## Options considered

1. Dump native C++ object representations.
2. Store JCS/JSON rows as primary raw data.
3. Use Arrow IPC or Parquet.
4. Use versioned fixed binary bodies with a literal length-prefixed row ID and
   an imported external-artifact envelope.

## Decision

Select option 4 exactly as specified in the accepted
[`STAGE11_STORAGE_DECISION_BUNDLE.md`](../STAGE11_STORAGE_DECISION_BUNDLE.md):

- suite and `physical_format_record_id`
  `RAW-OBS-U64LE-LP-RUNID-v1`;
- encoding `FIXED_U64_LE_LENGTH_PREFIXED_UTF8_RUN_ID`, time unit
  `PICOSECONDS`, endianness `LITTLE_ENDIAN`, and compression `NONE`;
- no file header/trailer/BOM/newline; the external artifact SHA-256 covers the
  exact row bytes, while the imported envelope is uncompressed UTF-8
  `JCS-I64-v1`;
- every row starts with a little-endian `uint32_t` UTF-8 byte length, the exact
  nonempty literal `run_id`, and minimum zero padding to an eight-byte
  boundary; prefixes are initialized before measurement;
- 64-byte-aligned worker-private buffer bases, eight-byte-aligned row starts
  and numeric bodies, separate cache-line control metadata, and no native ABI
  dump;
- producer bodies contain the accepted fifteen-word/120-byte raw-nanosecond
  and relative-picosecond layout, with flags exactly `15` for `ACCEPTED` and
  `1` for `FULL` and canonical zeroes for absent accepted-only fields;
- consumer bodies contain the accepted ten-word/80-byte raw-nanosecond and
  relative-picosecond layout;
- joined-derived bodies contain the 24 imported logical `uint64_t` fields in
  schema order, totaling 192 bytes;
- for `P(L)=round_up(4+L,8)`, exact row sizes are
  `b_P=P(L)+120`, `b_C=P(L)+80`, and `b_J=P(L)+192`;
- physical and logical order, exact row and byte counts, literal row/envelope
  identity, padding, flags, absent values, arithmetic, and versions all fail
  closed.

The complete word order, flags, empty-stream rule, synthetic input vectors,
and expected producer/consumer/joined SHA-256 values in the accepted bundle
are normative parts of this decision. Filenames, paths, suffixes, inferred row
sizes, pointers, and host ABI never identify or complete a row.

## Evidence

- Imported implementation specification Sections 8.1, 8.3, 8.4, 11, and 12;
  data dictionary; raw-observation schema; freeze checklist; and imported
  implementation decisions.
- ADR-0002, ADR-0004, ADR-0005, ADR-0015, ADR-0017, ADR-0022, ADR-0023,
  ADR-0030, and ADR-0031.
- Exact prospective size formulas and independently recomputed synthetic byte
  hashes recorded in the decision bundle.
- The repository owner answered `Q9 - accept the bundle` on 2026-08-21. No
  queue or performance outcome was used.

## Consequences and compatibility

Scientific effect: this freezes the amount and order of per-event observation
writing, including both clock representations, without changing any logical
field, timestamp boundary, queue operation, lifecycle, or estimand. Literal ID
bytes are prepared before measurement, so no timed string work is added.

Compatibility effect: suite ID, byte order, prefix, padding, flags, word order,
row-size formulas, clock pairs, envelope encoding, and count/order rules are
format identity. Unknown or mismatched values fail closed. A future Arrow,
Parquet, textual, big-endian, logical-only, or changed-row representation is a
new physical format and cannot reinterpret v1 bytes.

## Verification and acceptance tests

Stage 11 must implement and pass all bundle checks before software closure:
C++/Python independent golden parity, all three stream round trips, imported
logical-row conformance, exact ID/count/byte/SHA/order validation, maximum and
empty boundaries, corruption/truncation/trailing/padding/flags/mixed-version
negatives, private-buffer ownership and overflow, no hot allocation/I/O/lock/
format/compression, supported sanitizer matrices, and final integrated
dual-disassembler/mutant review. Q9 accepts expected behavior; it is not test
evidence.

The exact run plan, page-residency proof, memory/disk capacity, release build,
and stand remain Phase 16/pre-pilot evidence.

## Rollback or supersession

A byte-affecting change requires a new format ID, superseding ADR, new goldens,
converter or separately identified derived artifact, and full prospective
requalification. Existing source bytes, envelopes, IDs, and hashes remain
immutable and are never rewritten. Rollback means rejecting the new producer,
not reinterpreting old data.

## Protocol-amendment assessment

No amendment is required because the protocol explicitly delegates physical
encoding while fixing the logical rows. Any proposed logical-field, identity,
ordering, timestamp, or failure-semantics change requires protocol review and
normally a versioned amendment.
