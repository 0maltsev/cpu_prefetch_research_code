# Stage A Implementation Plan

Protocol version: **`2.0.0-pre.2`** (with immutable predecessor
`2.0.0-pre.1`). Status values are `COMPLETE`, `BLOCKED`, `PENDING`, and
`PROHIBITED`. The phases are dependency ordered; a later phase may be explored
only where it cannot force an unresolved earlier choice. Stage B and Stage C
are deferred future work outside this plan and require separate
authorization/amendment.

## Phase 1 — Protocol import and traceability

- **Objective:** Freeze an exact authoritative snapshot and map normative requirements to future owners and gates.
- **Inputs and prerequisite decisions:** Paper repository at the supplied sibling path; actual version and declared hashes established from repository evidence.
- **Files/components:** immutable versioned `protocol/` snapshots and manifests, root governance/status/readme, all `docs/` planning records.
- **Tests:** Source/import size and SHA-256 equality; declared-hash verification; JSON/schema validation; link/version/scope/file audits.
- **Acceptance criteria:** Every required artifact is byte-identical and listed; all requested documents exist; all normative areas have owner/validator; no production code, result, or invented platform value exists.
- **Explicitly excluded:** Benchmark, queues, controls, runner, analysis pipeline, calibration, pilot, confirmation.
- **Rollback or failure behavior:** A declared-hash mismatch or normative contradiction stops bootstrap; do not repair imported bytes. Remove no source evidence; replace a bad import only from verified source and record a new timestamp/manifest.
- **Status:** `COMPLETE_REVERIFIED`; Q11 preserved the original 18-artifact
  pre.1 snapshot and added the authorized 18-artifact pre.2 snapshot. The
  pinned jsonschema 4.26.0 check verifies all 36 sizes/hashes, both exact
  inventories, eight authoritative hashes, and all 14 imported Draft 2020-12
  schemas.

## Phase 2 — Implementation-decision freeze

- **Objective:** Resolve the smallest engineering decisions needed to finalize production architecture without selecting pilot outputs.
- **Inputs and prerequisite decisions:** Phase 1; queue provenance/license investigation; candidate language/atomic feasibility; storage/validator/sealing/platform capability evidence.
- **Files/components:** ADR-0001 through ADR-0021 for accepted architecture, software, queue/process/atomic/integrity/correctness, platform/custody, and no-license boundaries; synchronized architecture, flow, status, risks, tests, traceability, and decision register.
- **Tests:** License/provenance review; architectural scenario tests for early failure, immutable raw correction, sealing, and unavailable platform control; atomic/sanitizer/tool support matrix.
- **Acceptance criteria:** Every pre-architecture row in `docs/IMPLEMENTATION_DECISIONS.md` has an accepted evidence-backed ADR; no scientific behavior changed; contradictions have amendments, not workarounds.
- **Explicitly excluded:** Production source, concrete physical raw encoding, platform numerical values, pilot/confirmatory decisions.
- **Rollback or failure behavior:** Reject or supersede an unsupported ADR before code depends on it. If no eligible artifact/platform architecture exists, record `BLOCKED_BEFORE_IMPLEMENTATION` and stop.
- **Status:** `COMPLETE`. Q1-Q3 are recorded in ADR-0007 through ADR-0020. The owner's Q4 answer, no license grant, is recorded as D-028/ADR-0021; no `LICENSE` file or SPDX grant was added.

## Phase 3 — Build and CI foundation

- **Objective:** Create reproducible build, dependency, formatting/lint, test, sanitizer, schema, and clean-room entry points for the selected stack.
- **Inputs and prerequisite decisions:** Accepted Phase 2 language, build, dependencies, target support, and licensing ADRs.
- **Files/components:** Minimal build manifests, dependency records, CI workflows, test skeleton, command documentation; no benchmark behavior yet.
- **Tests:** Clean configure/build, empty/minimal test invocation, pinned Draft 2020-12 validator, lint/format, sanitizer capability probes, dependency/license scan, clean-environment reproduction.
- **Acceptance criteria:** Documented commands work from a clean environment; versions and hashes are captured; failures are nonzero and artifacts retained; no platform-specific constant is embedded.
- **Explicitly excluded:** Queue and measurement implementations, performance tests, pilot.
- **Rollback or failure behavior:** Keep previous accepted tool record; supersede build ADR/tool versions rather than silently drifting; block Phase 4 if clean reproduction fails.
- **Status:** `COMPLETE`. ADR-0022 and `config/dependencies.json` constrain the tool/dependency matrix. Clean GCC/libstdc++ and Clang/libc++ smoke builds/tests, both ASan/UBSan and TSan matrices, format/static checks, protocol/schema/document/dependency/CI checks, release-flag policy, metadata inspection, and package generation passed locally. LeakSanitizer is explicitly disabled under the managed ptrace boundary; external self-hosted CI execution and runner provisioning remain platform evidence, not a Phase 4 blocker. No benchmark behavior was added. The exact next safe phase is Phase 4.

## Phase 4 — Protocol/configuration model

