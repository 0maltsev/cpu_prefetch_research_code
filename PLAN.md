# Stage A Implementation Plan

Protocol version: **`2.0.0-pre.1`**. Status values are `COMPLETE`, `BLOCKED`, `PENDING`, and `PROHIBITED`. The phases are dependency ordered; a later phase may be explored only where it cannot force an unresolved earlier choice. Stage B and Stage C are deferred future work outside this plan and require separate authorization/amendment.

## Phase 1 — Protocol import and traceability

- **Objective:** Freeze an exact authoritative snapshot and map normative requirements to future owners and gates.
- **Inputs and prerequisite decisions:** Paper repository at the supplied sibling path; actual version and declared hashes established from repository evidence.
- **Files/components:** `protocol/2.0.0-pre.1/`, import manifest, root governance/status/readme, all `docs/` planning records.
- **Tests:** Source/import size and SHA-256 equality; declared-hash verification; JSON/schema validation; link/version/scope/file audits.
- **Acceptance criteria:** Every required artifact is byte-identical and listed; all requested documents exist; all normative areas have owner/validator; no production code, result, or invented platform value exists.
- **Explicitly excluded:** Benchmark, queues, controls, runner, analysis pipeline, calibration, pilot, confirmation.
- **Rollback or failure behavior:** A declared-hash mismatch or normative contradiction stops bootstrap; do not repair imported bytes. Remove no source evidence; replace a bad import only from verified source and record a new timestamp/manifest.
- **Status:** `COMPLETE`; fresh Draft 2020-12 meta-schema revalidation is explicitly tooling-blocked because no conforming validator is installed. JSON syntax and all other available Phase 1 checks pass.

## Phase 2 — Implementation-decision freeze

- **Objective:** Resolve the smallest engineering decisions needed to finalize production architecture without selecting pilot outputs.
- **Inputs and prerequisite decisions:** Phase 1; queue provenance/license investigation; candidate language/atomic feasibility; storage/validator/sealing/platform capability evidence.
- **Files/components:** Accepted ADRs for queue provenance/mode, language/standard/atomic envelope, storage/semantic-validator architecture, identity/SHA/canonical-record dependencies, sealing boundary, and credible target-platform control interface; updated status/commands.
- **Tests:** License/provenance review; architectural scenario tests for early failure, immutable raw correction, sealing, and unavailable platform control; atomic/sanitizer/tool support matrix.
- **Acceptance criteria:** Every pre-architecture row in `docs/IMPLEMENTATION_DECISIONS.md` has an accepted evidence-backed ADR; no scientific behavior changed; contradictions have amendments, not workarounds.
- **Explicitly excluded:** Production source, concrete physical raw encoding, platform numerical values, pilot/confirmatory decisions.
- **Rollback or failure behavior:** Reject or supersede an unsupported ADR before code depends on it. If no eligible artifact/platform architecture exists, record `BLOCKED_BEFORE_IMPLEMENTATION` and stop.
- **Status:** `BLOCKED` and the exact next safe phase; user decisions/evidence are required.

## Phase 3 — Build and CI foundation

- **Objective:** Create reproducible build, dependency, formatting/lint, test, sanitizer, schema, and clean-room entry points for the selected stack.
- **Inputs and prerequisite decisions:** Accepted Phase 2 language, build, dependencies, target support, and licensing ADRs.
- **Files/components:** Minimal build manifests, dependency records, CI workflows, test skeleton, command documentation; no benchmark behavior yet.
- **Tests:** Clean configure/build, empty/minimal test invocation, pinned Draft 2020-12 validator, lint/format, sanitizer capability probes, dependency/license scan, clean-environment reproduction.
- **Acceptance criteria:** Documented commands work from a clean environment; versions and hashes are captured; failures are nonzero and artifacts retained; no platform-specific constant is embedded.
- **Explicitly excluded:** Queue and measurement implementations, performance tests, pilot.
- **Rollback or failure behavior:** Keep previous accepted tool record; supersede build ADR/tool versions rather than silently drifting; block Phase 4 if clean reproduction fails.
- **Status:** `PENDING`, blocked by Phase 2.

