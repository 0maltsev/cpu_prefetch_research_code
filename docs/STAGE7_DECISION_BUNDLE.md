# Stage 7 Schedule-Generation Decision Bundle

Protocol version: **`2.0.0-pre.1`**

Decision ID: **D-027**  
Approval question: **Q6**  
State: **`ACCEPTED_BY_Q6`**

The repository owner accepted this bundle exactly as written by answering
`Q6 - accept the bundle` on 2026-08-17. ADR-0029 is `ACCEPTED`; Stage 7
has implemented and verified this decision. No experiment execution or
scientific result is authorized by the decision or implementation.

## Decision record

| Field | Accepted value |
|---|---|
| ID | D-027 |
| Classification | Scientific/reproducibility mapping with engineering implementation consequences |
| Owners | Repository owner; reproducibility owner; statistical owner; timing owner |
| Deadline / gate | Accepted before Stage 7 schedule-generation implementation |
| Selected suite ID | `POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1` |
| Supersession | New suite/version prospectively; existing schedules remain tied to their recorded suite and are never reinterpreted |

## Normative constraints preserved

The imported protocol requires pre-generated, completion-independent
exponential interarrivals; exact rational offered rates; integer deadlines;
nondecreasing order; a half-open `[origin, origin+horizon)` boundary; explicit
namespace, RNG, time-unit, encoding, count, overflow, storage, and checksum
identity; and matched-treatment schedule sharing. It deliberately does not
select the transform, bit mapping, integer unit, rounding, or overflow rule.

The decision does not select any master seed, concrete namespace, rate,
horizon, platform, clock, experiment outcome, or performance parameter.

## Options considered

| Option | Merits | Material problem | Recommendation |
|---|---|---|---|
| C++ `std::exponential_distribution` | Small implementation | The C++ distribution algorithm is implementation-defined, so the accepted standard-library matrices need not emit identical schedules | Reject |
| Fixed bit mapping plus `std::log`/`std::log1p` | Easy to review mathematically | The library result and intermediate binary rounding are not a frozen cross-tool byte contract | Reject |
| Independently implemented integer/fixed-point logarithm | No external numerical runtime | Large new numerical proof and maintenance surface for no scientific benefit | Reject for v1 |
| MPFR 4.2.2/GMP 6.3.0 offline generator | Correctly rounded, portable semantics | Adds two C-library dependencies and LGPLv3-or-later compliance/distribution work when the accepted Python standard library already provides the needed offline operation | Valid fallback, not recommended |
| Pinned Python 3.14 `decimal` offline generator | Already approved/provisioned; `Decimal.ln()` is correctly rounded; fixed context and goldens define stable bytes; no timed-process dependency | Generation is a separate tool and must be version/golden checked | **Recommend** |