- **Objective:** Implement versioned protocol record types, Draft schema validation, checked identities/arithmetic, and cross-record semantic validation framework.
- **Inputs and prerequisite decisions:** Phase 3; storage/identity architecture; canonical serialization policy; compatibility rule.
- **Files/components:** Protocol/config model, schema loader, semantic-validator rule registry, typed lifecycle/status/identity records, test fixtures.
- **Tests:** Positive/negative tests for all seven schemas; `1.x` rejection; arithmetic, referenced-hash, namespace, chronology, factorial, and lifecycle semantic fixtures.
- **Acceptance criteria:** Every imported schema has conformance coverage; semantic-invalid/schema-valid cases reject; validators never repair data; rule failures identify requirement IDs.
- **Explicitly excluded:** Queue operations, platform mutation, raw physical codec, experiment execution.
- **Rollback or failure behavior:** Preserve rejected fixtures and rule evidence; a schema/spec conflict stops implementation and requests amendment.
- **Status:** `COMPLETE`. ADR-0023 records the no-new-dependency typed-model
  boundary. All seven imported schemas have Draft 2020-12 positive/negative
  coverage; C++ types/loaders cover every stable Stage A record family;
  record-local semantic rules, immutable configuration, exact-rate handling,
  stable error paths/categories, `JCS-I64-v1` cross-language fixtures,
  round-trip tests, and sanitizer/static checks pass. Phase 12 now implements
  run-level cross-record checks; Phase 14 retains block/access chronology. Q10
  and Q11 imported D-031 as `2.0.0-pre.2` without changing the immutable
  predecessor.

## Phase 5 — Queue provenance and correctness

- **Objective:** Independently implement the exact ring and linked-plus-recycler packages behind the accepted non-distorting binding and prove their stated semantics.
- **Inputs and prerequisite decisions:** Phase 4; ADR-0013 independent provenance/mode; ADR-0021 no-license posture; exact atomic width/alignment/memory-order/layout decisions under ADR-0014.
- **Files/components:** Queue package sources, static adapters, provenance/refinement records, abstract FIFO/reference tests; no workload driver.
- **Tests:** FIFO/boundary/wrap/reuse; linearization/refinement histories; delayed-worker progress; node ownership/recycler stress; lock-free atomic evidence; ASan/UBSan/TSan where compatible; generated queue-boundary inspection.
- **Acceptance criteria:** Zero unresolved correctness/sanitizer findings; fixed-arena full refinement accepted; required atomics lock-free; no fallback allocation or silent source deviation.
- **Explicitly excluded:** Prefetch-effect measurement, arrivals, timing, pilot.
- **Rollback or failure behavior:** Retain failing artifact/test record; fix or supersede implementation under same proven semantics. A semantic change requires amendment.
- **Status:** `COMPLETE`. ADR-0024, two
  source-hashed independent provenance records, direct adapters, exact
  release/acquire mappings, fixed-arena refinement, lock-free/layout probes,
  FIFO/model/phase-suspension/property/stress tests, and the dual-toolchain
  sanitizer matrix pass. GNU Binutils 2.46 and LLVM 22.1.6 objdump pass four
  release operation bodies and both reject the call mutant; both views were
  reviewed and their hashes are bound into queue provenance. No queue
  performance was observed.

## Phase 6 — Record and working-set construction

- **Objective:** Build immutable one-line event records, persistent arenas, linked node cycle, footprint accounting, and address-pattern evidence.
- **Inputs and prerequisite decisions:** Phases 4–5; line-size/platform facts; RNG/permutation/mixing/checksum candidates for correctness fixtures.
- **Files/components:** Record/arena builders, footprint calculator, permutation/address report, content/index/delta checksum integration.
- **Tests:** Alignment/layout, immutability, persistent identity, exact cycle, bijection/golden order, distinct line/page, stride/modal/period thresholds, paired checksums, corruption/write detection, generated record-load/mix checks.
- **Acceptance criteria:** Both packages use identical event arena/order; linked gates are reproducible; no measured-path allocation/permutation; exact footprint method is documented.
- **Explicitly excluded:** Platform capacity selection from uncollected evidence, performance claims, Stage C mutable records.
- **Rollback or failure behavior:** Pre-freeze seed failure advances only under the frozen treatment-blind stream; post-freeze mismatch invalidates affected run. Never reseed from treatment outcome.
- **Status:** `COMPLETE`. Q5 and ADR-0025 through ADR-0028 freeze the
  deterministic suite, permutation/payload domains, mixer/integrity grammars,
  records, and package representation. The event arena, node-order plan,
  footprint selector, exact five static packages, no-allocation hook,
  known-answer/property/corruption tests, and dual-disassembler workload audit
  pass. Concrete seeds, cache/page facts, capacities, platform prefetch
  encoding, and calibrated `d2` remain later evidence and were not invented.

## Phase 7 — Schedule generation

