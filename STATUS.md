# Repository Status

Protocol snapshot: **`2.0.0-pre.1`**

Repository state: **`STAGE_11_SOFTWARE_COMPLETE_STAGE12_PROTOCOL_IMPORT_BLOCKED`**

Readiness verdict: **`D031_Q10_ACCEPTED_AMENDED_PROTOCOL_IMPORT_REQUIRED_MEASUREMENT_PROHIBITED`**

## Readiness by area

| Area | State | Evidence or blocker |
|---|---|---|
| Stage 1 import/traceability | `COMPLETE_REVERIFIED` | The Stage 11 closure freshly passed all 18 manifest sizes/SHA-256 values, exact inventory, four authoritative hashes, JSON parsing, and Draft 2020-12 meta-schema validation for all seven imported schemas. |
| Stage 2 implementation-decision freeze | `COMPLETE`; Q9 accepted | ADR-0001 through ADR-0033 are accepted. ADR-0032/0033 freeze the Stage 11 physical-row and no-compression/two-domain policies; their local implementation passes while operational domain/capacity evidence remains open. |
| Stage 3 build/CI foundation | `COMPLETE_LOCAL` | ADR-0022, constrained offline inputs, dual compiler/library presets, lint, sanitizer, metadata, package, and pinned self-hosted CI foundations remain passing. |
| Stage 4 protocol/configuration model | `COMPLETE_LOCAL` | ADR-0023, typed C++20 records for all seven schema families, strict loading, immutable configuration, record-local semantic rules, exact `JCS-I64-v1`, and explicit cross-record interfaces are implemented and pass the recorded matrix. |
| Queue implementation | `COMPLETE_LOCAL` | ADR-0024 fixes distinct independent ring and linked/recycler adapters, exact release/acquire, fixed-arena refinement, source-hashed provenance, layout/lock-free probes, and correctness suites. GNU Binutils 2.46 and LLVM 22.1.6 release disassembly/mutant checks pass and both instruction views were reviewed. |
| Workload construction | `COMPLETE_LOCAL` | ADR-0025 through ADR-0028 fix the deterministic stream, unbiased permutations, payload/mixer/integrity grammars, event/node layouts, and five package mechanisms. Known-answer/property/corruption/no-allocation and dual-disassembler checks pass. |
| Schedule generation | `COMPLETE_LOCAL` | ADR-0029's offline Decimal80/Philox suite, external u64be artifact, imported envelope, derivation record, immutable C++ decoder, namespace/common-family validation, and failure/golden/corruption matrices pass. |
| Timing system | `COMPLETE_SOFTWARE`; platform gate open | `cpu_prefetch_timing` implements D-009's selected reader, exact conversion, producer/consumer boundary capture, offline equations, qualification evaluators, no-correction diagnostics, and dual-disassembler/mutant audit. Development-host evidence is engineering-only. No explicit eligible pair, full dynamic qualification, or before-block evidence exists. |
| Platform layer | `COMPLETE_SOFTWARE`; operational stand gate open | `cpu_prefetch_platform` implements read-only Linux CPU/core/package/NUMA/cache/PCI/environment inventory, capability states, strict Stage A placement/memory/page validation, dry-run/injected apply, separate fresh readback, reverse restoration, rich canonical evidence, and exact imported-schema platform records. No production mutating backend, authority/whitelist, selected pair/address proof, vendor HW-PF mapping/probes, restoration exercise, or dynamic clock qualification exists. |
| Lifecycle/controller | `COMPLETE_SOFTWARE`; integration gates open | `cpu_prefetch_lifecycle` implements the exact internal graph/imported projection, and Stage 11 statically binds complete captures to preallocated private streams. Concrete queue-reset/package binding, platform relax/watchdog values, and final combined-worker codegen remain later gates. |
| Raw storage/integrity | `COMPLETE_LOCAL`; operational gate open | `cpu_prefetch_storage` implements the accepted codec, bounded private streams, immutable envelopes/integrity records, checked budgeting, no-replace two-copy local publication, recovery-only reopening, and partial finalization. Real domains/custody, run-plan capacity, residency, and recovery evidence remain Phase 16 gates. |
| Measurement system | `NOT_AUTHORIZED` | The Stage 10/11 integration is synthetic correctness infrastructure, not a stand runner. No eligible-pair qualification, production platform mutation, concrete run plan, reconciliation, or scientific run exists. |
| Pre-pilot validation | `NOT_STARTED` | Requires Stages 5–15 and fresh eligible-platform/custody evidence. |
| Pilot | `PROHIBITED` | Stage 16 and explicit pilot authorization are absent; this one-NUMA-node development host is ineligible for near/far evidence. |
| Confirmatory execution | `PROHIBITED` | Pilot outputs and later freeze records, budgets, authorities, and sealing proof are absent. |

