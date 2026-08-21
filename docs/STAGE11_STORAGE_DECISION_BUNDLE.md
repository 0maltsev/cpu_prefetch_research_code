# Stage 11 Physical-Storage Decision Bundle

Protocol version: **`2.0.0-pre.1`**

Decision IDs: **D-010** and **D-020**  
Approval question: **Q9**  
State: **`ACCEPTED_BY_Q9`**

The repository owner accepted this bundle exactly as published by answering
`Q9 - accept the bundle` on 2026-08-21. D-010 and D-020 are recorded separately
in ADR-0032 and ADR-0033. Acceptance authorizes Stage 11 implementation only;
it does not claim any implementation/evidence gate has passed and authorizes
no experiment execution.

## Decision records

| Field | D-010 accepted value | D-020 accepted value |
|---|---|---|
| Classification | Physical data representation with measured-path and scientific-integrity consequences | Artifact durability, compression, and recovery policy |
| Owners | Repository owner; storage owner; data-integrity owner; timing/code-generation reviewer | Repository owner; storage owner; data custodian; recovery owner |
| Deadline / gate | Accept before Stage 11 implementation; implementation/capacity/code-generation evidence before pilot | Accept before Stage 11 implementation; operational durability-domain evidence by Stage 16 and before pilot |
| Selected suite/policy | `RAW-OBS-U64LE-LP-RUNID-v1` | `RAW-OBS-NONE-TMP1-DUR2-v1` |
| Supersession | New format ID and decoder/converter; retain old raw bytes and emit a new derived artifact | New policy ID prospectively; never rewrite or delete a v1 canonical raw source as part of migration |

## Protocol constraints preserved

The imported protocol fixes the logical producer, consumer, and joined rows;
their exact integer timestamp meanings; independent ordered producer and
consumer capture; literal per-row `run_id`; accepted ordinal as the join key;
and append-only partial-failure behavior. It requires preallocated
thread-private measurement buffers, makes overflow a measurement failure, and
forbids allocation, dynamic growth, locks, file I/O, formatting, aggregation,
compression, and analysis in the measured path. Production raw envelopes must
reference external immutable artifacts. Compression, when selected, is
lossless and post-measurement and receives no hot-capacity credit.

This bundle does not change any logical field, timestamp equation, lifecycle,
queue behavior, validity rule, zero-loss rule, effective-tail rule, schedule,
clock, platform value, horizon, run count, seed, or treatment. It does not
select storage-domain names, paths, filesystems, quotas, reserve bytes, or
custodians. Those facts require explicit later evidence.

## Evidence used

- Imported implementation specification Sections 8.1, 8.3, 8.4, 11, and 12;
  the complete data dictionary; `raw-observation.schema.json`; the freeze
  checklist; and the imported implementation-decision list.
- ADR-0002, ADR-0004, and ADR-0005 require a replaceable codec, explicit
  versions, fail-closed readers, immutable source bytes, and append-only
  failure/correction evidence.
- ADR-0015 selects SHA-256 and `JCS-I64-v1`; ADR-0017 selects the correctness
  and sanitizer gate; ADR-0021 grants no repository license; ADR-0022 forbids
  an unapproved convenience dependency; ADR-0023 preserves the imported
  logical model; ADR-0030 retains absolute clock nanoseconds and exact relative
  picoseconds; ADR-0031 requires prepared storage and complete capture before a
  backend reports success.
- The current dependency inventory contains no Arrow, Parquet, or compression
  library. Python 3.14 is already accepted as an offline verification tool and
  can provide an independent standard-library decoder without adding a
  dependency.

No queue timing, latency, throughput, pilot, or treatment outcome was used.

## D-010 options considered

| Option | Merits | Material problem | Recommendation |
|---|---|---|---|
| Dump native C++ structs | Minimal source code | ABI padding, `std::optional`, endianness, and compiler layout are not a portable or independently decodable contract | Reject |
| JCS/JSON rows | Directly resembles the logical schema | Variable formatting and string work would be unacceptable in the measured path; substantially larger hot writes | Reject as primary raw storage; retain inline JSON only for protocol fixtures |
| Arrow IPC or Parquet | Mature tabular ecosystem and offline analysis support | Adds unapproved dependencies/licenses and a more complex allocation/buffering/encoding surface; Parquet compression/encoding is not a fixed hot-row contract | Do not select for v1; an offline derived artifact may be proposed later |
| Fixed binary rows with an envelope | Exact capacity, simple checked codec, direct preallocation, independent decoder, no new dependency | The row layout and write footprint become measured-path behavior and must be frozen and audited | **Recommend** |

