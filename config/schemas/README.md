# Implementation-owned schemas

These schemas supplement but never modify or replace the immutable logical
contracts under `protocol/2.0.0-pre.1/handoff/schemas/`.

`schedule-derivation-v1.schema.json` validates the ADR-0029 record referenced
by the imported schedule envelope's `rng.derivation_record_id`. It binds the
accepted base RNG and schedule suites, seed identity, explicit parent/child
namespaces, `arrival-schedule` purpose, derived Philox key identity, exact
Python/decimal runtime, canonicalization profile, and a zero-self canonical
SHA-256. The imported schedule remains the normative logical schedule record.