## Stage 4 products

- `cpu_prefetch_protocol`, with exact-value JSON, opaque IDs, typed hashes,
  all registered enums, and typed schedule/raw/join/integrity/manifest/block/
  failure/freeze/amendment/platform record families;
- `ScientificConfiguration`, which is immutable after validated construction;
- `Stage4SemanticValidator` for record-local arithmetic, lifecycle, factorial,
  access-record, and requested/verified-state rules;
- `CrossRecordSemanticValidator`, an intentionally unimplemented contract for
  later store-dependent reconciliation, lineage, and access chronology;
- imported-schema validation for all seven Draft 2020-12 schemas, with 17
  positive and 15 negative fixtures;
- C++ unit/property tests for exact rates and integers, stable error paths and
  categories, partial failures, valid `FULL`, low `N_eff`, accepted ordinals,
  joined timestamps/equations, exact 180-cell original/replacement blocks, all
  six H3 contexts, unseal evidence, version/enum rejection, and round trips;
- shared C++/Python `JCS-I64-v1` fixtures for integer boundaries, RFC binary64
  forms, escaping, and UTF-16 key order;
- ADR-0023 and synchronized architecture, data-flow, model, test, risk,
  traceability, plan, README, package, and CI records.

Stage 4 introduced no queue behavior. The Stage 5 operations below execute only
in correctness tests; no performance measurement or placeholder scientific
result is emitted.

## Stage 5 products

- `cpu_prefetch_queue`, with direct final ring and linked/recycler adapters;
- contiguous ABI-pointer-width atomic ring slots and separate modulo cursor
  ownership lines;
- exactly `C+1` linked nodes, supplied permutation, release/acquire successor
  publication, and a separate bounded SPSC atomic-pointer recycler;
- explicit `QueueCapacity` and `CacheLineBytes` inputs with no platform default,
  compile/runtime pointer-width/lock-free rejection, and runtime layout reports;
- machine-readable provenance records binding paper/version, official-artifact
  status, no source reuse, no-license status, source SHA-256 values,
  adaptations, atomic mapping, claims, refinement, and codegen status;
- abstract FIFO, boundary, wrap, rollover-assumption, exact node-cycle,
  one-attempt, phase-suspension, fault-detection, RapidCheck, and concurrent
  stress tests;
- ADR-0024 and the written happens-before/linearization/fixed-arena refinement
  record in `docs/QUEUE_CORRECTNESS.md`.

No queue operation records time/rate or consumes a schedule. No measurement
loop, platform control, platform prefetch instruction, or empirical output
exists.

## Stage 6 products

- `cpu_prefetch_workload`, with independent Philox4x32-10, OpenSSL 3
  HMAC-SHA-256 derivation, and explicit purpose domains;
- base-page-aligned, fully touched one-line event storage with immutable index,
  payload, and padding, strong record/logical-sequence/accepted-ordinal types,
  and no pointer identity serialization;
- unbiased cyclic event order, deterministic complete `C+1` node order,
  within-arena closure deltas, and exact content/order/delta SHA-256 inputs;
