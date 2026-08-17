# ADR-0029: Stage 7 schedule-generation suite

- Status: `PROPOSED`
- Date: 2026-08-17
- Classification: Schedule generation / deterministic numeric mapping
- Decision owners: Repository owner; reproducibility owner; statistical owner; timing owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Before Stage 7 implementation; awaiting Q6

## Context and scientific constraints

The protocol fixes completion-independent exponential interarrivals, exact
rational rates, integer deadlines, half-open horizons, namespace separation,
matched schedule sharing, immutable order, and schedule identities. It leaves
the exact transform, random-bit mapping, time unit, rounding, deadline
encoding, and overflow rule open. ADR-0025 supplies deterministic 64-bit
Philox draws but intentionally does not map them to exponential intervals.

This proposal has no force until the repository owner accepts Q6. No Stage 7
implementation may rely on it while its status is `PROPOSED`.

## Options considered

1. C++ `std::exponential_distribution`.
2. Fixed mapping with the platform C/C++ logarithm.
3. A new independent fixed-point logarithm.
4. An MPFR/GMP offline generator.
5. A pinned Python 3.14 `decimal` offline generator with a completely specified
   context, operation order, mapping, encoding, failure rule, and goldens.

## Proposed decision

Select option 5 and the suite
`POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1`, exactly as specified in
[`docs/STAGE7_DECISION_BUNDLE.md`](../STAGE7_DECISION_BUNDLE.md).

The proposal adds purpose label `arrival-schedule`, consumes one 64-bit draw per
candidate, maps it by `u=(2r+1)/2^65`, evaluates `-ln(u)` under an explicit
80-digit round-to-nearest-even decimal context, scales by the exact reduced
rate, accumulates before rounding, and floors the cumulative offset to
picosecond ticks. Deadlines are absolute unsigned 64-bit values. Production
storage is headerless big-endian `SCHEDULE-ABS-U64BE-v1`; overflow and
publication fail closed under `SCHEDULE-U64-ABS-FAIL-CLOSED-v1`. Decoded and
envelope SHA-256 grammars are versioned in the bundle.

The imported envelope binds the suite as
`rng.algorithm=POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS` and
`rng.version=1`. Its derivation-record reference must bind the accepted base
stream, purpose, seed identity, and matching parent/child namespaces. This uses
the imported logical fields without adding or editing a protocol schema.

Schedule construction is a single-threaded offline tool. The C++ timed process
consumes only a fully decoded, semantically validated, immutable deadline array
and never invokes or links Python.

## Evidence

- Imported implementation specification Section 5.1, data dictionary Schedule
  contract, schedule schema, and protocol freeze checklist.
- ADR-0010, ADR-0015, ADR-0023, and ADR-0025.
- The C++ draft specifies distribution generation algorithms as
  implementation-defined.
- Python 3.14 documents `Decimal.ln()` as correctly rounded with
  `ROUND_HALF_EVEN`.
- Synthetic decision-preparation vectors agree between CPython 3.14.5 C
  `decimal` and pure-Python `_pydecimal` for the transform boundaries.

## Consequences and compatibility

Scientific effect: the proposal prospectively fixes a midpoint approximation
to a uniform draw, 80-digit decimal intermediate rounding, and cumulative
floor-to-picosecond quantization of the continuous arrival model. It uses no
performance observation.

Compatibility effect: every mapping, context, arithmetic order, unit,
encoding, hash grammar, and failure rule named above is part of the suite.
Unknown or mismatched suites fail closed. A compatible decoder needs only
unsigned integer and SHA-256/JCS support; generation additionally needs the
already-approved Python 3.14 standard library. No MPFR/GMP dependency is added.

## Verification and acceptance tests

Stage 7 must implement all direct/integrated goldens from the bundle, complete
artifact and canonical-envelope hashes, C/pure-Python decimal parity, both C++
decoder matrices, boundary/overflow/corruption tests, namespace and matched
sharing invariants, and a call-graph boundary proving generation is absent from
the timed process. These are correctness checks only.

## Rollback or supersession

Before acceptance, edit or reject this proposal without changing Stage 6. Once
accepted, any bit-, deadline-, or identity-changing revision needs a new suite
ID, superseding ADR, prospective artifact regeneration, and full Stage 7
requalification. Existing schedules remain immutable under their original
suite.

## Protocol-amendment assessment

No amendment is expected because the protocol explicitly delegates these
numeric and physical schedule decisions while fixing their logical contract.
If review shows that cumulative-floor picosecond representation conflicts with
a normative scientific requirement, stop and amend the protocol instead of
accepting this ADR.
