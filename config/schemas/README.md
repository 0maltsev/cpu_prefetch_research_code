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

`runner-admission-v2.schema.json` is ADR-0044's incompatible phase-gated
successor. It preserves the selected pairs and relax mapping, adds a mandatory
`SOFTWARE_PREFETCH_MAPPING` distinct from H0/H1 control evidence, and replaces
the generic pilot authorization with an exact `PHASE_EXECUTION_AUTHORIZATION`.
The v1 schema remains unchanged and readable but cannot arm the v2 runner.

`runner-admission-v3.schema.json` is ADR-0048's incompatible correction. It
retains only the two pre-measurement start-barrier bounds and removes producer-
idle, consumer-empty, and drain poll caps that could expire on valid protocol
behavior. V1/v2 remain unchanged and cannot arm the v3 runner.

`qualification-evidence-v1.schema.json` includes the D-047
`SOFTWARE_PREFETCH_MAPPING` detail variant. It fixes
`X86-64-PREFETCHW-PREFETCHT0-v1`, the exact instruction roles, both owner-CPU
CPUID observations, and both compiler/disassembler results. Structural schema
validity does not imply eligibility; the typed builder requires every
capability and codegen gate to pass.

`stage17-authorization-v1.schema.json` is the implementation-owned Q14
envelope for future Q15 stand-qualification and Q16a--Q16d phase-scoped
authorizations. It does not instantiate or grant authority. Its semantic
check rejects omnibus phases, wildcard/latest/unresolved targets, overlapping
authority roles, non-forward validity intervals, same-domain custody, missing
predecessor evidence, run-count drift, confirmatory namespaces, and permission
bits that would enable a prohibited action.

`stage17-authorization-v2.schema.json` preserves that exact authority/custody
shape while binding the ADR-0048 v3 runner. It validates prospective authority
only and does not issue or execute it.

`hardware-prefetch-qualification-v1.schema.json` is ADR-0049's exact Intel
family-06 model-55H, MSR-0x1A4, CPUs-0/1/26 H0/H1 evidence envelope. Its
semantic validator proves complete-value mapping/readback/restoration, unknown-
bit preservation, unique CPU coverage, both probe gates, eligibility, and
quarantine. Synthetic fixtures perform no MSR access.

`q15-qualification-authorization-v1.schema.json` implements ADR-0051's split
authority boundary. It admits only a read-only `Q15_R_READ_ONLY` record or a
prestate-bound `Q15_W_APPLY_PROBE_RESTORE` record and binds the immutable
measurement candidate, separate qualification-tool bundle, four roles, exact
commands/targets/limits/custody, required predecessor evidence, inverse and
independent-readback relationships, prohibitions, and detached signature. Its
semantic checker rejects Q15-R mutation, incomplete CPU/prestate/order coverage,
self-readback, missing probe families, wildcard values, and role/domain overlap.

`q15-authorization-preparation-v1.schema.json` is deliberately not an authority
schema. It records the exact known candidate binding and unresolved Q15-R/Q15-W
inputs with `BLOCKED_INPUTS_REQUIRED`, null unsealed tool hashes, and every
authority flag false. Preparation records cannot validate under the authority
schema.

`q15-probe-collector-contract-v1.schema.json` fixes ADR-0052's no-execution
qualification contract: candidate scope, raw `L2_RQSTS.ALL_PF` programming,
working-set derivation, exact regular/dependent probe definitions and binary
classification, seven collector identities, append-only evidence policy, and
an explicitly false implementation/authority boundary. The semantic checker
also verifies local source hashes and rejects drift that structural JSON Schema
cannot express. Validation does not open a PMU/device or claim that an
executable or authorization exists.

`q15-probe-implementation-profile-v1.schema.json` fixes ADR-0053's companion
interpretation without rewriting D-052: the recorded 256-bit value is the
ADR-0025 master seed, its namespace/purpose and derived key are exact,
ADR-0026 supplies the shuffle, and complete-buffer pre/post SHA-256 plus exact
cycle closure stay outside the counted traversal. Every stand, PMU, privileged,
Q15-R/Q15-W, calibration, pilot, and confirmatory authority field is false.