- exact footprint calculation and three protocol working-set selectors over
  explicit cache facts and candidates, with no host fallback;
- five concrete static package policies `R0`, `R1`, `R2`, `L0`, and `L1`, exact
  fake-emitter target tests, and no default platform encoding or `d2`;
- fixed branch-free private consumer mixer, a 10,000-cycle post-preparation
  allocation hook, and GNU/LLVM workload generated-code checks/mutant;
- ADR-0025 through ADR-0028 and
  [`docs/WORKLOAD_CONSTRUCTION.md`](docs/WORKLOAD_CONSTRUCTION.md).

## Stage 7 products

- `tools/generate_schedule.py`, a standalone Python 3.14 generator for the
  exact ADR-0029 Decimal80/Philox suite with no implicit scientific inputs;
- append-only external `SCHEDULE-ABS-U64BE-v1` bytes, imported-schema schedule
  envelope, and immutable implementation-owned derivation record;
- `cpu_prefetch_schedule`, whose decoder validates the complete suite,
  derivation/runtime binding, byte/count/order/horizon invariants, and all
  artifact/decoded/envelope/derivation hashes before exposing immutable ticks;
- explicit warm-up, calibration, pilot, H3 training, H3 validation, H1/H2
  supplemental, and diagnostic roles with disjoint child namespaces and exact
  common-schedule-family matching;
- direct and integrated Philox/decimal goldens, C `decimal` versus `_pydecimal`
  parity, byte-for-byte reproduction, schema/canonical round trips,
  malformed/overflow/publication negatives, and an API-level outcome-
  independence test;
- [`docs/SCHEDULE_GENERATION.md`](docs/SCHEDULE_GENERATION.md) and the
  implementation-owned derivation schema under `config/schemas/`.

## Stage 8 products

- `cpu_prefetch_timing`, with the compiler-fenced vDSO
  `CLOCK_MONOTONIC_RAW` reader, checked absolute-nanosecond construction, exact
  relative-picosecond conversion, and raw-plus-derived in-memory samples;
- static producer and consumer capture for `a,b,c,u,p,r^e,v,q,r^d,f`, with
  accepted-only `p`/ordinal, no row for empty dequeue, and fail-closed partial
  observation handling;
- ring and linked queue boundary observers that place `p` immediately before
  release publication and `q` immediately after successful acquire observation
  and before L1 prefetch/reuse/action;
- offline identity/order validation and exact joined-record equations, with
  additive end-to-end components separated from nested diagnostics;
- exact static, per-core, and bidirectional three-window D-009 qualification
  evaluators whose accepted counts cannot be satisfied by short diagnostics;
- explicit uncorrected overhead summaries and no corrected output surface;
- GNU/LLVM reader and all-five-package generated-code checks with moved-p,
  moved-q, missing compiler fence, hardware fence, wrong clock, and forced
  syscall source mutants;
- [`docs/TIMING.md`](docs/TIMING.md), which records exact semantics and the
  remaining explicit-pair/platform gate.

## Stage 9 products

- `cpu_prefetch_platform`, with separate inventory, capability, request
  validation, apply, independent verify, restoration, and manifest operations;
- a Linux read-only provider for logical CPU/core/package/SMT/NUMA/cache and PCI
  locality plus CPU, page, kernel, microcode, firmware, power/environment,
  compiler, and standard-library observations;
- strict explicit `NEAR`/`FAR` non-SMT pair validation, producer-home shared
  storage, worker-local private buffers, and exact base-page rules, with Stage C
  placement/page choices rejected;
- typed requested controls for affinity/actual CPU, memory/residency/pages,
  governor/frequency/turbo/C-state/SMT/interrupt/isolation, HW prefetch,
  clocksource, and build/platform provenance;
- dry-run that never invokes an actuator, injected external actuation only,
  mandatory pre-state, fresh independently identified exact readback, stale
  snapshot/epoch rejection, and reverse-order restoration with retained partial
  failures;
