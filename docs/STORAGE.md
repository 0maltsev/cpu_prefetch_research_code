# Stage 11 Raw-Observation Storage

Protocol version: **`2.0.0-pre.2`**; physical format v1 is unchanged

Scope: bounded producer/consumer capture, the accepted physical codec,
immutable envelopes and integrity records, checked storage budgets, and
crash-aware local publication. Reconciliation, join audits, joined-row
construction, latency derivation, and run disposition are implemented by the
separate Stage 12 offline reconciliation layer.

## Frozen identities

| Contract | Value |
|---|---|
| Physical format | `RAW-OBS-U64LE-LP-RUNID-v1` |
| Encoding | `FIXED_U64_LE_LENGTH_PREFIXED_UTF8_RUN_ID` |
| Logical time unit | `PICOSECONDS` |
| Endianness | `LITTLE_ENDIAN` |
| Compression | `NONE` |
| Durability policy | `RAW-OBS-NONE-TMP1-DUR2-v1` |
| Logical/envelope schema version | Matches its immutable protocol graph (`2.0.0-pre.1` historical or current `2.0.0-pre.2`); no mixed envelope/row graph |
| Canonical JSON | `JCS-I64-v1`, UTF-8, no BOM or trailing newline |

These values implement ADR-0032 and ADR-0033. Unknown or mixed identifiers,
byte order, row counts, hashes, flags, padding, or logical versions fail
closed. Filenames and paths are never decoded as run or artifact identity.

## Logical-to-physical mapping

Every row begins with the literal UTF-8 `run_id`: `u32le(L)`, `L` exact bytes,
and minimum zero padding to `P(L)=round_up(4+L,8)`. The prefix is initialized in
every reserved row before the measurement barrier.

Producer bodies contain exactly 15 little-endian `uint64_t` words:

| Words | Logical/physical value |
|---:|---|
| 0 | `logical_sequence` |
| 1 | `record_index` validation value |
| 2 | `scheduled_arrival` relative picoseconds |
| 3–4 | `producer_handle_begin` absolute raw nanoseconds and relative picoseconds |
| 5–6 | `record_lookup_completion` absolute/relative pair |
| 7–8 | `enqueue_invocation` absolute/relative pair |
| 9–10 | accepted `enqueue_linearization` absolute/relative pair; canonical zeroes for `FULL` |
| 11–12 | `enqueue_attempt_completion` absolute/relative pair |
| 13 | accepted ordinal; canonical zero for `FULL` |
| 14 | flags `15` for `ACCEPTED`, `1` for `FULL` |

Consumer bodies contain exactly 10 words: consumed ordinal, observed record
index, and absolute/relative pairs for dequeue invocation, dequeue
linearization, dequeue completion, and consumer-action completion. Producer
rows remain in logical-arrival order and include every complete attempt;
consumer rows remain in successful-dequeue completion order. Logical sequence,
accepted ordinal, and repeating record index remain distinct types and no
pointer enters a row.

The codec also defines the accepted 24-word joined layout and its decoder for
format compatibility tests. `encode_joined_rows_for_format_test` accepts only
an already-formed logical row. Stage 11 exposes no join, matching, interval, or
production joined-writer operation.

Exact sizes are `b_P=P(L)+120`, `b_C=P(L)+80`, and `b_J=P(L)+192`. With
`run_id="r"`, the C++ encoder and independent Python decoder reproduce the
accepted 256-byte producer, 88-byte consumer, and 200-byte joined vectors and
their three ADR-0032 SHA-256 values.

## Prepared private streams and hot path

`ProducerObservationStream` and `ConsumerObservationStream` allocate one fixed
64-byte-aligned region and keep their 64-byte control blocks separate. Capacity
and byte arithmetic are checked before allocation. There is no growth path.

Allocation does not establish NUMA ownership. The already-affined producer and
consumer must each call their stream's `prepare_for_owner()` during
preparation. That call initializes and first-touches every reserved byte and
every prefix. Append rejects an unprepared stream. Stage 9/16 still has to bind
and independently verify the actual buffer pages; the API does not infer a
node or page size.

One producer append performs only:

1. prepared/sealed, accepted-field, and capacity checks;
2. selection of canonical accepted/`FULL` flags and absent values;
3. fixed little-endian stores of the 15 already-captured words; and
4. commit of `row_count` after the complete body.

One consumer append performs the corresponding state/capacity checks, 10 fixed
word stores, and final row-count commit. There is no allocator, filesystem,
compression, JSON, lock, clock, queue retry, logging, checksum finalization, or
analysis call in either append body. `CapturingObservationBackend` statically
connects the Stage 8 capture and Stage 10 backend seams and reports an attempt
or item complete only after the fixed row commits. Overflow sets a sticky
incomplete state and returns failure; it never truncates, wraps, aggregates, or
overwrites.

The release generated-code checker inspects both append bodies with GNU and
LLVM disassemblers. It rejects call, lock, fence, syscall, and memory-exchange
classes, while recording the compiler-inserted fail-closed
`__stack_chk_fail` guard separately. A deliberate call-injection mutant must
be rejected. This is instruction-presence evidence only, not a performance
observation.

## Post-run integrity and envelopes