- **Objective:** Generate reproducible open-loop schedules and namespace/seed records independently of completion.
- **Inputs and prerequisite decisions:** Phase 4; RNG/version/master derivation, permutation, time unit, deadline encoding, overflow behavior.
- **Files/components:** Namespace derivation, schedule generator/codec/envelope, exact rational-rate handling, immutable storage seam.
- **Tests:** Golden cross-build streams; decode round-trip; nondecreasing deadlines; exact count; half-open horizon; overflow rejection; completion independence; disjoint namespaces; matched-treatment sharing.
- **Acceptance criteria:** All semantic schedule rules pass; no implementation-defined RNG behavior; schedule generation is absent from timed path.
- **Explicitly excluded:** Concrete confirmatory rates/horizons/seeds and any tuning from outcomes.
- **Rollback or failure behavior:** Algorithm/version change creates new records and invalidates dependent schedules; never silently regenerate a frozen schedule.
- **Status:** `COMPLETE`. The offline Python 3.14 generator, external u64be
  artifact, imported-schema envelope, implementation-owned derivation record,
  C++ immutable decoder, namespace/common-family validator, append-only
  publication, exact goldens, corruption/boundary/overflow tests, and full
  compiler/sanitizer matrices pass. No queue outcome, clock, or performance
  observation enters the implementation.

## Phase 8 — Timing

- **Objective:** Implement exact producer/consumer timestamp boundaries and an accepted platform clock mapping without altering queue order.
- **Inputs and prerequisite decisions:** Phases 5 and 7; target clock, integer conversion, serialization, overhead policy, acceptance limits.
- **Files/components:** Tick reader/converter, boundary instrumentation, clock acceptance/calibration records, generated-code checks.
- **Tests:** Monotonicity, skew/drift/resolution/read cost, conversion goldens, boundary ordering, regression/negative correction faults, disassembly for compiler motion and synchronization effects.
- **Acceptance criteria:** Every fixed logical boundary is representable exactly; clock passes on explicitly selected cores; raw values are retained without overhead correction; queue order is unchanged.
- **Explicitly excluded:** Performance comparison and pilot until the full measurement system passes.
- **Rollback or failure behavior:** Clock failure makes platform/build ineligible or run invalid as appropriate; no substitute source without new ADR/evidence.
- **Status:** `COMPLETE_SOFTWARE`; Q7 accepted D-009 and ADR-0030. The
  `cpu_prefetch_timing` library now implements checked raw-nanosecond and exact
  relative-picosecond reads, every fixed producer/consumer boundary, offline
  exact interval equations, fail-closed static/per-core/bidirectional
  qualification evaluators, uncorrected overhead diagnostics, and dual-tool
  generated-code rules/mutants for all five packages. Fake-clock, real-clock
  engineering-smoke, cross-thread, failure, overflow, equation, sanitizer, and
  release assembly checks pass locally. No worker CPU pair is inferred; the
  exact 10-million-read, traced vDSO, three-window bidirectional selected-pair,
  affinity/source, and before-block evidence remains an open Stage 9
  operational/Phase 16 platform gate. Stage 9 software preserves that blocker,
  and Stage 10 subsequently completed without using it as experimental
  evidence. Measurement remains prohibited.

## Phase 9 — Platform control

- **Objective:** Implement least-privilege affinity, actual-CPU, NUMA/first-touch/residency, requested/verified HW-PF, relax, environment, and topology evidence.
- **Inputs and prerequisite decisions:** Target OS/architecture/platform inventory; named privilege authority; documented APIs/manuals; clock from Phase 8.
- **Files/components:** Platform inventory provider, control/readback/probe interfaces, placement verifier, environmental recorder, failure-safe restoration path.
- **Tests:** Capability and permission negatives; near/far topology; before/during/after residency; migration faults; readback/probe mismatch; relax generated code; restoration after failure.
- **Acceptance criteria:** Required controls are both requested and independently verified; no generic “disabled/local” claim; loss of verification stops the run; privileges are scoped/audited.
- **Explicitly excluded:** Invented commands/values and confirmatory state changes before authorization.
- **Rollback or failure behavior:** Restore authorized default safely, retain audit/failure evidence, and mark platform ineligible if mandatory control cannot be proved.
- **Status:** `COMPLETE_SOFTWARE_PLATFORM_GATE_OPEN`. `cpu_prefetch_platform`
  implements read-only Linux CPU/core/package/NUMA/cache/PCI/environment
  inventory, capability states, exact Stage A near/far and producer-home/
  worker-local/base-page validation, dry-run, injected external actuation,
  independently identified fresh readback, reverse restoration, canonical rich
  evidence, and exact imported-platform-schema emission. Topology, sibling,
  NUMA/policy, unsupported/authority, partial apply, disagreement, stale state,
  restoration, manifest, safe-host, sanitizer, format, static, schema/import,
  and package checks pass locally. No host state was changed. The exact stand
  actuator/authority/whitelist, selected pair and thread/address readback,
  before/during/after residency, vendor HW-prefetch mapping and probes,
  successful restoration exercise, full clock qualification, and processor
  relax/prefetch instruction mappings remain mandatory before measurement and
  by Phase 16. Phase 10 used only fake/dry-run platform inputs and passed its
  software gate; measurement remains prohibited.

## Phase 10 — Run state machine