- deterministic `LINUX-PLATFORM-EVIDENCE-v1` rich manifests and a separate
  exact `platform.schema.json` projection, both with explicit content identity;
- 12 platform tests covering topology, placement, sibling/NUMA/policy faults,
  capability/authority, dry-run/apply/readback disagreement, stale evidence,
  partial restoration, manifest completeness/partial failure/schema loading,
  and safe development-host inventory;
- [`docs/PLATFORM_CONTROL.md`](docs/PLATFORM_CONTROL.md) and an expanded
  read-only [`docs/STAND_RUNBOOK.md`](docs/STAND_RUNBOOK.md).

No privileged command, MSR access, service change, boot change, affinity
change, NUMA binding, governor/frequency change, or hardware-prefetch change
was executed on the current host.

## Stage 10 products

- `cpu_prefetch_lifecycle`, with a 16-phase internal graph projected onto the
  unchanged eight-value imported lifecycle enum and an exhaustive legal-edge
  table;
- transition records carrying monotonic sequence/time, actor, reason, exact
  protocol projection, and explicit append/retain/absence consequences;
- deterministic preparation and warm-up evidence with distinct typed schedule
  and namespace IDs, complete preallocation/verification, stopped arrivals,
  drain, barrier, and no ambiguous continuation;
- a replaceable logical-reset backend plus exact ring/linked reset verifier
  that preserves allocation, mapping, data home, permutation, and payload;
- a two-worker start barrier publishing one explicit origin, checked deadline
  arithmetic, exactly one producer backend attempt per due arrival, continuous
  consumer polling, and no outcome-derived schedule/retry path;
- `ARRIVALS-FINISHED-U32-RELEASE-ACQUIRE-v1`, with explicit cache-line input,
  compile/runtime lock-free evidence, producer release publication, consumer
  acquire observation, and drain-to-empty;
- explicit start/measurement/drain watchdog and cancellation failures with
  actual partial counts, plus recovery records only after finalization;
- 24 focused tests covering all state pairs/failure phases, early/partial
  artifacts, warm-start faults, empty/`FULL`/partial execution, start and
  publication races, backlog drain, causal failure attribution, watchdogs, and
  100 deterministic varied-scheduling histories; and
- [ADR-0031](docs/decisions/0031-stage10-lifecycle-and-termination-mapping.md)
  plus [`docs/LIFECYCLE.md`](docs/LIFECYCLE.md).

No scientific queue run, latency/throughput comparison, platform mutation, or
pilot was performed. Fake schedules, clocks, queues, storage, and scheduling
are software-correctness evidence only.

## Stage 11 products

- `cpu_prefetch_storage`, with 64-byte-aligned producer-private and
  consumer-private fixed-capacity streams whose owning worker explicitly
  initializes and first-touches every reserved byte before release;
- exact `RAW-OBS-U64LE-LP-RUNID-v1` producer, consumer, and compatibility-only
  joined codecs with literal UTF-8 run IDs, zero padding, little-endian u64
  words, raw nanoseconds, relative picoseconds, strict flags, and fail-closed
  external decoding into Stage 4 logical rows;
- a static `CapturingObservationBackend` connecting Stage 8 captures to Stage
  10 one-attempt calls, with row commit before success and sticky overflow as
  measurement failure;
- canonical phase/integrity reports and imported raw envelopes plus a separate
  versioned copy ledger carrying exact algorithm IDs, hashes, counts,
  completeness, domains, URIs, and independent readback results;
- checked per-run and plan-wide budgets for actual/conservative hot bytes,
  page-rounded mappings, one temporary copy, two durable raw copies, two
  joined-derived copies, metadata, and explicit reserve/available capacity;
- a Linux local append-only correctness backend using unique run directories,
  exclusive staging, checked writes/sync, streaming SHA-256 rereads, atomic
  no-replace publication, two explicit domain IDs/roots, and a fresh-process
  recovery-only mode that cannot publish new objects;
