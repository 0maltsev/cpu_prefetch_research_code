# Stage 6 Workload Construction

Protocol version: **`2.0.0-pre.1`**

Scope: deterministic record and node working sets plus the five Stage A package
mechanisms. This code performs no scheduling, clock read, performance
measurement, platform actuation, raw publication, or analysis.

## Accepted deterministic suite

`PHILOX4X32-10-HMAC-SHA256-v1` is frozen by ADR-0025 through ADR-0027.
The repository contains an independent Philox4x32-10 core and no Random123
source or dependency. A 256-bit master seed is the OpenSSL HMAC-SHA-256 key.
The HMAC message is four length-prefixed UTF-8 fields in fixed order:
`2.0.0-pre.1`, suite ID, namespace, and purpose. Lengths are unsigned 64-bit
big-endian values.

The first eight digest bytes become two big-endian Philox key words. A 64-bit
block ordinal becomes counter words zero and one in big-endian order; words two
and three are zero. Output word pairs `(0,1)` and `(2,3)` become big-endian
64-bit draws. Purpose labels are exactly:

| Purpose | Label |
|---|---|
| Event permutation | `event-order` |
| Linked node permutation | `node-order` |
| Physical event payload | `event-payload` |
| Initial consumer state | `initial-consumer-state` |

Descending Fisher-Yates uses rejection threshold `(-n) mod n` in unsigned
64-bit arithmetic before `draw mod n`. Physical event record `k` always has
index `k` and payload draw `k`; package, outcome, and logical sequence never
select or rewrite a payload.

Concrete master seeds and namespaces remain external freeze inputs. Stage 6
tests use only named synthetic fixture values.

## Event arena and identities

`EventArena` requires explicit nonzero power-of-two capacity, cache-line bytes,
base-page bytes, 256-bit seed, and namespace. No host query or fallback fills
one of those fields. It allocates one base-page-aligned, virtually contiguous
`C * B` byte region and writes every byte during preparation.

Each physical line has this exact Stage 6 layout:

| Offset | Size | Meaning |
|---:|---:|---|
| `0` | 8 | Immutable unsigned 64-bit record index |
| `8` | 8 | Immutable aligned unsigned 64-bit payload |
| `16` | `B-16` | Zeroed inert padding |

Only `const EventRecord*` access leaves the arena API after construction. The
record has no logical sequence, accepted ordinal, timestamp, ownership, or
mutable payload field. `RecordIndex`, `LogicalSequence`, and `AcceptedOrdinal`
are distinct C++ types. Logical sequence selects
`order[logical_sequence mod C]`; the resulting pointer is process-local only.
Validation rejects a pointer outside the arena, a pointer into the middle of a
line, or a record whose stored index disagrees with its physical line. No
pointer value enters an integrity byte stream or durable identity.

Allocation, first touch, HMAC, Philox draws, payload writes, permutation, and
whole-arena SHA-256 are preparation work. The prepared worker operations are
cyclic lookup, queue operation, pointer/index validation, two immutable 64-bit
loads, and the private mixer. A dedicated global-allocation hook executes
10,000 cycles through all five package types and observes no allocation after
preparation. Page residency and fault prevention still require the Phase 9
platform adapter; Stage 6 establishes only that every allocated byte is first
touched before worker use.

## Integrity byte grammars

Every SHA-256 field is encoded as an unsigned 64-bit big-endian byte length
followed by that field's bytes. Unsigned integers are eight big-endian bytes;
signed deltas are eight-byte two's-complement values. Each grammar begins with
its own length-delimited ASCII domain.

| Identity | Domain | Fields after domain |
|---|---|---|
| Record content | `cpu-prefetch/event-record-content-sha256/v1` | line bytes, capacity, then every physical record's index, payload, padding length, and exact padding bytes |
| Ordered index | `cpu-prefetch/ordered-index-sha256/v1` | count, then every index in the complete cyclic permutation |
| Address delta | `cpu-prefetch/address-delta-sha256/v1` | count, then every signed within-arena byte delta including final-to-first closure |

The pre-horizon content digest is retained at arena preparation. Recomputing
after a synthetic unchanged run matches; index, payload, padding, order, and
delta mutations change the appropriate digest. Node and event address deltas
are derived from indices and strides, so independently allocated bases produce
the same identity.