- **Objective:** Integrate specialized workers with lifecycle, warm-up/drain/reset/barriers, one-attempt workload, polling, termination, and honest partial-failure recording.
- **Inputs and prerequisite decisions:** Phases 5–9; process/thread model; warm-up/recovery records may remain symbolic for synthetic fixtures.
- **Files/components:** Controller, prepared run image, worker specializations, phase state machine, failure recorder, counts/integrity hooks.
- **Tests:** Every lifecycle transition; delayed/suspended workers; exact reset origin; no remap/retouch; no sleep/yield/backoff; release/acquire termination; backlog order; one attempt; early/partial failure without fabricated artifacts.
- **Acceptance criteria:** Hot path obeys allowlist; lifecycle evidence is complete; warm-up cannot leak; drain/count rules hold; generated code has no dynamic treatment dispatch.
- **Explicitly excluded:** Real pilot/confirmation and offline analysis.
- **Rollback or failure behavior:** Seal actual partial artifacts and failure; never resume the same run identity or synthesize missing output.
- **Status:** `COMPLETE_LOCAL`; `cpu_prefetch_lifecycle` implements the exact
  imported-enum projection, append-only transition metadata/consequences,
  deterministic preparation/warm-up/reset evidence, one-origin start barrier,
  one-attempt producer, polling consumer, dedicated u32 release/acquire
  termination, drain/watchdog/failure, no-retry outcomes, and recovery records.
  Twenty-four focused tests plus full regression/static/sanitizer checks pass.
  Fake queue/clock/platform evidence is software-only. Stage 11 now supplies
  the preallocated observation sinks; concrete reset/package bindings, platform relax,
  watchdog values, stand probes, and measured-release codegen remain later
  pre-pilot gates and do not authorize a run.

## Phase 11 — Raw storage and integrity

- **Objective:** Implement the frozen physical format, preallocated private buffers, immutable artifacts/envelopes, checksums, compression/copy policy, and capacity proof.
- **Inputs and prerequisite decisions:** Phase 10; physical format/row sizes/alignment/endianness/time unit; checksum/serialization/compression/copy decisions; horizon bounds.
- **Files/components:** Producer/consumer codecs and buffers, external artifact store, integrity reports, sealing and decode interfaces.
- **Tests:** Codec round-trip/cross-decoder; exact row count; `run_id`; overflow; no hot I/O/allocation; corruption/truncation/reorder; known checksums; pre/post content; capacity/disk exhaustion; immutable correction behavior.
- **Acceptance criteria:** Longest planned horizon fits without overflow/I/O; decoded rows conform logically; raw sources cannot be overwritten; compression is lossless/post-run only.
- **Explicitly excluded:** Quantiles/models and pilot until integration acceptance.
- **Rollback or failure behavior:** Any overflow/corruption is a measurement failure; append corrected derived/envelope records, never mutate raw bytes.
- **Status:** `COMPLETE_LOCAL`; Q9/ADR-0032/0033 freeze the exact contract.
  `cpu_prefetch_storage` implements independently owned preallocated streams,
  the literal-run-ID fixed codec/decoder, capture binding, integrity and
  imported-envelope documents, checked plan/run budgets, append-only two-copy
  publication, copy ledgers, recovery-only crash reopening, and honest partial
  finalization. Golden C++/Python, corruption, boundary/overflow, no-allocation,
  concurrency, crash/recovery, large synthetic, sanitizer, static, and
  dual-disassembler checks pass. The joined codec is compatibility-only; Stage
  11 does not reconcile. Exact operational run-plan capacity, page residency,
  real distinct failure domains/custody, and recovery exercise remain Phase 16
  evidence and measurement remains prohibited.

## Phase 12 — Reconciliation and validity gates

- **Objective:** Join private streams, derive exact intervals, classify statuses independently, and enforce manifest completeness.
- **Inputs and prerequisite decisions:** Phases 4, 10, 11; frozen logical contracts and integrity algorithms; D-031 simultaneous-blocker representation/precedence.
- **Files/components:** Join audit, accepted-sequence reconciler, joined-derived codec, status/gate evaluator, complete manifest assembler.
- **Tests:** Count/pointer/index/identity/ordinal/loss/duplicate/reorder/timestamp/equation fault injection; failed-audit no-join; valid `FULL`; valid low `N_eff`; missing-artifact negatives.
- **Acceptance criteria:** Latency exists only after passed audit; all equations exact; validity/zero-loss/effective-tail/block statuses remain independent; complete valid Stage A obligations enforced.
- **Explicitly excluded:** Replacement decisions based on FULL/low count and scientific effect analysis.
- **Rollback or failure behavior:** Seal failed audit and retain raw sources; invalid run makes original block incomplete; no in-place repair.
- **Status:** `COMPLETE_LOCAL`. Q10/Q11 authorize D-031 and immutable protocol
  `2.0.0-pre.2`; both snapshots pass inventory/hash/schema checks. ADR-0034
  records the compatibility boundary. `cpu_prefetch_reconciliation` implements
  exact accepted-sequence/k-th joins, conditional interval derivation,
  classified and independently regenerated audits, immutable source/hash/count/
  integrity/failure-evidence relationships, honest partial failures, and
  separate lifecycle/validity/join/count/zero-loss/tail/estimability states.
  Unit, fault-injection, generated property, round-trip/schema, and sanitizer
  checks use synthetic data only. Final estimability remains `NOT_EVALUATED`
  until Phase 14 injects authoritative block-completeness and access evidence.

## Phase 13 — Service-rate, zero-loss, and ring-distance calibration

