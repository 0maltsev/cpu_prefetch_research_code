# Implementation Handoff

This directory is the non-executable interface between the paper repository and a future experimental implementation repository. It fixes semantics, identifiers, data relationships, access control, schema shape, provenance expectations, and readiness without supplying benchmark or analysis code.

Protocol version: **`2.0.0-pre.1`**. Primary data and lifecycle instances are incompatible with `1.x`; see `AMENDMENTS.md`.

## Authority and reading order

1. Root `AGENTS.md` defines repository scope and amendment rules.
2. `EXPERIMENT_IMPLEMENTATION_SPEC.md` defines experimental behavior.
3. `PROTOCOL_FREEZE_CHECKLIST.md` identifies fixed and unresolved decisions.
4. `PROTOCOL_VERSION.md` and `AMENDMENTS.md` record version lineage, compatibility, reasons, and authoritative artifact hashes.
5. `IMPLEMENTATION_DECISIONS.md` classifies decisions by readiness boundary.
6. `DATA_DICTIONARY.md` defines stable identifiers, enums, units, and invariants.
7. `ACCESS_AND_SEALING_PROTOCOL.md` defines H3/H1-H2 data-access chronology.
8. `schemas/` defines non-executable JSON Schema contracts for implementation records.
9. `HANDOFF_READINESS_REPORT.md` states the evidence-backed readiness verdict.

If two normative artifacts conflict, implementation must stop at that ambiguity. A versioned amendment must resolve the conflict before affected code, pilot data, or confirmatory access proceeds. No implementation-specific convenience silently overrides the paper protocol.

## Artifact relationships

Run manifests, raw-observation envelopes, external raw streams, block plans, schedules, failure records, freeze records, selection records, access records, join audits, phase/integrity reports, and derived outputs are append-only. A derived artifact names all source artifact IDs and SHA-256 hashes. Corrections create new versioned records linked by `supersedes_id`; source raw observations are never overwritten.

Logical producer, consumer, and joined rows are normative. Their physical encoding is selected and frozen later. Production envelopes reference external immutable artifacts and record schema/format identity, encoding, units, endianness, compression, row/byte counts, ordering, and hashes; inline rows are fixtures/examples only. Lifecycle-aware manifests never fabricate artifacts for an early failure.

The schemas contain no platform defaults. Concrete CPU, clock, rate, capacity, duration, counter, seed, physical format, deterministic primitive, and budget values enter only through separately authorized implementation, pilot, or freeze records. Draft 2020-12 validation checks record shape; `DATA_DICTIONARY.md` and the normative specification separately enumerate arithmetic, factorial, chronological, referenced-hash, and namespace invariants that an implementation-side semantic validator must enforce.

## Boundary

This handoff permits a separate repository to implement the protocol. It does not authorize pilot or confirmatory execution. It contains no benchmark, plotting, analysis, build, hardware-control, or other executable code.