- crash-aware finalization that publishes only streams actually present,
  retains partial evidence, never emits joined data, and never upgrades
  storage completeness into scientific validity; and
- format/golden/corruption/boundary/no-allocation/concurrency/large-stream,
  store/fault/recovery/finalization, schema, sanitizer, static-analysis, and
  dual-disassembler tests documented in [`docs/STORAGE.md`](docs/STORAGE.md).

No producer/consumer reconciliation, latency construction, gate evaluation,
performance measurement, or benchmark result was implemented.

## Fresh local verification

| Check | Result |
|---|---|
| GCC 16.1.1/libstdc++ configure, full build, 129 CTest tests | `PASS`; exact approved RapidCheck revision and Draft validator prefix used |
| Clang 22.1.6/libc++ 22.1.6 configure, full build, 129 CTest tests | `PASS`; ABI-compatible approved GoogleTest/RapidCheck prefixes used |
| GCC and Clang Stage 11 ASan+UBSan storage matrices | `PASS`: 21 focused/compatibility/stress tests each; zero findings; LeakSanitizer disabled under managed ptrace |
| GCC Stage 11 TSan storage matrix | `PASS`: 21 tests; zero findings |
| Clang Stage 11 TSan storage matrix | `PASS`: 20 applicable tests; zero findings; only the known global-allocation-hook test is excluded |
| Stage 11 exact codec, golden vectors, independent decoder, and Draft schemas | `PASS`: 4 physical streams, 3 imported envelopes, 2 canonical implementation records; 2 schema positives and 4 negatives |
| Stage 11 large synthetic storage smoke | `PASS`: 200,000 producer and consumer rows; correctness-only output with no timing or performance claim |
| GCC and Clang Stage 10 ASan+UBSan lifecycle matrices | `PASS`: 24 focused tests each; zero findings; LeakSanitizer disabled under managed ptrace |
| GCC and Clang Stage 10 TSan lifecycle matrices | `PASS`: 24 focused tests each; zero findings |
| GCC Release Stage 10 fake-specialization source/symbol/disassembly audit | `PASS_LIMITED`: concrete backend has no vtable; termination access is inline; worker bodies have no allocation/I/O/logging/sleep; injected fixture `sched_yield` remains visible and is not a production relax mapping |
| GCC and Clang Stage 9 ASan+UBSan platform matrices | `PASS`: 12 focused tests each; zero findings; LeakSanitizer disabled under managed ptrace |
| GCC and Clang Stage 9 TSan platform matrices | `PASS`: 12 focused tests each; zero findings |
| Imported Draft 2020-12 fixtures | `PASS`: 7 schemas, 17 positive, 15 negative |
| C++ and independent Python canonical fixtures | `PASS`: 3 shared cases; exact round trip |
| Schedule direct/integrated goldens, schema/codec, boundary, namespace, hash, publication, and outcome-independence checks | `PASS`: 8 focused CTest cases; 8 Python cases; C `decimal`/`_pydecimal`/C++ parity |
| GCC and Clang ASan+UBSan Stage 8 timing matrices | `PASS`: 12 focused tests each; zero findings; LeakSanitizer disabled under managed ptrace |
| GCC and Clang TSan Stage 8 timing matrices | `PASS`: 12 focused tests each; zero findings |
| Queue-focused model/property/stress/phase tests | `PASS`; 14 focused checks plus full regression matrices |
| Workload known-answer/property/boundary/corruption/package/no-allocation tests | `PASS`; 12 focused CTest cases plus full regression matrices |
| clang-format over the full C++ inventory | `PASS` |
| clang-tidy over all 53 configured repository translation units | `PASS`; no user-code diagnostics |
| Protocol/import integrity | `PASS`: 18 artifacts, 4 authoritative hashes, 7 imported and 3 implementation Draft 2020-12 schemas |
| Documentation links, dependency/license inventory, and CI policy | `PASS` |
| Queue provenance/source/license check | `PASS`: two independent no-source-reuse records |
| GNU queue generated-code rules and negative mutant | `PASS`: Binutils 2.46; four operations and mutant reviewed |
| LLVM queue generated-code rules and negative mutant | `PASS`: LLVM 22.1.6; four operations and mutant reviewed |
| GNU and LLVM workload generated-code rules and negative mutant | `PASS`: six operations and mutant reviewed |
| GNU and LLVM timing generated-code rules and negative mutants under GCC and Clang release builds | `PASS`: reader plus ten package operations; six source and three machine mutants rejected |
| GNU and LLVM storage generated-code rules under GCC and Clang release builds | `PASS`: source/binary/rules/disassembly hashes bound; both private append bodies accepted and deliberate call mutant rejected |
| GCC Release unsafe-flag check, metadata, and package generation | `PASS`; 53 compile commands, reproducible dirty-tree fields inspected, Stage 11 library/headers/schemas/docs present |