- **Objective:** Implement treatment-blind calibration modes and records without selecting results in advance.
- **Inputs and prerequisite decisions:** Phases 5–12; approved calibration estimators, durations, repetition counts, matrix feasibility method/threshold/global rule, `d2` procedures, authority and stand budget.
- **Files/components:** Service-ready and open-loop probe modes, calibration planner/records, `mu_ref`/matrix-bound/`d2` calculation validators.
- **Tests:** Cell-configuration equality; continuous-ready-only difference; independent run-level LCB/minimum; all-exposure union bound; zero-observed-not-zero-bound; global action; `d2` rounding/minimum/cap/context properties.
- **Acceptance criteria:** Procedures are frozen before applicable results; outputs source-link valid evidence; no confirmatory outcome or cell-specific favorable adjustment enters decisions.
- **Explicitly excluded:** Pilot/confirmatory collection in this implementation phase and empirical recommendation.
- **Rollback or failure behavior:** Material build/platform/action/capacity change invalidates calibration freeze and requires new calibration; infeasible matrix stops confirmation.
- **Status:** `COMPLETE_LOCAL_SYNTHETIC`. Q12 accepted D-035 through D-038;
  ADR-0039 freezes the delegated Decimal/schema profile. The
  `cpu_prefetch_calibration` library implements the exact 60-cell service
  evaluator, prospective plan/no-top-up/context gates, owner/authority/budget
  evidence, exact rational minima, and per-run status/source decisions;
  preallocated ring acquire traces, advancing-only issue intervals, exact
  run-tail/H0/H1/worker merge, and distance cap/collapse handling. The offline
  Python layer implements the `180*5` run-cluster Hoeffding profile, prospective
  probe decisions, mandatory candidate/exposure/threshold/global-ladder
  validation, canonical hashing, append-only publication, and material
  invalidation. Five Draft 2020-12 schemas and C++/Python synthetic conformance
  tests pass. No platform
  calibration output was created. Exact stand, duration, prospective count,
  per-run sample minimum, seed, capacity, exposure, authority, and budget
  inputs remain unresolved; calibration execution remains unauthorized. The
  exact next safe software phase is Phase 14.

## Phase 14 — Stage A block planning and orchestration

- **Objective:** Build exact 180-cell plans, whole plots, role-specific namespaces, immutable roles, and complete-block replacement workflow.
- **Inputs and prerequisite decisions:** Phases 4, 7, 9–13; frozen `delta_star`, repetition counts, seeds, roles, recovery, budget, sealing, replacement cap/authority before final plans.
- **Files/components:** Factorial block generator/validator, role/access-aware scheduler, orchestration records, replacement authorization/stop workflow.
- **Tests:** Exact product/ordinals; H0/H1 whole plots; order/randomization goldens; role/seed compatibility; count formulas; original null fields; replacement lineage/new identity/full product; cap exhaustion; no cell repair.
- **Acceptance criteria:** Every final block is exact and immutable; all counts are evidence-derived; validation roles technically sealed; replacement workflow stops at budget.
- **Explicitly excluded:** Executing Stage A during planner implementation; Stage B/C blocks.
- **Rollback or failure behavior:** Discard only an unexecuted invalid plan by superseding it; executed/failed plans remain append-only. Any missing count/role/seed keeps confirmation blocked.
- **Status:** `COMPLETE_LOCAL_SYNTHETIC`. ADR-0040 records the
  implementation-owned compatibility profile. `cpu_prefetch_orchestration`
  generates and proves the exact 180-cell/two-whole-plot structure from
  explicit pre-derived keys and role seed catalogs; validates active-pool
  counts/namespaces/counterbalance; pins the separate 7/20/270/540/54
  precision registries and checked count equations; enforces exact
  access/sealing/amendment chronology, complete role block sets, a hashed
  precision-input/count binding at `TRAINING_OPEN`, and authority segregation;
  and permits only new complete role-preserving replacements from exact retained
  invalid-run/failure/authorization/budget evidence. Unit/property/schema and
  sanitizer tests use synthetic inputs only. Concrete counts, seed values,
  platform/build, authorities/custody, budget, and final plans remain later
  freeze inputs. No block was executed. The exact next safe software phase is
  Phase 15.

## Phase 15 — Offline analysis