## Phase 4 — Protocol/configuration model

- **Objective:** Implement `2.0.0-pre.1` record types, Draft schema validation, checked identities/arithmetic, and cross-record semantic validation framework.
- **Inputs and prerequisite decisions:** Phase 3; storage/identity architecture; canonical serialization policy; compatibility rule.
- **Files/components:** Protocol/config model, schema loader, semantic-validator rule registry, typed lifecycle/status/identity records, test fixtures.
- **Tests:** Positive/negative tests for all seven schemas; `1.x` rejection; arithmetic, referenced-hash, namespace, chronology, factorial, and lifecycle semantic fixtures.
- **Acceptance criteria:** Every imported schema has conformance coverage; semantic-invalid/schema-valid cases reject; validators never repair data; rule failures identify requirement IDs.
- **Explicitly excluded:** Queue operations, platform mutation, raw physical codec, experiment execution.
- **Rollback or failure behavior:** Preserve rejected fixtures and rule evidence; a schema/spec conflict stops implementation and requests amendment.
- **Status:** `PENDING`.

## Phase 5 — Queue provenance and correctness

- **Objective:** Implement or adapt the exact ring and linked-plus-recycler packages behind a non-distorting static seam and prove their stated semantics.
- **Inputs and prerequisite decisions:** Phase 4; immutable queue provenance/licenses/modes; atomic width/alignment/memory-order/layout decisions.
- **Files/components:** Queue package sources, static adapters, provenance/refinement records, abstract FIFO/reference tests; no workload driver.
- **Tests:** FIFO/boundary/wrap/reuse; linearization/refinement histories; delayed-worker progress; node ownership/recycler stress; lock-free atomic evidence; ASan/UBSan/TSan where compatible; generated queue-boundary inspection.
- **Acceptance criteria:** Zero unresolved correctness/sanitizer findings; fixed-arena full refinement accepted; required atomics lock-free; no fallback allocation or silent source deviation.
- **Explicitly excluded:** Prefetch-effect measurement, arrivals, timing, pilot.
- **Rollback or failure behavior:** Retain failing artifact/test record; fix or supersede implementation under same proven semantics. A semantic change requires amendment.
- **Status:** `PENDING`.

## Phase 6 — Record and working-set construction

- **Objective:** Build immutable one-line event records, persistent arenas, linked node cycle, footprint accounting, and address-pattern evidence.
- **Inputs and prerequisite decisions:** Phases 4–5; line-size/platform facts; RNG/permutation/mixing/checksum candidates for correctness fixtures.
- **Files/components:** Record/arena builders, footprint calculator, permutation/address report, content/index/delta checksum integration.
- **Tests:** Alignment/layout, immutability, persistent identity, exact cycle, bijection/golden order, distinct line/page, stride/modal/period thresholds, paired checksums, corruption/write detection, generated record-load/mix checks.
- **Acceptance criteria:** Both packages use identical event arena/order; linked gates are reproducible; no measured-path allocation/permutation; exact footprint method is documented.
- **Explicitly excluded:** Platform capacity selection from uncollected evidence, performance claims, Stage C mutable records.
- **Rollback or failure behavior:** Pre-freeze seed failure advances only under the frozen treatment-blind stream; post-freeze mismatch invalidates affected run. Never reseed from treatment outcome.
- **Status:** `PENDING`.

## Phase 7 — Schedule generation