## Accepted D-010 exact format

### Identity and imported-envelope binding

The suite ID and `physical_format_record_id` are exactly
`RAW-OBS-U64LE-LP-RUNID-v1`. The imported raw envelope fields are bound as
follows:

| Imported field | Accepted exact value/rule |
|---|---|
| `logical_row_schema_version` | `2.0.0-pre.1` |
| `physical_format_record_id` | `RAW-OBS-U64LE-LP-RUNID-v1` |
| `encoding` | `FIXED_U64_LE_LENGTH_PREFIXED_UTF8_RUN_ID` |
| `time_unit` | `PICOSECONDS` |
| `endianness` | `LITTLE_ENDIAN` |
| `compression` | `NONE` |
| `immutable_ordering` | `true` |
| `storage.mode` | `EXTERNAL_IMMUTABLE_ARTIFACT` in production; `INLINE_TEST_ONLY` remains fixtures/examples only |
| `artifact_sha256` | SHA-256 of the exact external row bytes, with no header, trailer, BOM, or newline |

The stream kind in the envelope selects the producer, consumer, or joined body
below. Filenames, suffixes, paths, row-size guesses, and host ABI are never
used to select a decoder.

The envelope itself is uncompressed UTF-8 `JCS-I64-v1`, with no BOM or trailing
newline. It has no fixed byte length because its normative IDs and URI are
variable strings. Its exact size is
`len(UTF8(JCS-I64-v1(envelope)))` after every value is bound and is included in
the pre-run storage proof. The envelope SHA-256 and copy locations live in the
append-only artifact/copy ledger rather than adding a field to the imported
schema or creating a self-hash cycle.

### Common row prefix and alignment

Let `L` be the exact byte length of the row's literal UTF-8 `run_id` and define:

```text
P(L) = round_up(4 + L, 8)
```

Every physical row starts with:

1. `L` as an unsigned 32-bit little-endian integer;
2. exactly `L` UTF-8 bytes, without normalization or a terminator;
3. the minimum zero padding needed to reach `P(L)` bytes.

`L` must be nonzero and fit `uint32_t`; all size calculations must also fit
`uint64_t` and the host `size_t`. Invalid UTF-8, nonzero padding, a different
row/envelope ID, truncation, or arithmetic overflow fails closed. The literal
prefix is prepared in every reserved producer and consumer row before the
measurement barrier, so each physical row carries `run_id` without timed
string formatting, copying, lookup, or a serialized pointer.

Each worker-private buffer begins at a 64-byte-aligned address. Every row start
and numeric body is 8-byte aligned; rows are not padded to cache-line size.
Producer and consumer control metadata occupy separate cache lines and are not
writable by the other worker. The implementation must use explicit
little-endian loads/stores and compile-time size/offset assertions; dumping a
C++ object representation is forbidden.

### Producer body

The producer body is exactly fifteen unsigned 64-bit little-endian words
(120 bytes), in this order:

| Word | Field |
|---:|---|
| 0 | `logical_sequence` |
| 1 | `record_index` |
| 2 | `scheduled_arrival` in relative picoseconds |
| 3, 4 | `producer_handle_begin`: absolute raw nanoseconds, relative picoseconds |
| 5, 6 | `record_lookup_completion`: absolute raw nanoseconds, relative picoseconds |
| 7, 8 | `enqueue_invocation`: absolute raw nanoseconds, relative picoseconds |
| 9, 10 | `enqueue_linearization`: absolute raw nanoseconds, relative picoseconds, or canonical zeroes when absent |
| 11, 12 | `enqueue_attempt_completion`: absolute raw nanoseconds, relative picoseconds |
| 13 | `accepted_ordinal`, or canonical zero when absent |
| 14 | flags word |