SHA-256 covers the exact headerless raw bytes. `decode_external_raw` requires
the imported external-storage envelope and validates its entire selected suite,
SHA, exact count/size, literal row identity, padding, flags, absent values,
ordinal/order continuity, and existing record-local timestamp semantics. It
retains raw absolute nanoseconds and logical relative picoseconds. Clock-origin
proof and cross-stream timestamps remain Stage 12 invariants.

The imported envelope is not extended. `integrity_artifact_ref` names an
immutable `cpu-prefetch-phase-integrity-report/1` document containing:

- final consumer state under
  `cpu-prefetch/consumer-mix64-adr0027/v1`;
- pre/post record content under the accepted
  `cpu-prefetch/event-record-content-sha256/v1` grammar;
- ordered indices under `cpu-prefetch/ordered-index-sha256/v1`; and
- address deltas under `cpu-prefetch/address-delta-sha256/v1`.

Every evidence item records algorithm record ID, version `1`, and lowercase
hex value. The report also records pre/post equality without suppressing a
mismatch. A mismatch may invalidate a run later; it does not authorize
destruction of the raw evidence.

`cpu-prefetch-copy-ledger-record/1` is implementation-owned and remains outside
the imported envelope. It records object/subject identity, exact bytes/hash,
stream completeness, policy/counts, each domain/URI/readback/result/timestamp,
failures, and `SEALED_COMPLETE` or `INCOMPLETE`. Here, sealed completion means
the bytes and two copies finalized; it is not a claim that the scientific run
is valid, reconciled, zero-loss, or estimable.

## Append-only publication and recovery

The Linux local backend requires two explicit, distinct domain IDs and two
distinct existing roots. It creates a unique run directory derived from a
SHA-256 path-safe encoding of the stored `run_id`; the literal ID remains in
the records and is never reconstructed from that path. Object and artifact IDs
are reserved once.

Publication occurs only after measurement:

1. uniquely create a staging object with no replacement;
2. perform checked writes and file sync;
3. independently reread its exact size and streaming SHA-256;
4. publish with an atomic same-filesystem hard link that fails if the target
   exists;
5. sync and independently reread the published object;
6. repeat sequentially in the second explicit domain; and
7. stage, reread, no-replace publish, and directory-sync a unique copy-ledger
   record in separate `ledger-staging/` and final `ledger/` namespaces.

No verified object is removed after a failure. Partial ledger bytes remain only
in `ledger-staging/` and cannot be mistaken for a sealed ledger record. A
partial write, sync failure,
hash mismatch, second-copy failure, duplicate ID, or ledger failure returns an
incomplete result. A fresh process may reopen the exact existing run directory
in recovery-only mode. That mode forbids new publication and can promote a
unique staging candidate only after exact expected size and SHA verification,
using the same no-replace operation. An unmatched candidate remains evidence
and a published object is never rewritten. The local backend proves software
behavior only: two local paths do not establish independent production failure
domains or custody.

`finalize_run_observations` publishes the phase/integrity report and whichever
sealed producer/consumer streams actually exist, followed by their immutable
envelopes. A missing stream stays missing. A partial stream may be preserved
with an incomplete ledger. No join audit or joined-derived artifact is emitted.

## Checked capacity model

For each concrete run the implementation calculates actual hot payload,
conservative hot mappings, page rounding, and retained raw bytes with checked
`uint64_t` arithmetic:

```text
B_hot,actual = N_sched*b_P + N_acc*b_C
B_hot,conservative = N_sched*(b_P+b_C)
B_raw,total = 3*(N_sched*b_P + N_acc*b_C) + 2*N_acc*b_J
```

Producer and conservative consumer mappings are rounded separately to the
explicit verified base-page size. `N_acc<=N_sched` and, when known,
`N_eff<=N_acc` are mandatory. The report separately flags the protocol's
`200000` and `2000000` effective-count thresholds; these flags never request a
repeat or extend a run.

The complete Stage A proof requires exactly `180*Rtotal` concrete run terms,
one explicit block per `Rtotal` unit, `m_tmp=1`, `m_dur=2`, and exact additional
bytes for envelopes, integrity reports, ledgers, schedules, manifests,
filesystem overhead, and operator reserve. Available bytes and base-page size
are mandatory explicit inputs. Capacity failure blocks measurement; a later
hot overflow is an invalidating measurement failure.

## Verification commands

```sh
cmake --build --preset dev-gcc
ctest --preset dev-gcc -L storage
cmake --build --preset dev-gcc --target storage-format-check
cmake --build --preset dev-gcc --target storage-schema-check
cmake --build --preset release-gcc --target storage-codegen-check
```

Run the same storage-labelled tests under the accepted ASan/UBSan and TSan
presets. The 200,000-row synthetic smoke is correctness-only and emits no
elapsed time, latency, throughput, treatment comparison, or result artifact.

## Later gates

Stage 12 resolves immutable references/hashes, proves raw absolute/relative
clock-origin relationships, reconciles only by `(run_id, accepted_ordinal)`,
emits a join audit for every attempt, and creates joined rows only after a
passed audit. Phase 16 must supply the exact run plan, page residency, available hot
and durable capacity plus reserve, two real independent storage domains,
permissions/custody, and an exact-release crash/recovery exercise. Until those
gates pass, pilot and performance measurement remain prohibited.