- **Objective:** Generate reproducible open-loop schedules and namespace/seed records independently of completion.
- **Inputs and prerequisite decisions:** Phase 4; RNG/version/master derivation, permutation, time unit, deadline encoding, overflow behavior.
- **Files/components:** Namespace derivation, schedule generator/codec/envelope, exact rational-rate handling, immutable storage seam.
- **Tests:** Golden cross-build streams; decode round-trip; nondecreasing deadlines; exact count; half-open horizon; overflow rejection; completion independence; disjoint namespaces; matched-treatment sharing.
- **Acceptance criteria:** All semantic schedule rules pass; no implementation-defined RNG behavior; schedule generation is absent from timed path.
- **Explicitly excluded:** Concrete confirmatory rates/horizons/seeds and any tuning from outcomes.
- **Rollback or failure behavior:** Algorithm/version change creates new records and invalidates dependent schedules; never silently regenerate a frozen schedule.
- **Status:** `PENDING`.

## Phase 8 — Timing

- **Objective:** Implement exact producer/consumer timestamp boundaries and an accepted platform clock mapping without altering queue order.
- **Inputs and prerequisite decisions:** Phases 5 and 7; target clock, integer conversion, serialization, overhead policy, acceptance limits.
- **Files/components:** Tick reader/converter, boundary instrumentation, clock acceptance/calibration records, generated-code checks.
- **Tests:** Monotonicity, skew/drift/resolution/read cost, conversion goldens, boundary ordering, regression/negative correction faults, disassembly for compiler motion and synchronization effects.
- **Acceptance criteria:** Every fixed logical boundary is representable exactly; clock passes on selected cores; corrected and uncorrected values retained; queue order is unchanged.
- **Explicitly excluded:** Performance comparison and pilot until the full measurement system passes.
- **Rollback or failure behavior:** Clock failure makes platform/build ineligible or run invalid as appropriate; no substitute source without new ADR/evidence.
- **Status:** `PENDING`.

## Phase 9 — Platform control

- **Objective:** Implement least-privilege affinity, actual-CPU, NUMA/first-touch/residency, requested/verified HW-PF, relax, environment, and topology evidence.
- **Inputs and prerequisite decisions:** Target OS/architecture/platform inventory; named privilege authority; documented APIs/manuals; clock from Phase 8.
- **Files/components:** Platform inventory provider, control/readback/probe interfaces, placement verifier, environmental recorder, failure-safe restoration path.
- **Tests:** Capability and permission negatives; near/far topology; before/during/after residency; migration faults; readback/probe mismatch; relax generated code; restoration after failure.
- **Acceptance criteria:** Required controls are both requested and independently verified; no generic “disabled/local” claim; loss of verification stops the run; privileges are scoped/audited.
- **Explicitly excluded:** Invented commands/values and confirmatory state changes before authorization.
- **Rollback or failure behavior:** Restore authorized default safely, retain audit/failure evidence, and mark platform ineligible if mandatory control cannot be proved.
- **Status:** `PENDING`, platform evidence required.

## Phase 10 — Run state machine

- **Objective:** Integrate specialized workers with lifecycle, warm-up/drain/reset/barriers, one-attempt workload, polling, termination, and honest partial-failure recording.
- **Inputs and prerequisite decisions:** Phases 5–9; process/thread model; warm-up/recovery records may remain symbolic for synthetic fixtures.
- **Files/components:** Controller, prepared run image, worker specializations, phase state machine, failure recorder, counts/integrity hooks.
- **Tests:** Every lifecycle transition; delayed/suspended workers; exact reset origin; no remap/retouch; no sleep/yield/backoff; release/acquire termination; backlog order; one attempt; early/partial failure without fabricated artifacts.
- **Acceptance criteria:** Hot path obeys allowlist; lifecycle evidence is complete; warm-up cannot leak; drain/count rules hold; generated code has no dynamic treatment dispatch.
- **Explicitly excluded:** Real pilot/confirmation and offline analysis.
- **Rollback or failure behavior:** Seal actual partial artifacts and failure; never resume the same run identity or synthesize missing output.
- **Status:** `PENDING`.

## Phase 11 — Raw storage and integrity