The flags word is exactly `15` for `ACCEPTED` and exactly `1` for `FULL`:
bit 0 is `attempted`, bit 1 is accepted outcome, bit 2 is linearization
presence, and bit 3 is ordinal presence. All other bits are zero. A decoder
rejects every other combination. Thus an ordinal value of zero remains
distinguishable from absence, and `FULL` cannot fabricate accepted-only data.

The exact producer row size is:

```text
b_P(L) = P(L) + 120
```

### Consumer body

The consumer body is exactly ten unsigned 64-bit little-endian words
(80 bytes), in this order:

| Word | Field |
|---:|---|
| 0 | `consumed_ordinal` |
| 1 | `observed_record_index` |
| 2, 3 | `dequeue_invocation`: absolute raw nanoseconds, relative picoseconds |
| 4, 5 | `dequeue_linearization`: absolute raw nanoseconds, relative picoseconds |
| 6, 7 | `dequeue_completion`: absolute raw nanoseconds, relative picoseconds |
| 8, 9 | `consumer_action_completion`: absolute raw nanoseconds, relative picoseconds |

The exact consumer row size is:

```text
b_C(L) = P(L) + 80
```

Absolute nanoseconds preserve the accepted clock reader's raw output. The
imported logical decoder emits the corresponding relative-picosecond fields.
The later cross-record validator proves their exact origin/conversion relation;
the physical decoder must not invent an origin.

### Joined-derived body

The joined body is post-run data and contains exactly the 24 unsigned 64-bit
logical fields in the imported schema order, from `accepted_ordinal` through
`end_to_end_latency` (192 bytes). It does not duplicate the implementation-only
absolute nanoseconds because its two immutable source artifacts and hashes are
normative inputs.

```text
b_J(L) = P(L) + 192
```

### Ordering and exact counts

- Producer byte order is logical-arrival order and retains every complete
  `ACCEPTED` and `FULL` attempt.
- Consumer byte order is successful-dequeue completion order.
- Joined order is accepted-ordinal order after a passed Stage 12 audit.
- The decoder consumes exactly `row_count` rows and requires
  `byte_count == row_count * b_kind(L)` using checked arithmetic. It rejects
  trailing bytes, partial rows, prefix disagreement, noncanonical absent
  values, impossible flags, or an ordering/key discontinuity.
- An empty stream has zero artifact bytes and the standard SHA-256 of the empty
  byte string; per-row identity is then vacuously satisfied. No empty-stream
  special file header is introduced.

### Synthetic codec vectors

These are format evidence only, not experiment observations. With literal
`run_id="r"`, `P(1)=8`; producer, consumer, and joined row strides are 128,
88, and 200 bytes. After the common prefix, the exact decimal word arrays are:

```text
producer ACCEPTED = [0,7,500,101,1000,102,2000,103,3000,104,4000,105,5000,0,15]
producer FULL     = [1,8,1500,102,2000,103,3000,104,4000,0,0,105,5000,0,1]
consumer          = [0,7,105,5000,106,6000,107,7000,108,8000]
joined            = [0,0,7,0,0,500,1000,2000,3000,4000,5000,5000,
                     6000,7000,8000,500,1000,2000,3500,2000,2000,
                     2000,1000,7500]
```

The two producer rows are concatenated in the shown order. The accepted
fixtures produce:

| Stream fixture | Rows | Byte count | SHA-256 |
|---|---:|---:|---|
| One valid accepted producer row followed by one canonical `FULL` row | 2 | 256 | `c6b47e3a4e73fa26e913ccd9101bd68e72bc3de4a488c3e3332fc65c7c61787c` |
| Matching successful consumer row | 1 | 88 | `0ed5a56f76a293b344eca47c684558d7fe6e46cebffd06981a446fd2c667a888` |
| Matching joined-derived row with exact interval equations | 1 | 200 | `f02f4b2bc4a035dba7b9d5e91bb38a20aa2d309c19d81f49b9054aad9bc28f2a` |

Stage 11 must store the complete bytes as reviewed fixtures and require C++20
encoder/decoder parity with an independently implemented Python 3.14
standard-library decoder. These accepted expected hashes are not Stage 11 acceptance
evidence until that implementation reproduces them.

