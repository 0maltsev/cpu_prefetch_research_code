# ADR-0023: Stage 4 typed model and validation boundary

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Protocol model / validation / compatibility
- Decision owners: Validation owner; data-integrity owner; implementation maintainer
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 4

## Context and scientific constraints

The seven imported Draft 2020-12 schemas are normative logical contracts, but
they cannot express every arithmetic, factorial, chronology, artifact, and
cross-record invariant. ADR-0004, ADR-0006, and ADR-0015 require fail-closed
version handling, separate structural and semantic passes, exact 64-bit
integers, and deterministic `JCS-I64-v1` serialization. The dependency policy
forbids adding a convenience JSON library without approval.

## Options considered

1. Add a third-party C++ JSON/schema stack.
2. Keep all protocol values as untyped Python dictionaries.
3. Use the pinned Python Draft 2020-12 validator for the imported schemas and a
   small repository-owned C++20 parser/model for typed controller inputs and
   record-local semantic validation.

## Decision

Use option 3. The structural pass validates unmodified input against the
imported schemas with pinned jsonschema 4.26.x. The C++ layer rejects duplicate
object keys, invalid UTF-8, unknown fields/enums/versions, non-64-bit integers,
missing normative values, and invalid typed values with stable categories and
JSON paths. It maps all seven schema families to typed records and retains the
immutable parsed source document for lossless reserialization.

`ScientificConfiguration` has no assignment or mutation interface after load;
workers will receive a later prepared image, never a parser or mutable config.
`Stage4SemanticValidator` implements record-local invariants. A separate
`CrossRecordSemanticValidator` interface reserves artifact lookup, chronology,
and lineage checks for the stages that own immutable stores and reconciliation.
No implementation-owned compatibility schema is needed. The protocol does not
state precedence when several independent confirmation blockers coexist;
D-031 remains unresolved, so Stage 4 validates that a stated reason applies but
does not choose a reason priority.

Canonical metadata uses the accepted `JCS-I64-v1` profile. Shared C++ and Python
fixtures cover signed/unsigned 64-bit boundaries, values around `2^53`, RFC
8785 binary64 examples, escaping, and UTF-16 property ordering. No SHA/HMAC,
RNG, permutation, mixer, physical raw codec, queue, clock, or measurement
behavior is selected here.

## Evidence

- Imported data dictionary, implementation specification, lifecycle/access
  rules, and all seven schemas.
- ADR-0002, ADR-0004 through ADR-0006, ADR-0010, ADR-0015, ADR-0017, and
  ADR-0022.
- Stage 4 unit, property, schema-positive/schema-negative, round-trip, shared
  canonical-fixture, static-analysis, and sanitizer results.

## Consequences and compatibility

Scientific effect: none; the implementation enforces the imported meanings and
keeps validity, zero loss, effective tail, and estimability independent.
Compatibility effect: only `2.0.0-pre.1` is accepted. There is no implicit 1.x
migration, future-enum pass-through, platform-value default, or input repair.
Changing an accepted logical value requires a protocol amendment; adding
compatible implementation support requires a superseding compatibility ADR and
fixtures.

## Verification and acceptance tests

Every imported schema has valid fixtures and negative mutations. C++ tests
cover exact rates, lifecycle/artifact conditions, producer/consumer/joined
timestamps, interval equations, exact 180-cell coverage, replacements, H3
contexts, access records, stable errors, immutable configuration, round trips,
and canonical bytes. Both supported compiler/library matrices and applicable
ASan/UBSan presets must pass.

## Rollback or supersession

A different parser, validator, or model may supersede this ADR only with the
same imported-schema suite, semantic rule IDs, exact-value behavior, canonical
fixtures, and fail-closed compatibility. Removing a normative check or changing
logical meaning requires protocol review and normally an amendment.

## Protocol-amendment assessment

No amendment is required. The decision implements existing logical contracts
without changing scientific semantics.