- **Objective:** Implement the frozen physical format, preallocated private buffers, immutable artifacts/envelopes, checksums, compression/copy policy, and capacity proof.
- **Inputs and prerequisite decisions:** Phase 10; physical format/row sizes/alignment/endianness/time unit; checksum/serialization/compression/copy decisions; horizon bounds.
- **Files/components:** Producer/consumer codecs and buffers, external artifact store, integrity reports, sealing and decode interfaces.
- **Tests:** Codec round-trip/cross-decoder; exact row count; `run_id`; overflow; no hot I/O/allocation; corruption/truncation/reorder; known checksums; pre/post content; capacity/disk exhaustion; immutable correction behavior.
- **Acceptance criteria:** Longest planned horizon fits without overflow/I/O; decoded rows conform logically; raw sources cannot be overwritten; compression is lossless/post-run only.
- **Explicitly excluded:** Quantiles/models and pilot until integration acceptance.
- **Rollback or failure behavior:** Any overflow/corruption is a measurement failure; append corrected derived/envelope records, never mutate raw bytes.
- **Status:** `PENDING`, physical format deliberately unresolved.

## Phase 12 — Reconciliation and validity gates

- **Objective:** Join private streams, derive exact intervals, classify statuses independently, and enforce manifest completeness.
- **Inputs and prerequisite decisions:** Phases 4, 10, 11; frozen logical contracts and integrity algorithms.
- **Files/components:** Join audit, accepted-sequence reconciler, joined-derived codec, status/gate evaluator, complete manifest assembler.
- **Tests:** Count/pointer/index/identity/ordinal/loss/duplicate/reorder/timestamp/equation fault injection; failed-audit no-join; valid `FULL`; valid low `N_eff`; missing-artifact negatives.
- **Acceptance criteria:** Latency exists only after passed audit; all equations exact; validity/zero-loss/effective-tail/block statuses remain independent; complete valid Stage A obligations enforced.
- **Explicitly excluded:** Replacement decisions based on FULL/low count and scientific effect analysis.
- **Rollback or failure behavior:** Seal failed audit and retain raw sources; invalid run makes original block incomplete; no in-place repair.
- **Status:** `PENDING`.

## Phase 13 — Service-rate, zero-loss, and ring-distance calibration

- **Objective:** Implement treatment-blind calibration modes and records without selecting results in advance.
- **Inputs and prerequisite decisions:** Phases 5–12; approved calibration estimators, durations, repetition counts, matrix feasibility method/threshold/global rule, `d2` procedures, authority and stand budget.
- **Files/components:** Service-ready and open-loop probe modes, calibration planner/records, `mu_ref`/matrix-bound/`d2` calculation validators.
- **Tests:** Cell-configuration equality; continuous-ready-only difference; independent run-level LCB/minimum; all-exposure union bound; zero-observed-not-zero-bound; global action; `d2` rounding/minimum/cap/context properties.
- **Acceptance criteria:** Procedures are frozen before applicable results; outputs source-link valid evidence; no confirmatory outcome or cell-specific favorable adjustment enters decisions.
- **Explicitly excluded:** Pilot/confirmatory collection in this implementation phase and empirical recommendation.
- **Rollback or failure behavior:** Material build/platform/action/capacity change invalidates calibration freeze and requires new calibration; infeasible matrix stops confirmation.
- **Status:** `PENDING`, numerical inputs and execution unauthorized.

## Phase 14 — Stage A block planning and orchestration

- **Objective:** Build exact 180-cell plans, whole plots, role-specific namespaces, immutable roles, and complete-block replacement workflow.
- **Inputs and prerequisite decisions:** Phases 4, 7, 9–13; frozen `delta_star`, repetition counts, seeds, roles, recovery, budget, sealing, replacement cap/authority before final plans.
- **Files/components:** Factorial block generator/validator, role/access-aware scheduler, orchestration records, replacement authorization/stop workflow.
- **Tests:** Exact product/ordinals; H0/H1 whole plots; order/randomization goldens; role/seed compatibility; count formulas; original null fields; replacement lineage/new identity/full product; cap exhaustion; no cell repair.
- **Acceptance criteria:** Every final block is exact and immutable; all counts are evidence-derived; validation roles technically sealed; replacement workflow stops at budget.
- **Explicitly excluded:** Executing Stage A during planner implementation; Stage B/C blocks.
- **Rollback or failure behavior:** Discard only an unexecuted invalid plan by superseding it; executed/failed plans remain append-only. Any missing count/role/seed keeps confirmation blocked.
- **Status:** `PENDING`.

