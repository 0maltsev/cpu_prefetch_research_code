# Implementation-owned schemas

These schemas supplement but never modify or replace the immutable logical
contracts under the current `protocol/2.0.0-pre.2/handoff/schemas/` (with the
immutable pre.1 predecessor retained separately).

`schedule-derivation-v1.schema.json` validates the ADR-0029 record referenced
by the imported schedule envelope's `rng.derivation_record_id`. It binds the
accepted base RNG and schedule suites, seed identity, explicit parent/child
namespaces, `arrival-schedule` purpose, derived Philox key identity, exact
Python/decimal runtime, canonicalization profile, and a zero-self canonical
SHA-256. The imported schedule remains the normative logical schedule record.

`phase-integrity-report-v1.schema.json` gives the protocol-required referenced
phase/integrity artifact a concrete implementation-owned document shape. Its
five checksum-evidence objects project unchanged into the imported run
manifest's `integrity_evidence`; the schema does not extend that manifest.

`copy-ledger-record-v1.schema.json` records ADR-0033's append-only durability
evidence outside the imported raw-observation envelope. It fixes the v1
no-compression, one-temporary/two-durable-copy policy and supports explicit
incomplete records. Distinct domain IDs, exact expected/observed identity, and
sealed-state implications are also checked by the C++ semantic builder because
JSON Schema cannot express all of those relationships.

`join-audit-v1.schema.json` fixes the implementation-owned Stage 12 audit
envelope. A passed audit has no issues and must reference the joined artifact;
a failed audit has at least one stable failure issue and must not reference a
joined artifact. The C++ cross-record validator checks its exact sources,
counts, status, identity, and zero-self canonical SHA-256 against the imported
run manifest and raw streams.