- **Objective:** Implement source-linked run summaries, tail diagnostics, fixed model/contrasts, separate H1/H2 max-T, and sealed H3 selection/validation.
- **Inputs and prerequisite decisions:** Phases 4 and 12–14; `delta_star`, `B_boot`, seed, model matrix, effective-tail rules, access authorities; synthetic fixtures only until authorized data exist.
- **Files/components:** Quantile/effective-count summaries, design-matrix/contrast registry, block bootstrap, H3 access-aware workflows, derived provenance/manifests.
- **Tests:** Independent quantile goldens; drain/ties/no-pooling; effective thresholds; rank/alias; exact 7/20/270/540/54 registries; complete-block resampling; max-T goldens; selection ties; access negatives; missing/gate-blocked outcomes.
- **Acceptance criteria:** Outputs reproduce from named immutable inputs; no event pseudo-replication; no family mixing; access chronology enforced; blocked estimands reported, not imputed.
- **Explicitly excluded:** Empirical Results/Discussion/recommendation before valid authorized confirmation.
- **Rollback or failure behavior:** Append corrected derived artifact linked to unchanged raw sources; access leakage is a stop/audit condition, not a rerun opportunity.
- **Status:** `COMPLETE_LOCAL_SYNTHETIC`. ADR-0041 records the versioned
  platform-conditioned analysis profile. `cpu_prefetch_analysis` validates
  immutable version/hash/source evidence; verifies or performs exact Stage 12
  reconciliation; derives registered inverse-ECDF summaries and diagnostics;
  proves the full-rank 40-column balanced design; constructs only exact active
  complete blocks; implements separate seven/twenty two-sided complete-block
  max-T families; performs six-context training selection, immutable selection
  hashing, authorized unseal, and 54-comparison one-sided validation; and emits
  byte-stable canonical machine plus explicitly synthetic human reports.
  Known-answer/fault tests use only compact synthetic distributions. No
  empirical artifact, finding, recommendation, pilot value, or authority was
  created. The exact next safe stage is Phase 16 pre-pilot verification without
  measurement.

## Phase 16 — Pre-pilot verification

- **Objective:** Demonstrate integrated software correctness and reproducibility before any performance pilot.
- **Inputs and prerequisite decisions:** Phases 3–15 implemented to pilot-applicable scope; all pre-pilot decisions frozen; pilot plan/authority/budget.
- **Files/components:** Release candidate build, complete verification bundle, clean-room record, synthetic dry-run records, pre-pilot readiness report.
- **Tests:** Full `docs/TEST_STRATEGY.md`: schema/semantic, unit/property, queue/refinement/stress, sanitizers, generated code, timing/platform, storage/integrity, reconciliation/lifecycle, 180 cells, sealing/replacement, clean environment, synthetic end-to-end.
- **Acceptance criteria:** Every applicable check freshly passes; no unresolved correctness issue; clean build reproducible; storage/control/custody proven; synthetic results clearly non-empirical.
- **Explicitly excluded:** Pilot execution until a separate authorization decision after readiness review.
- **Rollback or failure behavior:** Classify and fix software/test/environment failures; supersede build and rerun affected then broad checks. Never waive a failed gate to collect data.
- **Status:** `COMPLETE_SOFTWARE_READY_FOR_STAND_PREFLIGHT`. ADR-0042 and the
  readiness report record fresh clean GCC/libstdc++ and Clang/libc++
  development/release matrices, all applicable ASan/UBSan and TSan matrices,
  protocol/schema/golden/provenance/static/generated-code and focused synthetic
  disposition evidence. A deterministic append-only stand-preflight bundle
  passes repeat-build identity, external/internal hashes, clean extraction, and
  nonprivileged smoke/preflight self-tests. Component timed bodies pass source
  and dual-disassembler audits. The production measurement executable and
  combined-worker audit, eligible-stand platform/control/clock/residency/storage
  evidence, and prospective calibration/pilot inputs remain explicit
  `BLOCKED_BEFORE_PILOT` gates; no platform value or scientific outcome was
  created. Clean revision `1b0a7f5` now has a byte-reproducible bundle with
  SHA-256 `e8eb9150d252d38f72b56884b0bcb5026480aee00b969c736fdc124783cb6eac`;
  its stand-side outer/internal/self-test gates and inventory pass. Detailed
  read-only topology proves `(0,1)` and `(0,26)` as static near/far candidates,
  while storage discovery finds only one mounted durable data namespace. The
  Q13/ADR-0043 now accepts the evidenced `(0,1)`/`(0,26)` pair, one `PAUSE`,
  and fail-closed static runner entry profile for implementation only. The
  strict admission/ticket/static-dispatch core, non-executing CLI, tests, and
  relax probe are added after the sealed Stage 16 bundle. Final affined
  production integration, dynamic qualification, second storage domain,
  named authority/custody, exact limits, and pilot plan remain unresolved;
  Phase 17 execution is prohibited.

## Phase 17 — Pilot execution

- **Objective:** Collect treatment-blind evidence needed to freeze platform-dependent capacities, calibration outputs, horizons, environment, precision, and feasibility.
- **Inputs and prerequisite decisions:** Phase 16 accepted; D-044 through D-046
  governance accepted; D-047 physical mapping implemented and strict combined
  audit passed; ADR-0104 finite operational graph; ADR-0105 append-only state
  journal; verified exact no-authority candidate bytes and custody receipt;
  accepted preflight and exact stand
  qualification; then dependency-ready phase inputs and a phase-scoped pilot
  authorization with exact namespaces, plans, durations/repetitions, controls,
  custody, storage, and stand budget. See
  [`STAGE17_OPERATIONAL_AUTHORIZATION.md`](docs/STAGE17_OPERATIONAL_AUTHORIZATION.md).