## Phase 15 — Offline analysis

- **Objective:** Implement source-linked run summaries, tail diagnostics, fixed model/contrasts, separate H1/H2 max-T, and sealed H3 selection/validation.
- **Inputs and prerequisite decisions:** Phases 4 and 12–14; `delta_star`, `B_boot`, seed, model matrix, effective-tail rules, access authorities; synthetic fixtures only until authorized data exist.
- **Files/components:** Quantile/effective-count summaries, design-matrix/contrast registry, block bootstrap, H3 access-aware workflows, derived provenance/manifests.
- **Tests:** Independent quantile goldens; drain/ties/no-pooling; effective thresholds; rank/alias; exact 7/20/270/540/54 registries; complete-block resampling; max-T goldens; selection ties; access negatives; missing/gate-blocked outcomes.
- **Acceptance criteria:** Outputs reproduce from named immutable inputs; no event pseudo-replication; no family mixing; access chronology enforced; blocked estimands reported, not imputed.
- **Explicitly excluded:** Empirical Results/Discussion/recommendation before valid authorized confirmation.
- **Rollback or failure behavior:** Append corrected derived artifact linked to unchanged raw sources; access leakage is a stop/audit condition, not a rerun opportunity.
- **Status:** `PENDING`.

## Phase 16 — Pre-pilot verification

- **Objective:** Demonstrate integrated software correctness and reproducibility before any performance pilot.
- **Inputs and prerequisite decisions:** Phases 3–15 implemented to pilot-applicable scope; all pre-pilot decisions frozen; pilot plan/authority/budget.
- **Files/components:** Release candidate build, complete verification bundle, clean-room record, synthetic dry-run records, pre-pilot readiness report.
- **Tests:** Full `docs/TEST_STRATEGY.md`: schema/semantic, unit/property, queue/refinement/stress, sanitizers, generated code, timing/platform, storage/integrity, reconciliation/lifecycle, 180 cells, sealing/replacement, clean environment, synthetic end-to-end.
- **Acceptance criteria:** Every applicable check freshly passes; no unresolved correctness issue; clean build reproducible; storage/control/custody proven; synthetic results clearly non-empirical.
- **Explicitly excluded:** Pilot execution until a separate authorization decision after readiness review.
- **Rollback or failure behavior:** Classify and fix software/test/environment failures; supersede build and rerun affected then broad checks. Never waive a failed gate to collect data.
- **Status:** `PENDING`.

## Phase 17 — Pilot execution

- **Objective:** Collect treatment-blind evidence needed to freeze platform-dependent capacities, calibration outputs, horizons, environment, precision, and feasibility.
- **Inputs and prerequisite decisions:** Phase 16 accepted; pilot authority, namespaces, plan, durations/repetitions, controls, custody, storage, stand budget.
- **Files/components:** Immutable pilot/calibration run artifacts, failure records, blinded summaries, freeze-decision inputs; no confirmatory namespace.
- **Tests:** Per-run runbook gates, manifest completeness, join/integrity, blinded covariance/tail/recovery/environment procedures, no-access and namespace audits.
- **Acceptance criteria:** Evidence is complete and treatment-blind for each required freeze; no failed correctness gate; all confirmatory decisions can be justified or the study is declared infeasible/unresolved.
- **Explicitly excluded:** Confirmatory outcomes, result-bearing claims, treatment-driven tuning, pilot substitution for Stage A.
- **Rollback or failure behavior:** Preserve all pilot artifacts/failures. Material implementation/platform change invalidates dependent pilot evidence. Do not cherry-pick or repeat for favorable effects.
- **Status:** `PROHIBITED` until Phase 16 and explicit authorization.

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