## D-020 options considered

| Option | Merits | Material problem | Recommendation |
|---|---|---|---|
| No compression, one durable instance | Small implementation | One storage-domain failure can remove primary observations | Reject for production eligibility |
| No compression, two independently verified durable instances | No codec dependency; exact capacity; identical hashes; simpler recovery | Uses the conservative maximum storage footprint and still needs named independent domains | **Recommend** |
| Post-run zstd or another lossless codec, two instances | Can reduce retained size | Adds an unapproved dependency/license and codec-version/corruption/recovery surface; compression cannot reduce hot capacity | Do not select for v1 |
| One raw and one compressed instance | Saves some space | The two instances are not byte-identical, complicating identity and recovery authority | Reject for v1 |

## Accepted D-020 exact policy

Select `RAW-OBS-NONE-TMP1-DUR2-v1`:

- `compression=NONE`; canonical producer, consumer, and joined bytes are never
  compressed by v1.
- `m_tmp=1`: capacity reserves at most one complete temporary
  producer/consumer raw work image in addition to durable instances.
  Publication/copying is sequential. A unique filesystem staging object that
  becomes the verified primary is counted within `m_dur`, not again as a
  simultaneous temporary copy.
- `m_dur=2`: production eligibility requires exactly two byte-identical,
  independently read-back and SHA-256-verified durable instances, including
  the primary, in two explicitly different `storage_domain_id` values.
- Both durable instances carry the same artifact ID, byte count, and raw
  SHA-256. A URI is a location, never identity.
- Every write, hash, verification, sync, publication, replication, ledger
  update, and recovery action occurs after measurement. Compression/copy code
  is unreachable from the timed worker graph.
- Joined rows are streamed after a passed audit into the unique no-replace
  primary and then replicated; no complete temporary joined artifact is
  materialized. This preserves the imported formula's `m_dur*N_acc*b_J` term.
- The Linux local-store backend uses unique create/no-overwrite staging,
  complete checked writes, data sync, independent reread/size/hash, atomic
  no-replace publication, and directory sync. A backend that cannot prove
  equivalent no-overwrite and durability semantics fails capability
  validation.
- A copy ledger is append-only and records policy ID, artifact ID/hash/size,
  two distinct domain IDs and URIs, verification timestamps/results, and
  complete/incomplete state. The imported raw envelope remains unmodified.
- Raw source deletion is not an automatic operation. A failed second copy,
  disk exhaustion, crash, or sync/readback mismatch retains every verified
  instance and an incomplete ledger/failure record; it never relabels one copy
  as two, overwrites a source, truncates the run, or retries measurement.
- Crash recovery may promote a unique staging candidate only after exact
  expected size and SHA verification. Otherwise it remains quarantined
  non-artifact evidence. Recovery never mutates a published artifact or reuses
  an artifact ID for changed bytes.
- Partial measurement streams that exist are subject to the same preservation
  and ledger rules. Missing streams are recorded as absent and are never
  fabricated.

The repository contains no production storage-domain or custody facts. Stage
11 therefore implements a replaceable store plus fake/local correctness
backends. Stage 16 must bind and independently prove two real failure domains,
permissions, free-space evidence, no-overwrite behavior, recovery, and named
custody before pilot eligibility.

## Capacity contract

For each run, let `L_r` be the UTF-8 `run_id` byte count and use the exact row
formulas above. The hot payload bound is:

```text
B_hot,r = N_sched,r * b_P(L_r) + N_sched,r * b_C(L_r)
```

The second term is conservatively sized to scheduled count because
`N_acc,r <= N_sched,r`. Each private mapping is additionally rounded up to the
explicit verified base-page size; allocation bookkeeping/control pages and the
prepared schedule/records are accounted separately. All pages are allocated,
initialized, touched, bound, and independently residency-verified before the
measurement barrier. No compression ratio is used.

With accepted `m_tmp=1` and `m_dur=2`, the imported total-storage formula is:

```text
B_total >= sum_r [3 * (N_sched,r*b_P(L_r) + N_acc,r*b_C(L_r))
                  + 2 * N_acc,r*b_J(L_r)]
```

