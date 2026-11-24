# Stage 7 Deterministic Schedule Generation

This document records the implemented correctness boundary for ADR-0029 under
current protocol `2.0.0-pre.2`. The frozen deterministic preimage retains its
ADR-0029 `2.0.0-pre.1` domain label. It describes an offline tool and a C++
decoder/validator. It does not authorize a pilot, execute a queue, read a
clock, or report performance.

## Exact contract

`tools/generate_schedule.py` accepts every scientific and lifecycle input
explicitly; it supplies no seed, namespace, rate, origin, or horizon default.
It requires Python 3.14.x and emits three new append-only paths:

1. a headerless `SCHEDULE-ABS-U64BE-v1` artifact containing one unsigned
   64-bit big-endian absolute deadline per row;
2. a schedule envelope conforming to the imported Draft 2020-12 schedule
   schema; and
3. an implementation-owned derivation record conforming to
   `config/schemas/schedule-derivation-v2.schema.json`.

The normalized schedule suite is
`POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1`. Candidate `i` consumes
exactly Philox draw `i` from the ADR-0025 stream with purpose
`arrival-schedule`. The tool maps `r` to `(2r+1)/2^65`, applies `-ln` in an
explicit 80-digit, round-half-even decimal context, scales by the caller's
positive reduced rational rate, accumulates before rounding, and floors the
cumulative offset to picosecond ticks. Tied deadlines remain separate and in
order. The first candidate at or beyond `origin_ticks + horizon_ticks` is
excluded, implementing `[origin, origin+horizon)`.

The envelope binds schedule kind, Poisson/exponential arrival family, seed and
parent/child namespace identities, RNG algorithm/version, picosecond unit,
absolute encoding, explicit origin/horizon, exact reduced rational rate,
offered count, fail-closed overflow-rule ID, immutable ordering, storage
identity, and three hashes. The derivation record additionally binds the base
RNG suite, purpose, derived-key identity, exact Python/decimal/libmpdec runtime,
canonicalization suite, and its own zero-self hash. Pointer values, queue
outcomes, clock readings, and filenames are not identities.

## Integrity and failure behavior

- `artifact_sha256` covers the exact external bytes.
- `decoded_deadlines_sha256` uses
  `DECODED-DEADLINES-U64BE-SHA256-v1` and binds the protocol/schedule suite,
  time unit, origin, horizon, exact rate, count, and every decoded deadline.
- `schedule_sha256` uses `SCHEDULE-JCS-I64-ZEROSELF-SHA256-v1` over the full
  imported logical envelope.
- `record_sha256` uses
  `SCHEDULE-DERIVATION-JCS-I64-ZEROSELF-SHA256-v1` over the derivation record.

Generation rejects invalid or non-reduced rates, zero horizons, unsigned
overflow, exhausted draw ordinals, trapped/non-progressing decimal arithmetic,
byte/count overflow, unsupported Stage A kinds, unsupported runtime, and any
publication failure. Files are staged, flushed, and installed with no-replace
hard links. The derivation record and artifact are linked before the schedule
envelope, which is the commit record; a crash before the final link cannot
leave a valid envelope that references missing inputs. If an ordinary
three-file publication failure occurs, newly linked paths are rolled back; an
existing artifact is never overwritten. A temporary or unreferenced file is
not a protocol artifact.

`cpu_prefetch::schedule::decode_and_validate` consumes the imported logical
record, exact artifact bytes (or the protocol's `INLINE_TEST_ONLY` fixture
form), and the referenced derivation record. It fails closed on unknown suite,
unit, encoding, overflow profile, runtime binding, derivation mismatch,
malformed byte count, count mismatch, decreasing or out-of-horizon deadlines,
or any hash mismatch. Successful decoding returns an immutable
`PreparedSchedule`; generation, parsing, hashing, allocation, and publication
remain outside any future timed worker loop.

## Namespace and common-schedule rules

The implementation represents warm-up, calibration, pilot, H3 training, H3
validation, H1/H2 supplemental, and diagnostic roles explicitly. It never
infers a role from an identifier or filesystem path. Distinct roles cannot
reuse a child namespace. The three confirmatory role subspaces must share the
declared common Stage A parent while retaining distinct child namespaces.
Every treatment use carries an explicit common-schedule-family identity;
members of one family must bind the same logical schedule, hashes, seed,
namespace, rate, origin, horizon, and suite. Concrete namespaces and master
seeds remain later immutable lifecycle inputs.

## Synthetic golden evidence

The accepted synthetic seed and namespace produce Philox key words
`3f0bb803,84b3f51c`, first draws
`97a43571a6326b9a,56c3c6fdd95d24b5,6c6f5fb1b58c9a53,e5323de41d1a3f26`,
104 deadlines in `[0,10000)`, artifact SHA-256
`18f1da603f3d4383bb08410ffb0e41a8c4df336871765e633b4f116f1b22e81c`,
decoded SHA-256
`a07a349e5e95ff170036ffb21361d4d85dc9073177de7687c263ff254517a441`,
and `2.0.0-pre.2` envelope SHA-256
`df42859564d5075cca591b663e9db8a34da1e8a6ee4d81983d797db2bc6944f9`.
CPython C `decimal`, `_pydecimal`, and the C++ decoder agree. These are
software-correctness fixtures, not experiment inputs or empirical evidence.

## Local verification

With the accepted offline dependency prefix and `PYTHONPATH` configured:

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc
cmake --build --preset dev-gcc --target schedule-check
ctest --preset dev-gcc -L schedule
```

The same schedule-labeled tests run under both compiler/library development,
ASan/UBSan, TSan, and release presets. Any suite-defining change requires a
new version, a superseding ADR, prospectively regenerated artifacts, and full
requalification; existing artifacts are never reinterpreted.