Authoritative evidence is the [C++ draft distribution
clause](https://eel.is/c++draft/rand.dist), which makes distribution algorithms
implementation-defined; the [Python 3.14 `decimal`
contract](https://docs.python.org/3.14/library/decimal.html), which specifies
correctly rounded natural logarithms; and the imported protocol's exact
schedule fields. [MPFR](https://www.mpfr.org/mpfr-current/) was evaluated as a
fallback because it also specifies correctly rounded, architecture-independent
operations; it is not needed by the selected option.

## Accepted exact algorithm

### Stream and bit consumption

- Reuse `PHILOX4X32-10-HMAC-SHA256-v1` from ADR-0025 without changing its
  key/counter/word mapping.
- Add the exact purpose label `arrival-schedule`. Schedule-kind and role
  separation remains in the supplied namespace; concrete namespace values are
  not selected here.
- Candidate interarrival `i` consumes exactly `draw(i)`, starting at zero.
  There is one draw per candidate and no rejection, spare-bit cache, or hidden
  draw.
- Map unsigned draw `r_i` to the open-unit-interval midpoint
  `u_i = (2*r_i + 1) / 2^65`. Both endpoints are excluded, so every inverse is
  finite and strictly positive.

### Arithmetic context and inverse transform

Generation is a standalone, single-threaded Python 3.14 tool. It constructs an
explicit `decimal.Context` with:

- precision `80` decimal digits;
- `ROUND_HALF_EVEN`;
- `Emin=-999999`, `Emax=999999`, `capitals=1`, and `clamp=0`;
- traps for invalid operation, division by zero, overflow, underflow,
  subnormal, and accidental binary-float mixing;
- no process-global or inherited context.

For a reduced positive exact rate
`numerator_events / denominator_ticks`, candidate `i` is evaluated in this
operation order:

```text
u_i       = Decimal(2*r_i + 1) / Decimal(2^65)
z_i       = -ln(u_i)
delta_i   = (z_i * Decimal(denominator_ticks)) / Decimal(numerator_events)
sum_i     = sum_(i-1) + delta_i, with sum_-1 = 0
offset_i  = floor(sum_i)
deadline_i = checked_add(origin_ticks, offset_i)
```

Every arithmetic result uses the stated context. `ln` is rounded to nearest,
ties-to-even as specified by `Decimal.ln`; unary negation is exact. Inputs are
created only from integers. `numerator_events` and `denominator_ticks` must be
positive unsigned 64-bit integers and already reduced by their greatest common
divisor; noncanonical equivalent rates are rejected rather than silently
normalized.

The first candidate with `deadline_i >= origin_ticks + horizon_ticks` is not
stored and terminates generation. Earlier deadlines are retained exactly,
including ties. No tie is deduplicated, delayed, jittered, or reordered.
Rounding the cumulative absolute time down, rather than rounding each interval,
avoids per-interval ceiling accumulation and keeps every retained deadline in
the declared half-open horizon. Its prospective scientific effect is a fixed
floor quantization of less than one schedule tick toward the interval start of
the suite-defined decimal cumulative value. The separately specified 80-digit
rounding defines that cumulative value; it is not represented as exact-real
arithmetic.

### Time unit, origin, and deadline representation

- `time_unit` is exactly `ps` (one picosecond). This is a representation unit,
  not a claim of clock accuracy. Stage 8 must still qualify the clock and its
  conversion.
- `origin_ticks` remains an explicit unsigned 64-bit input; no implicit zero is
  inserted.
- `horizon_ticks` is a positive unsigned 64-bit input.
- `deadline_encoding` is exactly `ABSOLUTE_INTEGER_TICKS`.
- Production deadline bytes use format ID `SCHEDULE-ABS-U64BE-v1`: one
  unsigned 64-bit big-endian absolute deadline per row, with no header,
  padding, or trailing bytes. The envelope supplies all metadata.
- `byte_count` must equal `8 * offered_count`. `INLINE_TEST_ONLY` remains
  fixtures-only.

Picoseconds make the cumulative-floor error less than one picosecond while a
64-bit relative horizon still spans more than 200 days. Later platform clock
qualification may reject a stand or conversion; it may not silently change
the schedule unit or deadlines.

### Imported-envelope binding

The imported schema deliberately has no additional `schedule_suite` property.
The suite is therefore bound without extending or editing that schema:

| Imported field | Proposed rule |
|---|---|
| `arrival_family` | Exactly `POISSON_EXPONENTIAL` |
| `rng.algorithm` | Exactly `POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS` |
| `rng.version` | Exactly `1`; the normalized suite ID is `rng.algorithm + "-v" + rng.version` |
| `rng.seed_id` | Explicit caller-supplied immutable seed identity; never the seed bytes and never a default |
| `rng.derivation_record_id` | Explicit reference to an immutable record binding the seed identity, parent and child namespaces, `PHILOX4X32-10-HMAC-SHA256-v1`, purpose `arrival-schedule`, and the derived-key identity |
| `rng.parent_namespace_id` | Explicit caller-supplied parent; must match the derivation record |
| `namespace_id` | Explicit caller-supplied child; must match the derivation record |
| `inclusion_boundary` | `start_inclusive=true`, `end_exclusive=true` |
| `overflow_rule_record_id` | Exactly `SCHEDULE-U64-ABS-FAIL-CLOSED-v1` |
| `immutable_ordering` | Exactly `true` |

`schedule_kind`, seed identity, namespace identities, origin, horizon, and rate
remain external lifecycle inputs. The semantic validator must reject any
envelope/derivation mismatch. The suite binding also selects the physical,
decoded, and envelope-hash profiles below; they are not inferred from a file
name or URI.

### Overflow and failure rule

The referenced overflow-rule ID is
`SCHEDULE-U64-ABS-FAIL-CLOSED-v1`. Generation rejects, without publishing a
valid schedule envelope, when any of the following occurs:

- zero, non-reduced, or out-of-range rate fields;
- checked `origin_ticks + horizon_ticks` overflow;
- need for a candidate after unsigned draw ordinal `2^64-1`; that last ordinal
  is valid, and generation may terminate successfully if its deadline reaches
  the horizon, but it fails closed if another candidate would be required;
- nonfinite arithmetic, a trapped decimal signal, or failure of the internal
  cumulative value to increase;
- negative or greater-than-`uint64` offset/deadline;
- `offered_count` or `8 * offered_count` overflow;
- output truncation, trailing bytes, row-count disagreement, or publication
  failure.

A temporary partial file is not an artifact and cannot be referenced. A later
lifecycle layer records the actual failure; it never truncates the schedule,
changes rate/horizon/seed, switches transform, or resumes under the same
schedule identity.

### Integrity identities

The physical artifact SHA-256 covers the exact `SCHEDULE-ABS-U64BE-v1` bytes.
The decoded-deadline algorithm ID is
`DECODED-DEADLINES-U64BE-SHA256-v1`. Its SHA-256 preimage is a sequence of
fields, each encoded as an unsigned 64-bit big-endian byte length followed by
the exact field bytes:

1. ASCII domain `cpu-prefetch/decoded-deadlines-sha256/v1`;
2. UTF-8 protocol version;
3. UTF-8 schedule-suite ID;
4. UTF-8 time unit;
5. eight-byte big-endian origin;
6. eight-byte big-endian horizon;
7. eight-byte big-endian rate numerator;
8. eight-byte big-endian rate denominator;
9. eight-byte big-endian offered count;
10. each decoded absolute deadline as its own eight-byte big-endian field.

The schedule-envelope identity profile is
`SCHEDULE-JCS-I64-ZEROSELF-SHA256-v1`: serialize the complete schedule record
with `JCS-I64-v1` after replacing `/schedule_sha256` with 64 lowercase ASCII
zeroes, then SHA-256 those bytes. `schedule_id` must already be an opaque,
non-hash identity, avoiding recursion. This profile is selected by the exact
`rng.algorithm`/`rng.version` binding above. Unknown suite/profile IDs fail
closed.

## Accepted golden vectors

These values are synthetic correctness fixtures, not experiment seeds or
performance data.

### Direct transform boundary vector

With rate `1/100` events per picosecond, zero origin, and the raw draws below in
the stated order, cumulative-floor offsets must be:

| Raw draws | Expected offsets |
|---|---|
| `0`, `1`, `2^63-1`, `2^63`, `2^64-2`, `2^64-1` | `4505, 8901, 8970, 9039, 9039, 9039` |

This covers both midpoint endpoints, adjacent central values, and retained
ties without an infinite logarithm.

### Integrated stream vector

Inputs:

- master seed:
  `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f`;
- namespace: `stage7-schedule-test`;
- purpose: `arrival-schedule`;
- rate: `1/100` events per picosecond;
- origin: `0`; horizon: `10000`.

Expected derivation and output:

| Field | Expected value |
|---|---|
| Philox key words | `3f0bb803`, `84b3f51c` |
| First four draws | `97a43571a6326b9a`, `56c3c6fdd95d24b5`, `6c6f5fb1b58c9a53`, `e5323de41d1a3f26` |
| Offered count | `104` |
| First twelve deadlines | `52, 160, 246, 257, 296, 365, 413, 570, 688, 872, 963, 1059` |
| Last twelve deadlines | `8963, 9091, 9164, 9299, 9471, 9495, 9605, 9656, 9835, 9868, 9902, 9998` |
| Artifact SHA-256 | `18f1da603f3d4383bb08410ffb0e41a8c4df336871765e633b4f116f1b22e81c` |
| Decoded-deadline SHA-256 | `a07a349e5e95ff170036ffb21361d4d85dc9073177de7687c263ff254517a441` |

The complete 104-row output is bound by both hashes. During decision
preparation, CPython 3.14.5's C `decimal` and separately executed
standard-library reference `_pydecimal` implementations produced the same
direct-transform offsets and the same integrated output. `_pydecimal` is
verification-only, not a production dependency or generator entry point.
Stage 7 must add the complete fixture and independently verify the integrated
hashes before closure.

## Scientific and compatibility effects

Scientific effect: this prospectively fixes the discrete representation of the
otherwise protocol-required exponential arrival process. The declared
midpoint discretization, 80-digit intermediate rounding, and cumulative
floor-to-picosecond quantization are all part of that representation. It is
selected without queue or performance outcomes.

Compatibility effect: purpose label, 64-bit draw consumption, midpoint
mapping, decimal context, operation order, rate normalization, time unit,
flooring, absolute encoding, byte order, stopping rule, failure rule, and hash
grammars are all suite identity. Python and decimal exact versions are recorded
for generation, and any golden mismatch fails closed. The C++ prepared-run
consumer receives only validated immutable unsigned deadlines and does not link
or invoke Python.

No new third-party dependency is added: Python 3.14 and its standard library
are already in the accepted dependency baseline. MPFR/GMP remain unselected.

## Stage 7 verification closure

Stage 7 passes the required direct/integrated goldens under Python 3.14, C
`decimal` versus `_pydecimal` parity, GCC/libstdc++ and Clang/libc++ decoder
parity, external and inline-test decode paths, hash/corruption negatives,
nondecreasing/tie/count/half-open rules, rate/overflow failures,
completion-independence, namespace separation, exact matched-treatment
sharing, and every supported sanitizer matrix. The standalone generator and
`PreparedSchedule` boundary keep generation, parsing, hashing, publication,
and allocation outside the future timed worker path. Full evidence and the
exact contract are recorded in [`SCHEDULE_GENERATION.md`](SCHEDULE_GENERATION.md).

## Approval record

The repository owner answered **`Q6 - accept the bundle`** on 2026-08-17.
D-027 and ADR-0029 are therefore accepted and implemented exactly as recorded
here. Any later change to a suite-defining field requires
a superseding ADR, new suite/version, prospective artifact regeneration, and
full requalification; selecting the MPFR fallback would additionally require
approved dependency, license, and version records.