The consumer update is private, branch-free modulo-`2^64` arithmetic:

```text
x = state + 0x9e3779b97f4a7c15
x ^= record_index
x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9
x ^= payload
x = (x ^ (x >> 27)) * 0x94d049bb133111eb
state = x ^ (x >> 31)
```

## Node order and capacity construction

`NodeOrderPlan` requires a power-of-two logical `C`, explicit cache-line bytes,
an explicit node stride containing an integral number of those lines, compatible
base-page bytes, seed, and namespace. It builds one
complete `C+1` permutation, including the sentinel, and retains the complete
closure delta vector, ordered-index SHA-256, address-delta SHA-256, distinct
line/page counts, shortest possible cycle, adjacent-line count, and signed
modal-delta count. The linked queue consumes the plan directly and now requires
its node-arena alignment explicitly; tests prove the arena base is aligned and
the supplied cycle repeats exactly.

The address report preserves raw signed deltas. Qualifying a concrete seed,
physical page-frame order, and the protocol's one-percent pre-run gate remains a
treatment-blind matrix-freeze/platform activity; no development fixture is
declared eligible.

Capacity selection consumes explicit `B`, usable `K2(P)`, usable producer-home
`K_home(P)`, and actual common-event-plus-queue byte candidates. It applies the
three imported rules to both ring and linked footprints:

- largest `C` with `4B < F <= K2/2` for L2-resident;
- largest `C` with `2K2 < F <= K_home/2` for LLC-resident;
- smallest `C` with `F >= 2K_home` for beyond-LLC.

No matching candidate is an error. Stage 6 proves the arithmetic and boundary
selection but supplies no real cache fact or capacity.

## Exact package operations

The packages are five concrete, non-polymorphic types. A platform emitter is a
statically bound, non-owning seam; Stage 6's instrumented emitter records exact
targets but emits no CPU prefetch instruction.

| Package | Producer operation | Consumer operation | Distance state |
|---|---|---|---|
| `R0` | one ring `try_enqueue`; no hint | one ring `try_dequeue`; no hint | none |
| `R1` | request retaining write-intent for future slot, then one `try_enqueue` | request retaining read for same-distance future slot, then one `try_dequeue` | `d1=ceil(B/sizeof(pointer))` slots |
| `R2` | same exact producer site as R1 | same exact consumer site as R1 | externally calibrated whole-line `d2`, at least two lines and at most `C/4` slots |
| `L0` | one linked/recycler `try_enqueue`; no hint | one linked/recycler `try_dequeue`; no hint | none |
| `L1` | one linked/recycler `try_enqueue`; no producer hint | acquire successor; request one retaining-read hint for that successor header; then demand its event field and complete dequeue/recycler return | immediate successor only |

R1/R2 never target an event record. L1 never targets an event record or
recycler and has no numeric distance. R2 construction requires a nonempty
calibration evidence identity and rejects a one-line value, quarter-cap
violation, or cap collapse. No R2 default exists.

## Generated-code audit

The GCC release probe exposes the consumer action, R1/R2 producer and consumer
sites, and L1 consumer site. GNU Binutils 2.46 and LLVM 22.1.6 views contain no
call, `lock`, `xchg`, or `mfence` class in the six bodies. The consumer body has
exactly the two record loads, constants, shifts, XORs, and two multiplications,
with no record store. R1/R2 compute and expose the future slot target before the
queue's demanded current-slot access. L1 exposes the acquired successor target
before loading its event field. Both tools reject a deliberate call-injection
mutant. This is correctness evidence only; no instruction latency or throughput
was observed.

Platform prefetch encoding/form, clock reads, wait relaxation, termination,
timestamp boundaries, and the final combined worker body remain later
generated-code gates.

## Unresolved inputs and next gate

The following remain deliberately absent: eligible-stand line/page/cache facts,
producer-home NUMA evidence, actual capacities, qualifying event/node seeds,
physical page-frame order, platform retaining read/write instructions or named
read fallback, and calibrated per-context R2 distances. Those are external or
later calibration records, not Stage 6 defaults.

Stage 7 schedule implementation additionally requires D-027 to freeze the
exponential transform, input-bit mapping, integer time unit, rounding, and
overflow behavior. ADR-0025's general stream and derivation are ready for that
prospective decision, but Stage 6 does not generate a schedule.
