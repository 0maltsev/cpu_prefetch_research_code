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

The five Stage 13 schemas implement ADR-0038/0039 without changing an imported
contract:

- `calibration-plan-v1.schema.json` records a prospectively enumerated plan and
  distinguishes provided from unresolved external inputs;
- `service-rate-result-v1.schema.json` records all 60 service cells, every
  present run's status/raw/integrity/failure sources, exact throughput,
  valid-count decisions, rational minima, and candidate loads;
- `ring-distance-result-v1.schema.json` records all six contexts, per-run
  H-state validity/source/tail decisions, conservative demand/issue quantities,
  common producer/consumer distance, and ineligibility;
- `zero-loss-feasibility-result-v1.schema.json` records all 180 evaluated cells
  (or an honest blocked partial set), every probe decision, planned simultaneous
  exposure, the accepted estimator/profile/confidence/threshold/candidate
  binding, and matrix lower bound; and
- `calibration-freeze-v1.schema.json` records proposed/frozen/unresolved/
  invalidated states, source graph, material fingerprint, and supersession.

They use exact decimal strings for unsigned values that may exceed the
`JCS-I64-v1` numeric domain. C++ and Python semantic evaluators enforce cell
products, prospective run identity, exact methods, source hashes, arithmetic,
and append-only behavior which Draft 2020-12 alone cannot express. Synthetic
schema fixtures are not platform calibration evidence.

`runner-admission-v1.schema.json` is the implementation-owned Q13 admission
shape. It fixes the accepted pair/profile/relax identities, exact five-package
domain, nonzero limit fields, and immutable/eligible hash references. The C++
validator additionally proves exact evidence-kind coverage and uniqueness,
current trust-anchor binding, regular non-symlink files, and actual SHA-256
agreement before it can construct an admission ticket. It is not an imported
scientific schema and cannot authorize execution by itself.