Before acceptance of a concrete run plan, checked arithmetic must add the
exact canonical envelope, integrity, ledger, schedule, manifest, filesystem,
and operator-reserved bytes. Available capacity, reserve, filesystem, storage
domains, `N_sched`, horizons, `Rtotal`, and actual `run_id` values are later
explicit inputs—not defaults in this bundle. The proof must cover the longest
planned run, all `180*Rtotal` runs, staging peak, partial-failure retention, and
both durable instances. Failure blocks the run before measurement; hot overflow
after start is a measurement failure and never enables aggregation, overwrite,
extension, or retry.

## Required Stage 11 verification after approval

Approval would authorize implementation, not declare these checks passed:

1. exact C++/Python golden and boundary round trips for all three stream kinds,
   including maximum `uint64_t`, long UTF-8 IDs, `FULL`, and empty streams;
2. imported-schema validation of every decoded logical row and exact
   envelope/row `run_id` equality;
3. corruption, changed flags/padding, truncation, trailing bytes, row-count,
   byte-count, SHA, reorder, duplicate, and mixed-version rejection;
4. preallocated ownership, capacity-boundary, overflow, allocation/I/O/lock/
   formatting/compression interception, and final integrated worker
   dual-disassembler evidence;
5. raw absolute-nanosecond/relative-picosecond preservation and later exact
   origin-conversion validation;
6. immutable publication, no-overwrite, staged-crash, disk-exhaustion,
   partial-copy, readback disagreement, recovery, and append-only correction
   tests;
7. checked `B_hot`/`B_total` properties, page rounding, `m_tmp=1`, `m_dur=2`,
   and no compression credit;
8. applicable unit/property/stress, GCC/Clang, ASan/UBSan, and TSan evidence;
9. dependency/license review confirming no new library and no repository
   license grant; and
10. Phase 16 repetition on the exact release and named durable domains before
    any pilot.

## Scientific and compatibility effects

Scientific effect: the recommended producer/consumer layout fixes the amount
and order of per-event observation writing, including retention of each clock
read's absolute nanoseconds and relative picoseconds. It is therefore a
prospective measured-path choice requiring generated-code review. The choice
does not change a timestamp boundary or logical value. Run-ID prefixes are
preinitialized, so identity is literal in every row without timed string work.
No performance result selected the layout.

Compatibility effect: byte order, prefix grammar, zero padding, word order,
flags, row-size formulas, absolute/raw pairs, envelope encoding, format ID,
compression identity, and copy counts are version-defining. Unknown IDs,
native-ABI dumps, big-endian reinterpretation, noncanonical flags/padding, one
durable copy, compressed v1 bytes, or inferred storage domains fail closed.
Changing any of them requires a new format/policy ID, superseding ADRs,
converters or derived artifacts, and full prospective requalification. Logical
schema changes still require a protocol amendment.

## Remaining evidence that approval does not invent

| Gate | Still required after Q9 |
|---|---|
| Stage 11 software closure | Implement both ADRs and pass every codec, buffer, corruption, publication, capacity, sanitizer, and code-generation check above |
| Phase 12 | Cross-record reconciliation, source-hash resolution, absolute/relative clock-origin proof, joined publication, and D-031 resolution |
| Phase 16 / pre-pilot | Exact horizons/counts/run IDs, mapped-memory and disk capacity with explicit reserve, real independent storage domains, custody/permissions, crash-recovery exercise, and exact-release repetition |
| Pilot/confirmation | All unrelated platform, clock, hardware-state, environment, calibration, statistical, access, budget, and authorization gates |

## Approval record

The repository owner accepted D-010 as `RAW-OBS-U64LE-LP-RUNID-v1` and D-020
as `RAW-OBS-NONE-TMP1-DUR2-v1`, exactly as specified in this bundle, by
answering on 2026-08-21:

```text
Q9 - accept the bundle
```

D-010/ADR-0032 and D-020/ADR-0033 are therefore `ACCEPTED`. Stage 11
implementation may begin, but every software and Phase 16 evidence gate listed
above remains open. A change now requires the recorded supersession process;
this accepted bundle is not rewritten.
