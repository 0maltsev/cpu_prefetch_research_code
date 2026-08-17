# Test Strategy

## Purpose

This is the verification plan for a future Stage A implementation. Stage 4 now
provides the typed protocol/configuration model and validation layer; no queue
or measurement production code exists. ADR-0009 through ADR-0011, ADR-0017,
ADR-0022, and ADR-0023 fix the framework/toolchain/sanitizer/model baseline and
documented commands. Tests establish software correctness, protocol
conformance, reproducibility, and access integrity. Synthetic and
development-machine tests do **not** establish queue performance, a prefetch
benefit, a platform population effect, or any empirical paper claim.

Every behavior change must add or update targeted tests and rerun the relevant sanitizer/static/generated-code gates. A failed required gate blocks pilot; rerunning until a favorable performance result is never a testing strategy.

## Verification layers

### Accepted execution matrix

| Evidence class | Accepted mechanism | Acceptance boundary |
|---|---|---|
| Unit | GoogleTest under CTest | All supported compiler/library debug and release matrices |
| Property | RapidCheck under CTest after a current-toolchain compatibility probe | Recorded generator version/seed; shrink result becomes regression fixture |
| Deterministic concurrency/refinement | Repository-owned executable history checker/model oracle | Both queue packages, boundary suspension, full/empty/wrap/recycler cases |
| Stress | Repository-owned fixed-seed and recorded-seed executables | Frozen durations/repetitions/machines before pilot; no retry-to-pass |
| Memory/UB | ASan plus UBSan | Zero findings in both supported toolchain matrices |
| Data race | TSan | Zero findings in each supported matrix where the toolchain/standard-library combination is demonstrated compatible |
| Generated code | GNU objdump and llvm-objdump plus machine rules and human review | Every release package specialization; negative mutants caught |
| Scientific harness timing | Repository-owned harness | Google Benchmark or another framework control loop is forbidden |

Framework changes require a superseding ADR and equivalent behavioral evidence.

### 1. Import and compatibility

- Recompute SHA-256 and size for every protocol snapshot artifact against `IMPORT_MANIFEST.json`.
- Compare the four current authoritative artifacts to hashes declared by `handoff/PROTOCOL_VERSION.md`.
- Reject changed imported bytes, undeclared files, current `1.x` identifiers, and unsupported compatibility claims.
- Verify that imported paper instructions remain evidence only and cannot override root `AGENTS.md`.

### 2. JSON Schema positive and negative tests

Use a real Draft 2020-12 validator selected and pinned in Phase 3. For each of the seven schemas:

- validate the schema against the Draft 2020-12 meta-schema;
- maintain at least one minimal valid instance where the contract permits it;
- maintain negative fixtures for required fields, enums, version constants, `additionalProperties`, and conditional branches;
- specifically cover original/replacement block conditions, accepted/FULL row conditions, lifecycle/join artifact conditions, all freeze record kinds, and exact H3 selection keys.

JSON parsing alone is not schema validation.

Stage 4 status: implemented by `tools/check_protocol_fixtures.py` with pinned
jsonschema 4.26.x and a Draft 2020-12 format checker. All seven imported schemas
are meta-validated and covered by 17 positive and 15 negative fixture cases,
including every freeze record kind, both block lineages, honest partial
failures, valid `FULL`/low-`N_eff`, accepted/`FULL` rows, exact H3 contexts,
unseal hashes, empty affected blocks, versions, enums, hashes, IDs, units, and
conditional combinations.

### 3. Semantic-validator tests

Schema-valid but semantically invalid fixtures must be rejected for:

- schedule decoded count, nondecreasing order, half-open horizon membership, row count, namespace separation, matched sharing, and completion independence;
- count identities and zero final occupancy;
- envelope/row `run_id` disagreement;
- timestamp order and every exact derived interval equation;
- exact 180-cell Cartesian coverage and cell ordinals;
- one `H0` and one `H1` whole plot;
- replacement identity, ordinal, role, seed subspace, authority, budget, and lineage;
- referenced artifact existence/hash, chronology, roles, namespace membership, authority segregation, and append-only ancestry;
- storage decode count and logical-row conformance.

Test each rule with one clear failing reason and an independently derived expected outcome.

Stage 4 status: record-local rules are implemented with stable category, path,
and rule IDs. Store-dependent reference/hash, cross-stream reconciliation,
append-only ancestry, authority segregation, and budget proofs remain assigned
to Phases 12/14 through the `CrossRecordSemanticValidator` interface; they are
not reported as passing. Simultaneous failed gates accept either applicable
singular blocker reason and reject `ESTIMABLE`; D-031 blocks Phase 12 from
freezing a precedence that the imported protocol does not state.

### 4. Unit tests

Planned pure or bounded units include identity construction, checked integer/tick arithmetic, exact rational rates, half-open horizon inclusion, cyclic index lookup, checksum primitives, interval equations, inverse-ECDF order statistics, count classification, status transitions, capacity inequalities, `d1`/`d2` formulas, and duration/storage formulas.