LeakSanitizer remains explicitly disabled in ASan presets because it cannot run
under the managed ptrace boundary; AddressSanitizer and UndefinedBehaviorSanitizer
remain enabled. All applicable Stage 11 storage tests, all 24 Stage 10
lifecycle tests, all 12 Stage 9 platform tests, and all 12 Stage 8 timing tests
pass both GCC and Clang TSan. The
pre-existing Clang-TSan/global-allocation-hook collision remains a precisely
documented limitation of the separate Stage 6 no-allocation target and is not
reclassified by this focused run. The external self-hosted CI workflow was
inspected but cannot be executed from this workspace. Coverage remains
unconfigured because no coverage gate was accepted. These development-machine
checks establish software correctness only and are not empirical performance
evidence.

## Deferred cross-record blockers

Stage 12 must resolve immutable artifact references and hashes, reconcile
producer/consumer streams by `(run_id, accepted_ordinal)`, prove artifact-derived
counts/timestamps/integrity, and forbid joined output after failed audit. Q10
selects D-031's versioned multi-reason representation, but its amended protocol
snapshot must be imported before final run dispositions can be implemented.

Stage 14 must prove replacement lineage/budget/authority across records, common
block-pool and namespace membership, predecessor hashes, access chronology,
authority segregation, and technical sealing. A structurally and locally valid
record is not claimed to satisfy either later gate.

## License and dependency state

ADR-0021 records no repository license grant. There is no `LICENSE` file. The
package carries `docs/NO_LICENSE_GRANT.md`; all 22 third-party build/runtime/test
inputs retain their separately recorded sources, version rules, hashes where
applicable, licenses, purposes, and scopes. Stage 6 adds OpenSSL 3 and its
runtime closure to that inventory. Stage 5 closure records GNU Binutils as the
already-required primary disassembly tool; it added no queue runtime dependency
and no third-party queue source. The current FastFlow project is
recorded only as an official-project search result; exact 2010 artifact/license
mapping remains unresolved and no implementation text was used.

## Immediate gate

Stage 11's local software slice is complete under accepted ADR-0032/0033. The
raw streams and immutable publication boundary are ready for reconciliation,
and D-031's representation direction is now accepted. The protocol and
statistical owner accepted the
[D-031/Q10 decision bundle](docs/STAGE12_D031_DECISION_BUNDLE.md) on
2026-08-21, selecting a versioned exhaustive blocker array with a non-priority
multiple summary. **The exact next safe action is to publish or supply that
versioned amended protocol snapshot, then import and hash-verify it.** Stage 12
final run-disposition implementation remains blocked until that import.
Measurement, pilot activity, and confirmatory execution remain prohibited.
Static inventory and development-host smoke are not selected-pair, address
residency, hardware-state, restoration, or dynamic clock evidence; those exact
stand gates remain open through Phase 16.