- **Files/components:** Immutable pilot/calibration run artifacts, failure records, blinded summaries, freeze-decision inputs; no confirmatory namespace.
- **Tests:** Per-run runbook gates, manifest completeness, join/integrity, blinded covariance/tail/recovery/environment procedures, no-access and namespace audits.
- **Acceptance criteria:** Evidence is complete and treatment-blind for each required freeze; no failed correctness gate; all confirmatory decisions can be justified or the study is declared infeasible/unresolved.
- **Explicitly excluded:** Confirmatory outcomes, result-bearing claims, treatment-driven tuning, pilot substitution for Stage A.
- **Rollback or failure behavior:** Preserve all pilot artifacts/failures. Material implementation/platform change invalidates dependent pilot evidence. Do not cherry-pick or repeat for favorable effects.
- **Status:** `PREPARED_EXTERNAL_INPUTS_REQUIRED`; Q14 accepts D-044 through D-046, D-047 closes the
  physical emitter and strict combined audit, and Q15-P0/ADR-0048 through
  ADR-0050 accept the repository-local prerequisite correction/mapping/policy.
  The v3 implementation passes the complete local compiler, sanitizer, schema,
  static-analysis, and generated-code matrix. Clean revision `693f00b` seals
  the no-authority candidate with outer SHA-256 `f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1`.
  The clean Q15-S3 component release is sealed and verified. Q15-R-P1 accepts
  D-057..D-060 for repository-local work only. ADR-0057..0060, the strict
  authorization-v2 contract, fixed 15-step controller core/no-authority CLI,
  fake failure/resource tests, dual-disassembler retry-mutant gate, and
  unapplied role/custody plan are implemented. They cannot authorize activity.
  D-052/ADR-0052 freezes the probe/collector contract. Q15-S2/ADR-0053
  implements, audits, and releases the pointer-order/integrity and
  counted-traversal slice in a clean no-authority bundle. Q15-S3/ADR-0054
  through ADR-0056 now repository-locally implement the literal same-buffer
  phase-spanning session, exact fakeable Linux acquisition seams, and all seven
  canonical collector components. Fake/no-allocation tests and strict
  traversal-plus-counter-boundary dual-disassembler audits pass. This work is
  handed off as one clean exact commit and a separate clean no-authority
  qualification-tool bundle. That clean v1 release intentionally has no
  production controller command. Clean Q15-R-P1 commit
  `a75bcdd0367d79f8ee0496c55edda74311c9ef7d` and v2 archive SHA-256
  `48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035`
  now bind the fixed controller as verified base evidence with authority
  `NONE`. Q15-R-P2 accepts D-061 through D-064 and ADR-0061 through ADR-0064.
  The fixed inherited-descriptor trust adapter, canonical receipt, fake tests,
  synchronized no-authority records, and blocked exact setup preparation are
  implemented locally. Clean commit `c8b69ab` produced and verified an
  adapter-bearing no-authority operational-release candidate. Q15-R-P3 accepts
  D-065 and selects its exact bytes without stand or execution authority;
  versioned successor preparation v2 resolves only the release
  evidence group and keeps five external inputs unresolved. Q15-R-P4-D accepts
  D-066 through D-070 as acquisition methods, implements the fixed no-authority
  prestate collector behind a fakeable executor, and prepares exact but
  unissued Q15-R-P4-R/Q15-R-P4-K records. Every literal value remains null and
  no stand was accessed. Clean commit `34da95d` now produces and verifies the
  no-authority collector-bearing v3 bundle at archive SHA-256
  `f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`.
  Q15-R-P4-E accepts D-071/ADR-0071 and selects those exact bytes as
  collector-release evidence only. Versioned successor P4-R preparation v2
  resolves only the clean collector-release group. Seven P4-R and eight P4-K
  inputs remain null, all execution authority remains false, and the collector
  has not run. Q15-R-P4-F accepts D-072 through D-075/ADR-0072 through
  ADR-0075, bound to governance commit `f30036e` and the immutable v3 archive.
  It freezes exact create-exclusive staging/capture/custody paths, named
  principals, a 1,800-second SSHSIG window, and split P4-R-I identity then
  P4-R-C one-shot collection with non-deleting partial retention. The two
  successor templates remain unissued and retain six null external-input
  groups each. P4-R v2 and P4-K remain byte-preserved with seven and eight null
  inputs respectively. Q15-R-P4-K-D accepts D-076 through D-079/ADR-0076
  through ADR-0079 for repository-local policy and template preparation only.
  It selects a later separately authorized new offline ceremony, logical
  custody domain `OWNER-OFFLINE-Q15-KEY-CUSTODY`, custodian
  `cpu-prefetch-q15-custodian`, split P4-K-A/P4-K-R, and the accepted
  operator/1,800-second/JCS-I64/SSHSIG/distinct-auditor profile. The original
  P4-K preparation remains unchanged with eight null inputs. Separate P4-K-A
  and P4-K-R templates are unissued with 13 and 9 null fields; the logical
  domain is not operational evidence. No key or public artifact is read,
  generated, copied, fingerprinted, created, signed, issued, or installed. A
  fully resolved and
  separately authorized four-role/custody setup,
  the five external trust/path/prestate inputs, exact signed Q15-R argv, and
  dynamic authority remain required.
  Q15-R-P4-K-A-D accepts D-080 through D-085/ADR-0080 through ADR-0085 as
  policy only. It freezes the exact offline environment/toolchain,
  encrypted-key custody, public export, bootstrap-root, fixed-controller, and
  issuance/review contracts while retaining all seven P4-K-A external inputs
  as null. D-093 later supersedes only the unaccepted bootstrap-genesis
  proposal and specified genesis security controls. Under its explicit critical
  risk acceptance, exactly one create-exclusive development-host unencrypted
  Ed25519 root was created and its public evidence verifies. D-094 subsequently
  records the exact `CREATED` to `ACTIVE` transition without using the private
  key. D-095 subsequently authorized exactly one signature and one target-key
  attempt under a further security downgrade. The signature verifies, but a
  deterministic wrapper defect stopped before target-key generation. The
  append-only partial tree remains and D-095 is terminal. D-096/ADR-0096
  separately authorized one corrected create-exclusive `p4-k-v2` transaction;
  its bootstrap signature, target public key/fingerprint, hashes, receipt, and
  private-key metadata verify. It stopped before P4-K-R. D-097/ADR-0097 then
  authorized and completed one separate bootstrap-signed public-only review;
  hashes, fingerprint, principal/key equality, receipt, and mandatory P5 stop
  verify without private access or presence probing.
  The later owner delegation authorizes repository-local work, and ADR-0086
  implements a generic no-authority controller admission/state-machine with no
  OS backend. It requires every future external hash, active signature,
  independent review, explicit bound, and direct process contract before it
  can mint a ticket. D-087 through D-092 remain byte-preserved but are
  superseded by D-093. P4-K-A and P4-K-R are complete under their accepted
  downgrade. D-098 prepares P5 but resolves only the two D-097 public groups;
  operational release root, independent secondary custody root, and fresh
  stand prestate remain null. D-099/ADR-0099 completed the exact signed P4-R-I
  gate with four successful pinned-host read-only observations, one immutable
  local capture, one single-owner review, and a mandatory stop without stand
  mutation. D-100 through D-103 are accepted under ADR-0100 through ADR-0103
  for repository-local implementation only. The fixed D-104 executor, output
  schemas, fake full graph/failure matrix, and still-unissued preparation are
  implemented with zero action authority. Because D-099 did not identify the
  remote Python, `dd`, and tar runtime used by that implementation, the
  executor retains an explicit null runtime-acceptance gate and cannot execute.
  Clean implementation commit `dc643df` and D-099..D-108 records/evidence are
  now hash-preserved. D-105 through D-108 remain proposed/unaccepted and are no
  longer an endlessly recursive pilot gate. ADR-0104 adds the sole finite
  successor: `PREPARED -> AUTHORIZED_FOR_READ_ONLY_PREFLIGHT ->
  PREFLIGHT_ACCEPTED -> READY_FOR_STAGE17_PHASE_AUTHORIZATION`. The pilot owner
  may hold owner/operator/controller/custodian/auditor roles and one
  authorization may cover the frozen read-only preflight observation set; no
  independent-review claim is permitted. The current state remains `PREPARED`
  because the ADR-0105 genesis journal contains no resolution or transition
  records. The immutable requirement catalog therefore reports all ten
  `S17-EXT` inputs missing. The historical `S17-EXT-006` release metadata is
  preserved but cannot resolve the input until caller-supplied archive and
  sidecar bytes pass their fixed integration contract and a real custody
  receipt is recorded. The D-104 self-test is hermetic; real qualification
  archive bytes are handled only by an explicit external-artifact integration
  contract. No
  stand, P4-R-C, P5, Q15, calibration, pilot, measurement, or confirmatory
  action is authorized.
  Q15-S1/ADR-0051 accepts and
  locally implements the separate tool plus Q15-R/Q15-W split; neither
  preparation record is authority. Separate
  dependency-ready scientific phase inputs and an exact phase authorization
  remain mandatory. No Stage 17 record authorizes Stage 18.