Boundary cases include zero offered rows where permitted, maximum representable tick/count, overflow rejection, `pN` at an integer boundary, repeated quantile values, `N_eff` exactly at each threshold, `d2` cap collapse, and replacement budget exhaustion.

### 5. Property tests

Generate deterministic cases for:

- schedule encode/decode round trips, monotonicity, horizon membership, and exact counts;
- permutation bijection and frozen rejection-stream behavior;
- queue FIFO order, no duplication/loss, wrap/reuse, and count identities;
- joined intervals and additive identity over valid ordered timestamps;
- every 180-cell factor combination exactly once;
- block order/seed namespace invariants;
- serialization/codec round trip and cross-implementation checksum equality.

All randomized tests record their generator version and seed. A failing seed becomes a permanent regression fixture.

### 6. Queue linearization and refinement tests

Both queues require histories checked against an abstract bounded FIFO with single producer/single consumer try semantics. Tests must expose invocation, protocol-defined linearization, and response points and cover empty, full, wrap, delayed workers, and repeated reuse.

The linked package additionally requires a written refinement argument and executable history checks for immediate full when the recycler is empty, exclusive node states, acyclic/reachable chain, no recycle while reachable, FIFO recycler transfer, and repeated `C+1` cycles. Suspension at relevant phases must not violate the stated wait-free/terminating try-operation boundary.

### 7. Concurrent stress tests

- Long fixed-seed producer/consumer sequences with independent delay injection.
- Repeated full/empty transitions and ring wrap.
- Linked FIFO/recycler cycling sufficient to exercise every node many times.
- Cross-check first, internal, and final sequences; counts; node ownership; record contents; and checksums.
- Stress both slow-producer and slow-consumer cases and abrupt controlled termination/failure recording.

Acceptance durations, repetition counts, machines, and seeds are frozen before pilot. A retry after a flaky failure does not convert it to a pass.

### 8. Sanitizers and language/runtime checks

- AddressSanitizer for out-of-bounds/use-after-free and buffer errors.
- UndefinedBehaviorSanitizer for arithmetic, alignment, and language undefined behavior.
- ThreadSanitizer where compatible with the selected atomics, compiler, and target; incompatibility must be documented and compensated with independent deterministic concurrency evidence rather than silently skipped.
- Compiler/static diagnostics appropriate to the selected language at an accepted strictness level.
- Runtime/compile-time proof that required atomics are lock-free on the eligible platform.

Acceptance is zero unresolved findings. A suppression is not a pass unless a named owner records the exact diagnostic, smallest scope, tool defect or deliberate mechanism, compensating evidence, and expiry/review gate. Unsupported TSan combinations are recorded as unavailable and require both supported-toolchain deterministic history/refinement evidence plus the approved compensating plan; they are never silently skipped.

Sanitizer builds verify correctness only and are never used for performance claims.

### 9. Deterministic schedule golden tests

Golden vectors bind RNG version, master/derived seed IDs, namespace, exact rational rate, encoding, integer time unit, origin, horizon, overflow behavior, decoded deadlines, and checksums. Cross-build and cross-platform generation must be bit-identical for supported targets. Warm-up, pilot, calibration, confirmatory roles, diagnostics, and optional stages must never collide.

### 10. Timing tests

- Tick reads never regress on either selected core.
- Cross-core offset, drift, resolution, conversion, serialization, and exact boundary-read overhead meet frozen limits.
- Compiler/generated-code inspection proves timestamp reads stay at defined boundaries without strengthening queue synchronization.
- Conversion and overhead-correction fixtures retain both corrected and uncorrected values and reject negative corrected intervals.
- Fault injection catches regression, excessive skew/drift, invalid conversion, and moved/missing boundaries.

### 11. Record, checksum, and corruption tests

- Assert one measured-line record size, payload alignment, immutable fields, and package-independent arena/order.
- Known-answer tests for consumer mixing, rolling checksum, content checksum, index checksum, delta checksum, canonical serialization, and artifact SHA-256.
- Flip, truncate, duplicate, reorder, or replace rows/bytes and require the correct schema, semantic, join, or integrity failure.
- Verify pre/post record-content equality and generated code containing expected loads/private update with no record write.

Stage 4 canonicalization status: shared C++/Python `JCS-I64-v1` fixtures cover
signed/unsigned limits, `2^53` boundaries, RFC 8785 binary64 examples, UTF-16
ordering, escaping, Unicode, and negative zero. RapidCheck exercises generated
`uint64_t` exact serialization. Mixing/rolling/data checksum algorithms remain
unresolved and no placeholder primitive is implemented.

### 12. Reconciliation fault injection

Start from independently built producer and consumer streams, then inject count mismatch, wrong `run_id`, wrong ordinal, unexpected pointer/index, duplicate, loss, reorder, invalid timestamp, broken equation, row/envelope disagreement, wrong source hash, and partial/truncated artifact. Every attempted join emits an audit. No failure may emit successful joined data or latency.

### 13. Lifecycle transition tests

