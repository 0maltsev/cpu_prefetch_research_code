# Repository Status

Protocol snapshot: **`2.0.0-pre.1`**

Repository state: **`STAGE_8_SOFTWARE_COMPLETE`**

Readiness verdict: **`STAGE9_READY_MEASUREMENT_PROHIBITED_CLOCK_PAIR_PENDING`**

## Readiness by area

| Area | State | Evidence or blocker |
|---|---|---|
| Stage 1 import/traceability | `COMPLETE_REVERIFIED` | The Stage 8 closure freshly passed all 18 manifest sizes/SHA-256 values, exact inventory, four authoritative hashes, JSON parsing, and Draft 2020-12 meta-schema validation for all seven schemas. |
| Stage 2 implementation-decision freeze | `COMPLETE`; Q7 accepted | ADR-0001 through ADR-0030 are accepted. Q7 freezes the final D-009 bundle. Later implementation evidence and platform/pilot selections remain open at their recorded gates. |
| Stage 3 build/CI foundation | `COMPLETE_LOCAL` | ADR-0022, constrained offline inputs, dual compiler/library presets, lint, sanitizer, metadata, package, and pinned self-hosted CI foundations remain passing. |
| Stage 4 protocol/configuration model | `COMPLETE_LOCAL` | ADR-0023, typed C++20 records for all seven schema families, strict loading, immutable configuration, record-local semantic rules, exact `JCS-I64-v1`, and explicit cross-record interfaces are implemented and pass the recorded matrix. |
| Queue implementation | `COMPLETE_LOCAL` | ADR-0024 fixes distinct independent ring and linked/recycler adapters, exact release/acquire, fixed-arena refinement, source-hashed provenance, layout/lock-free probes, and correctness suites. GNU Binutils 2.46 and LLVM 22.1.6 release disassembly/mutant checks pass and both instruction views were reviewed. |
| Workload construction | `COMPLETE_LOCAL` | ADR-0025 through ADR-0028 fix the deterministic stream, unbiased permutations, payload/mixer/integrity grammars, event/node layouts, and five package mechanisms. Known-answer/property/corruption/no-allocation and dual-disassembler checks pass. |
| Schedule generation | `COMPLETE_LOCAL` | ADR-0029's offline Decimal80/Philox suite, external u64be artifact, imported envelope, derivation record, immutable C++ decoder, namespace/common-family validation, and failure/golden/corruption matrices pass. |
| Timing system | `COMPLETE_SOFTWARE`; platform gate open | `cpu_prefetch_timing` implements D-009's selected reader, exact conversion, producer/consumer boundary capture, offline equations, qualification evaluators, no-correction diagnostics, and dual-disassembler/mutant audit. Development-host evidence is engineering-only. No explicit eligible pair, full dynamic qualification, or before-block evidence exists. |
| Measurement system | `NOT_IMPLEMENTED` | No queue-driven experiment loop, raw physical codec, controller, or platform mutation exists. Stage 8 components do not authorize timing comparisons; remaining scientific/platform selections stay open at their assigned gates. |
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

## Fresh local verification

| Check | Result |
|---|---|
| GCC 16.1.1/libstdc++ clean configure, build, 72 CTest tests | `PASS`; exact approved RapidCheck revision and Draft validator prefix used |
| Clang 22.1.6/libc++ 22.1.6 clean configure, build, 72 CTest tests | `PASS`; ABI-compatible approved GoogleTest/RapidCheck prefix used |
| Imported Draft 2020-12 fixtures | `PASS`: 7 schemas, 17 positive, 15 negative |
| C++ and independent Python canonical fixtures | `PASS`: 3 shared cases; exact round trip |
| Schedule direct/integrated goldens, schema/codec, boundary, namespace, hash, publication, and outcome-independence checks | `PASS`: 8 focused CTest cases; 8 Python cases; C `decimal`/`_pydecimal`/C++ parity |
| GCC and Clang ASan+UBSan Stage 8 timing matrices | `PASS`: 12 focused tests each; zero findings; LeakSanitizer disabled under managed ptrace |
| GCC and Clang TSan Stage 8 timing matrices | `PASS`: 12 focused tests each; zero findings |
| Queue-focused model/property/stress/phase tests | `PASS`; 14 focused checks plus full regression matrices |
| Workload known-answer/property/boundary/corruption/package/no-allocation tests | `PASS`; 12 focused CTest cases plus full regression matrices |
| clang-format and clang-tidy over 34 translation units | `PASS`; no user-code diagnostics |
| Protocol/import integrity | `PASS`: 18 artifacts, 4 authoritative hashes, 7 schemas |
| Documentation links, dependency/license inventory, and CI policy | `PASS` |
| Queue provenance/source/license check | `PASS`: two independent no-source-reuse records |
| GNU queue generated-code rules and negative mutant | `PASS`: Binutils 2.46; four operations and mutant reviewed |
| LLVM queue generated-code rules and negative mutant | `PASS`: LLVM 22.1.6; four operations and mutant reviewed |
| GNU and LLVM workload generated-code rules and negative mutant | `PASS`: six operations and mutant reviewed |
| GNU and LLVM timing generated-code rules and negative mutants under GCC and Clang release builds | `PASS`: reader plus ten package operations; six source and three machine mutants rejected |
| GCC Release unsafe-flag check, metadata, and package generation | `PASS`; 25 compile commands, reproducible dirty-tree fields inspected, Stage 8 timing library/headers/docs present |

LeakSanitizer remains explicitly disabled in ASan presets because it cannot run
under the managed ptrace boundary; AddressSanitizer and UndefinedBehaviorSanitizer
remain enabled. All 12 Stage 8 timing tests pass both GCC and Clang TSan. The
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
counts/timestamps/integrity, forbid joined output after failed audit, and resolve
D-031's protocol-level precedence/representation for simultaneous blocker
reasons before accepting final run dispositions.

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

Stage 8's software and generated-code slice is complete under accepted
D-009/ADR-0030. The exact next safe activity is **Stage 9 platform control and
explicit selected-pair qualification**. Measurement, pilot activity, and
confirmatory execution remain prohibited until their applicable lifecycle
gates pass; static stand inventory and development-host smoke results are not
dynamic clock or worker-pair evidence.