## Phase 18 — Confirmatory execution

- **Objective:** Execute the frozen common Stage A block pool and the exact H3/H1/H2 access chronology.
- **Inputs and prerequisite decisions:** All prior phases accepted; complete freeze record; final blocks/roles/seeds; matrix feasibility; stand/replacement budgets; named authorities; technical sealing.
- **Files/components:** Immutable Stage A raw/join/integrity/manifests, block/failure/replacement/access records, authorized derived analyses.
- **Tests:** Every runbook gate; continuous hash/access audit; block completeness; valid FULL/low-tail classification; replacement cap; selection/unseal/evaluation/release chronology; final provenance reconstruction.
- **Acceptance criteria:** No unauthorized access or silent protocol/build drift; all primary inputs are valid complete blocks or affected hypotheses explicitly unresolved; analyses follow frozen families and source hashes.
- **Explicitly excluded:** Outcome-dependent deletion, reseeding, narrowing, extending, tuning, repeat-until-success, Stage B/C substitution, or recommendation outside passed H3 contexts.
- **Rollback or failure behavior:** Raw evidence is never rolled back. Stop on contradiction, leakage, custody loss, cap exhaustion, or failed mandatory control; retain failures and report unresolved status. Changes require amendment and cannot erase prior records.
- **Status:** `PROHIBITED`.

## Deferred future work

Stage B tagged-pointer NBLFQ and Stage C robustness ablations are not implementation phases here. They may be planned only after separate approved scope and can never repair, replace, or reinterpret Stage A cells.