Cover every lifecycle state and independent join status. Verify early failure without fabricated artifacts, partial measurement/drain artifacts, failed join with audit only, complete valid Stage A obligations, valid `FULL` plus zero-loss failure, valid low `N_eff` plus effective-tail failure, invalid run plus failure record, and block-incomplete consequences.

### 14. Manifest completeness tests

For each stage/run mode, verify identity, provenance, schedules, seeds, treatments, platform state, counts, integrity, artifact relationships, hashes, failure references, and status consistency. Remove each conditionally mandatory artifact in turn and require rejection. Verify corrections append new derived records and never overwrite raw streams.

### 15. Exact 180-cell factorial block validation

Construct the independent expected product of five packages, two requested hardware states, two placements, three residency classes, and three loads. Require exactly one of all 180 tuples, ordinals `0..179`, two distinct whole plots containing `H0`/`H1`, correct node-seed nullability/package rules, and role-compatible seed references. `uniqueItems` is not accepted as sufficient evidence.

### 16. Sealing and unsealing negative tests

- Validation data, summaries, logs, and treatment-dependent diagnostics are inaccessible in `PLANNED`, `COLLECTED_SEALED`, `TRAINING_OPEN`, and `SELECTION_FROZEN` as applicable.
- Selection contains exactly six stable keys, valid candidates, training inputs/hashes, rule version, authority, and checksum.
- Reject missing/wrong predecessor ID/hash, invalid state transition, wrong role, empty affected blocks, bad namespace, unauthorized actor, overwritten/branched lineage, early H1/H2 access, and leaked outcomes.
- H3 evaluation must reference the unseal record; H1/H2 release must reference sealed H3 evaluation/access evidence.

### 17. Complete-block replacement tests

Verify that `FULL`, low `N_eff`, and extreme valid latency never authorize replacement. For genuine invalidity, retain the original and require a new 180-cell block with new identity, ordinal, role-compatible seed subspace, randomization, same immutable role, authority, failure record, and available budget. Reject cell repair, seed/ID reuse, role change, absent lineage, and collection past `R_replacement_max`.

### 18. Generated-code acceptance

For each package/build, inspect and hash the generated boundaries for queue publication/observation, prefetch site/target/form/distance, wait relaxation, termination flag, immutable record loads, private checksum update, timestamp boundaries, static specialization, and absence of virtual dispatch, treatment branch, allocation, I/O, logging, or unexpected calls. Source, object, executable, compiler, flags, standard-library, linker, disassembler, rule-set, and report hashes travel together. The test must include negative fixtures or mutated builds proving the checks detect missing/moved operations.

### 19. Clean-environment build and verification

From a documented clean environment with network access disabled, recreate dependencies, build artifacts, fixtures, validator outputs, and generated-code reports solely from tracked inputs and recorded versions. Compare source/build/protocol/dependency hashes and licenses and run the complete non-performance test suite. Stage 3 provides the local/CI commands in `README.md`; later phases extend the same presets and checks rather than inventing separate entry points.

### 20. Synthetic end-to-end dry run

Use a small explicitly synthetic fixture namespace to exercise planning, schedules, lifecycle, private streams, sealing, join, manifests, failure injection, status gates, and derived provenance. It must not be called a pilot, use confirmatory namespaces, tune treatment parameters, or support a performance claim. Its acceptance is structural correctness only.

### 21. Dependency and provenance tests

- Fail configure/verification for an unrecorded dependency, missing immutable source hash, unknown license, network fetch, or incompatible license decision.
- Bind queue implementation files to the accepted provenance/mode record and paper-to-source semantic map.
- Verify that independent queue implementation imports no third-party queue source or mechanically derived code.
- Verify every generated source/table has a tracked generator, inputs, version, deterministic regeneration command, output hash, review classification, and stale-output check.

### 22. Plane and privilege isolation tests

- Prove the worker call graph cannot reach config/schema parsers, general allocators, filesystem/network/console APIs, compression, reconciliation, or analysis.
- Run negative mutants that add each prohibited call and require rejection.
- Verify the measurement process has no platform-control or validation-custody privilege.
- Exercise denied/partial platform operations, independent readback mismatch, rollback failure, inaccessible validation data, and crash/restart at every artifact handoff.
- Confirm requested-state fields never populate verified-state fields without independent evidence.

## Evidence order

Verification proceeds from import/dependency checks through schema/unit/property checks, queue/refinement/concurrency checks, sanitizers, platform/timing/generated-code gates, lifecycle/storage/reconciliation integration, clean-room build, and synthetic dry run. Pre-pilot acceptance requires all applicable layers to pass with immutable evidence, zero unresolved sanitizer/correctness findings, a qualified eligible platform, and no unapproved suppression or unavailable mandatory capability.

## Software evidence versus scientific evidence

Passing tests shows that the implementation conforms to the frozen contract under tested environments. Calibration and treatment-blind pilot evidence may freeze platform-dependent parameters after software acceptance. Only authorized, valid, complete confirmatory blocks analyzed under the sealed protocol can support empirical scientific claims.
