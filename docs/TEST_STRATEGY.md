# Test Strategy

## Purpose

This is the verification plan for a future complete Stage A implementation. Stage 4
provides the typed protocol/configuration model and validation layer. Stage 5
now provides independently authored ring and linked/recycler queue cores and
correctness tests. Stage 6 provides deterministic workload construction and the
five package mechanisms. Stage 7 provides offline deterministic schedule
generation and immutable decoding. Stage 8 provides the accepted clock reader,
timestamp boundaries, offline interval derivation, and qualification
evaluators. Stage 9 provides read-only Linux inventory, typed platform
request/capability/control evidence, dry-run, independent verification,
failure-safe restoration, and platform manifests. Stage 10 provides the
fake-backed lifecycle graph, reset evidence, start/termination/drain
concurrency, and partial-failure rules. Stage 11 provides bounded private raw
writers, the accepted codec, storage/integrity records, checked budgets, and a
local crash-aware append-only store. Stage 12 provides exact offline
reconciliation, run-level semantic relationships, and independent D-031 gate
evaluation; no authorized scientific run, privileged stand actuator, or
eligible-pair qualification exists. ADR-0009 through ADR-0011, ADR-0017, and
ADR-0022 through ADR-0034 fix the
framework/toolchain/sanitizer/model/queue/workload/schedule/clock/lifecycle/
storage-decision baseline and commands. ADR-0030's software and dual-tool
generated-code slice and ADR-0031's lifecycle/concurrency slice pass;
ADR-0032/0033 are accepted contracts whose Stage 11 local software tests pass.
Explicit selected-pair and stand qualification evidence remains Phase 9/16
work.
Tests establish software correctness, protocol
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
and rule IDs. Stage 12 implements immutable run-level reference/hash, exact
cross-stream reconciliation, and D-031 exhaustive blocker rules. Append-only
block/replacement ancestry, authority segregation, access chronology, and
block budget proofs remain Phase 14 responsibilities and are not reported as
passing.

### 4. Unit tests

Planned pure or bounded units include identity construction, checked integer/tick arithmetic, exact rational rates, half-open horizon inclusion, cyclic index lookup, checksum primitives, interval equations, inverse-ECDF order statistics, count classification, status transitions, capacity inequalities, `d1`/`d2` formulas, and duration/storage formulas.

Boundary cases include zero offered rows where permitted, maximum representable tick/count, overflow rejection, `pN` at an integer boundary, repeated quantile values, `N_eff` exactly at each threshold, `d2` cap collapse, and replacement budget exhaustion.

Stage 6 status: exact capacity inequalities, `d1`, externally supplied `d2`
validation, cyclic lookup, strong identity types, record alignment, and
content/order/delta SHA-256 inputs have unit coverage. Real cache facts,
qualifying seeds, and calibrated `d2` remain external evidence.

Stage 7 status: exact reduced rates, zero/minimal/boundary horizons, explicit
origin, half-open exclusion, retained ties, unsigned overflow, draw exhaustion,
malformed byte/count/order/unit/encoding/suite/hash cases, and append-only
publication rollback have unit coverage.

Stage 11 status: zero-row, minimal and exact-full streams, sticky overflow,
checked arithmetic overflow, `N_acc<=N_sched`, `N_eff<=N_acc`, tail
thresholds, page rounding, metadata/reserve, byte/row counts, duplicate IDs,
partial writes, readback mismatches, and recovery-only state have unit coverage.

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

Stage 6 status: RapidCheck verifies deterministic event/node permutations are
bijections for generated power-of-two capacities; known-answer fixtures pin the
Philox/HMAC stream, Fisher-Yates order, mixer, and three checksum grammars.

Stage 7 status: a deterministic configuration matrix covers byte-for-byte
reproduction, exact ordering/horizon properties, C `decimal` versus
`_pydecimal` parity, imported and implementation-schema conformance, canonical
round trips, role namespace separation, exact matched-family sharing, and an
API test proving queue outcomes cannot enter generation.

Stage 11 status: exact producer/consumer/compatibility-only joined goldens are
checked independently by C++ and Python; strict decoding maps bytes back to
logical rows without loss and rejects reorder, prefix/padding/flag, version,
endianness, timestamp, count, size, and checksum corruption.

### 6. Queue linearization and refinement tests

Both queues require histories checked against an abstract bounded FIFO with single producer/single consumer try semantics. Tests must expose invocation, protocol-defined linearization, and response points and cover empty, full, wrap, delayed workers, and repeated reuse.

The linked package additionally requires a written refinement argument and executable history checks for immediate full when the recycler is empty, exclusive node states, acyclic/reachable chain, no recycle while reachable, FIFO recycler transfer, and repeated `C+1` cycles. Suspension at relevant phases must not violate the stated wait-free/terminating try-operation boundary.

Stage 5 status: implemented for both direct adapters. Deterministic tests cover
empty/full/capacity/FIFO, 200,000 sequential ring reuse operations, exact
linked `C+1` node cycles, 10,000-step abstract-model histories, generated
RapidCheck histories, and suspension immediately before ring publication/reuse
and linked publication/recycler return. The written memory-order,
linearization, ownership, progress, and fixed-arena refinement argument is in
`docs/QUEUE_CORRECTNESS.md`.

### 7. Concurrent stress tests

- Long fixed-seed producer/consumer sequences with independent delay injection.
- Repeated full/empty transitions and ring wrap.
- Linked FIFO/recycler cycling sufficient to exercise every node many times.
- Cross-check first, internal, and final sequences; counts; node ownership; record contents; and checksums.
- Stress both slow-producer and slow-consumer cases and abrupt controlled termination/failure recording.

Acceptance durations, repetition counts, machines, and seeds are frozen before pilot. A retry after a flaky failure does not convert it to a pass.

Stage 5 status: the repository stress target transfers fixed sequences under
both slow-producer and slow-consumer yield patterns, validates exact pointer and
payload order, and audits quiescent ring occupancy and linked node ownership.
A separate history issues exactly one enqueue attempt per logical arrival,
retains accepted/full outcomes, drains, and compares only the accepted
sequence. Correctness-only complete-transfer loops may retry outside the
adapter solely to force repeated slot/node reuse; no retry exists in an
operation or production driver.

### 8. Sanitizers and language/runtime checks

- AddressSanitizer for out-of-bounds/use-after-free and buffer errors.
- UndefinedBehaviorSanitizer for arithmetic, alignment, and language undefined behavior.
- ThreadSanitizer where compatible with the selected atomics, compiler, and target; incompatibility must be documented and compensated with independent deterministic concurrency evidence rather than silently skipped.
- Compiler/static diagnostics appropriate to the selected language at an accepted strictness level.
- Runtime/compile-time proof that required atomics are lock-free on the eligible platform.

Acceptance is zero unresolved findings. A suppression is not a pass unless a named owner records the exact diagnostic, smallest scope, tool defect or deliberate mechanism, compensating evidence, and expiry/review gate. Unsupported TSan combinations are recorded as unavailable and require both supported-toolchain deterministic history/refinement evidence plus the approved compensating plan; they are never silently skipped.

Sanitizer builds verify correctness only and are never used for performance claims.

Stage 11 status: the storage-labelled matrix passes GCC and Clang ASan/UBSan
and TSan without a storage suppression or finding. The dedicated hot-writer
allocation hook remains intentionally unavailable only in the pre-existing
Clang-TSan/global-allocator collision; it runs under development, both
ASan/UBSan matrices, and GCC TSan. The fixed two-writer concurrency and large
synthetic storage tests run in all applicable matrices.

Stage 7 status: GCC/libstdc++ and Clang/libc++ full unit/property/stress suites,
including workload construction, package target, and schedule tests, pass
ASan/UBSan and TSan without suppression or finding. LeakSanitizer
remains separately disabled by the accepted managed-ptrace limitation. The
runtime pointer-atomic checks pass on the development host and must be repeated
on the eligible stand. The single-thread global-`operator new` interception test
is intentionally absent only from the Clang TSan build because that runtime
defines the same allocator symbols; it runs in both development and ASan/UBSan
matrices and under GCC TSan, while every other configured test runs under Clang
TSan.

### 9. Deterministic schedule golden tests

Golden vectors bind RNG version, master/derived seed IDs, namespace, exact rational rate, encoding, integer time unit, origin, horizon, overflow behavior, decoded deadlines, and checksums. Cross-build and cross-platform generation must be bit-identical for supported targets. Warm-up, pilot, calibration, confirmatory roles, diagnostics, and optional stages must never collide.

Stage 7 status: the accepted direct six-draw vector and 104-row integrated
vector pass under Python 3.14 C `decimal` and `_pydecimal`; C++ independently
matches the Philox key/draws, external artifact, first/last deadlines, and
artifact/decoded/envelope hashes. The derivation record binds and hashes the
exact Python, decimal, and libmpdec versions. Concrete scientific seeds and
namespace values remain later freeze inputs.

### 10. Timing tests

- Implement the exact `CLOCK-QUAL-LMRV1` limits and failure rules from the
  accepted D-009 bundle; no local threshold may replace them.
- Tick reads never regress on either selected core.
- Cross-core offset, drift, resolution, conversion, serialization, and exact boundary-read overhead meet frozen limits.
- Compiler/generated-code inspection proves timestamp reads stay at defined boundaries without strengthening queue synchronization.
- Conversion fixtures prove exact nanosecond-to-picosecond arithmetic and
  overflow rejection; raw timestamps are primary and any overhead correction
  is rejected by the accepted no-correction policy.
- Fault injection catches regression, excessive skew/drift, invalid conversion, and moved/missing boundaries.

Stage 8 software status: Q7 accepted D-009/ADR-0030. Checked conversion,
absolute/raw sample retention, fake and real readers, every producer/consumer
boundary, `FULL`/empty/failure handling, cross-thread publication, exact
offline equations, static/per-core/bidirectional qualification math,
uncorrected overhead diagnostics, and GNU+LLVM generated-code checks with all
six required source mutants pass locally. Short synthetic inputs are marked
ineligible by exact sample-count fields. The 10,000-read development smoke is
engineering evidence only. An explicit pair, exact full-count traced vDSO and
three-window evidence, affinity/source identity, and before-block repetition
remain Phase 9/16 gates.

### 10a. Platform inventory and control tests

- Parse CPU lists and CPU/core/package/SMT/NUMA/cache/PCI topology with missing,
  malformed, duplicate, and inconsistent evidence negatives.
- Accept only explicit Stage A near/far non-SMT placement, producer-home shared
  data, worker-local private buffers, and the inventoried base-page size.
- Reject unavailable/mapping-unresolved controls, missing authority,
  actuation-as-readback, impossible/offline CPUs, sibling/core confusion, NUMA
  mismatch, interleave/consumer-local/replicated/migrated placement, and huge
  page treatments.
- Prove dry-run invokes no actuator. Inject partial apply, missing pre-state,
  permission failure, reverse restoration, and restoration failure.
- Make apply/readback disagree; remove mandatory readback; change snapshot or
  epoch; change verification mechanism; require ineligibility with exact error
  evidence.
- Emit deterministic canonical complete and partial manifests, validate binary
  and library provenance completeness, and load the exact projection through
  the imported platform model/schema contract.

Stage 9 software status: the platform-labelled GCC tests cover these paths and
a safe read-only development-host inventory smoke. ASan/UBSan and TSan must run
the same test set. None establishes stand eligibility. The exact selected
pairs, thread/address-specific before/during/after residency, approved actuator
and authority, vendor HW-prefetch mapping/readback/probes, successful
restoration exercise, and full Stage 8 selected-pair qualification remain
stand/Phase 16 blockers for measurement.

### 11. Record, checksum, and corruption tests

- Assert one measured-line record size, payload alignment, immutable fields, and package-independent arena/order.
- Known-answer tests for consumer mixing, rolling checksum, content checksum, index checksum, delta checksum, canonical serialization, and artifact SHA-256.
- Flip, truncate, duplicate, reorder, or replace rows/bytes and require the correct schema, semantic, join, or integrity failure.
- Verify pre/post record-content equality and generated code containing expected loads/private update with no record write.

Stage 6 status: shared C++/Python `JCS-I64-v1` fixtures cover
signed/unsigned limits, `2^53` boundaries, RFC 8785 binary64 examples, UTF-16
ordering, escaping, Unicode, and negative zero. RapidCheck exercises generated
`uint64_t` exact serialization. Workload tests pin the accepted consumer mixer,
pre/post record content, ordered-index, and signed closure-delta SHA-256 inputs;
flip/index/payload/padding and unexpected-pointer cases fail as required. A
10,000-cycle allocation hook covers lookup, record action, and all five package
operations after preparation.

Stage 11 status: accepted producer/consumer/joined SHA-256 goldens, physical
round trips, final rolling/pre/post/order/delta algorithm identities, imported
raw envelopes, copy ledgers, and phase/integrity canonical documents are
covered. Fault tests flip bytes, alter counts/hashes/ordering, inject partial
writes and finalization failure, restart in recovery-only mode, attempt
overwrite/duplicate IDs, and prove missing streams are not fabricated.

### 12. Reconciliation fault injection

Start from independently built producer and consumer streams, then inject count mismatch, wrong `run_id`, wrong ordinal, unexpected pointer/index, duplicate, loss, reorder, invalid timestamp, broken equation, row/envelope disagreement, wrong source hash, and partial/truncated artifact. Every attempted join emits an audit. No failure may emit successful joined data or latency.

Stage 12 status: deterministic unit and RapidCheck-generated histories cover
empty and repeating-index success, first/internal/last loss, duplicate,
reorder, malformed producer/consumer ordinals, unexpected Stage 6 mapping and
consumer index, run identity, count, and timestamp corruption. Every failed
result has classified issues and an empty joined vector. Audit tests enforce
passed-with-joined versus failed-without-joined and exact regenerated audit
bytes. The cross-record integration fixture rejects missing typed envelopes,
duplicate identities, mixed versions, wrong immutable hashes/source lineage,
and accepts a pre-run failure with schedules and failure evidence but no
fabricated raw or joined streams. Status tests cover exact count identities,
invalid-without-failure rejection, valid `FULL`, valid low `N_eff`, pending
Stage 14 evidence, and all five simultaneous blockers in canonical order. The
same label is required under development, ASan/UBSan, and TSan presets; all
inputs are synthetic.

### 13. Lifecycle transition tests

Cover every lifecycle state and independent join status. Verify early failure without fabricated artifacts, partial measurement/drain artifacts, failed join with audit only, complete valid Stage A obligations, valid `FULL` plus zero-loss failure, valid low `N_eff` plus effective-tail failure, invalid run plus failure record, and block-incomplete consequences.

Stage 10 status: the pure transition graph enumerates all 256 internal
state-pairs and tests every accepted edge and phase-specific failure
projection. Transition metadata, nondecreasing timestamps, actual/absent
artifact consequences, immutable failure, recovery-outside-measurement, and
`FULL`/low-`N_eff` non-failure behavior fail closed. Preparation/warm-up tests
require separate namespaces, complete preallocation/verification, no ambiguous
continuation, and stop/drain/barrier evidence. Ring and linked reset fixtures
cover exact origin plus every remap/retouch/allocation/count/checksum fault.

Concurrency tests exercise delayed start, one published origin, u32
release/acquire payload visibility, producer completion before backlog drain,
empty schedules, exactly one call for every `FULL`, partial producer failure,
long legitimate deadline gaps, start-clock cancellation, drain backend
failure, backlog drain beyond the former cap, and 100 deterministic varied-
scheduling histories. The fake backend uses fixed
storage; input schedules and thread setup finish before the origin. Explicit
test limits and host `yield` scheduling are fixture behavior, not production
relax or start/external-watchdog selections. ADR-0048 prohibits worker-loop
poll-count expiry. The same label must pass ASan/UBSan and TSan.

Q15-P0 hardware-prefetch tests cover exact family/model/CPU/MSR/mask mapping,
H0 preservation, H1 unknown-bit preservation, H0/H1 collapse, complete-value
independent readback, regular/pointer probes, reverse exact restoration,
partial apply, restoration quarantine, and independent-backend enforcement.
All use fake state. The schema suite adds two positive and six negative
synthetic evidence records and performs no MSR access.

Q15-S1 adds fixed Linux-adapter tests behind a fake file-operation boundary.
They require only `/dev/cpu/{0,1,26}/msr`, offset 0x1A4, exact access flags and
64-bit transfers; reject every other CPU, stale/broad transitions, H0/H1
collapse, and open/read/write/close faults; and prove one transition has no
hidden retry or self-readback. CLI tests execute only self-test, scope, and an
invalid-authorization negative. Split-schema tests cover 2 prospective
positive shapes, 10 authority negatives, and two blocked preparation records.
The pure bundle-profile checker covers one accepted no-authority shape and 24
negative mutations spanning every authority flag, clean-source identity,
required/forbidden binaries and libraries, mapping/tool identity, and exact
probe-contract ID/path/hash binding. The D-052 contract checker validates one
frozen document and rejects 18 scope, PMU, privilege, multiplexing, traversal,
classification, collector, artifact, and authority mutations. No test
opens an MSR device, seals a release bundle, or accesses the stand.

Q15-S2 adds seven D-053 C++ tests that independently pin the HMAC-derived
Philox key, eight-line order, complete-buffer SHA-256, alignment/zero-fill,
single-cycle bijection/closure, malformed/corrupt cycles, exact counted loads,
pre/post integrity, multiplex/fault/H1 failure, and both pointer-H0
classifications. The machine-readable profile checker rejects ten seed,
integrity, encoding, source-hash, and authority mutations. The release checker
requires both GNU and accepted LLVM disassembly to expose one static demand
load and no call/prefetch/fence/system instruction in each counted body; an
extra-load mutant and a prefetch mutant must remain detectable. Applicable
tests run under ASan/UBSan and TSan. No test opens a PMU or accesses the stand.

### 13a. Calibration framework tests

Stage 13 tests are synthetic/fake correctness evidence only. The C++ suite
must cover exact rational reduction/comparison/overflow, the complete 60-cell
service product, prospective plan completion, retained invalid runs, the
58/59 validity boundary, no top-up, configuration equality, and exact
`mu_cell`/`mu_ref`/candidate minima. Fake-clock ring tests bracket the exact
slot acquire, retain FULL/empty demand observations, derive issue intervals
only from advancing operations, and cover all six contexts, both hardware
states/workers, inverse-ECDF ranks, conservative max/min, line rounding,
quarter cap, common producer/consumer distance, cap collapse, H0/H1 context
drift, trace overflow classification, and malformed-valid-series rejection.

The offline suite must cover direct guard160 Decimal vectors, a precision-240
reference pass, unequal weights, finite all-zero positive upper bounds,
clamp-to-one, zero-offered rejection, exact 180-cell exposure, honest partial
`NOT_EVALUATED` records, mandatory confidence/threshold/profile fields, the
complete common scale ladder, and forbidden confirmatory outcome access. All
five implementation schemas receive Draft 2020-12 positive/negative fixtures.
Canonical round trip, UTF-16 property order, signed/unsigned 64-bit boundaries,
zero-self SHA-256, attempted overwrite, and material-change invalidation are
mandatory. No test fixture may be published as a platform calibration output.

Stage 13 status: the `calibration` CTest label and `calibration-check` target
implement this matrix. Applicable ASan/UBSan and TSan presets must pass the C++
evaluator and acquire-observer tests; Python/schema checks run under the pinned
offline Python/jsonschema prefix.

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

Stage 14 status: the `orchestration` CTest label and `orchestration-check`
target implement Sections 15 through 17 with synthetic inputs only. Exact
factor/ordinal/whole-plot and seed-sharing mutations fail; a 32-key property
sweep and pool test cover deterministic reproduction, unique role subspaces,
and H0/H1-first counterbalance. Fixed-family tests pin 7 H1, 20 H2, 270
training, 540 pre-selection validation, and 54 post-selection comparisons,
including formula/minimum/ceiling and outcome-input rejection. Access tests
cover exact chronology and affected block sets, six contexts, the complete
`TRAINING_OPEN` family/count/input freeze, independent precision-count binding,
role/namespace boundaries, predecessor hashes, authority
segregation/approved overlap, early/wrong-role access, append-only amendments,
selection-payload/input-hash corruption, outcome-leak rejection, and branched
lineage.
Replacement tests require retained invalid-run/failure/authorization/budget
links, new complete role-preserving plans, reject valid `FULL` and low-tail
runs, reject role/cell/branch repair, and return unresolved at budget
exhaustion. Imported Draft 2020-12 fixtures add nine positive and ten negative
block/freeze shapes; path-shaped identity remains an intentional semantic
negative. The same C++ label must pass GCC/Clang ASan/UBSan and TSan presets.
No fixture is an authorized block or scientific outcome.

### 18. Offline-analysis contract tests

The `analysis` CTest label and `analysis-check` target exercise the accepted
synthetic-only Stage 15 profile. Tests independently pin the inverse-ECDF rank
rule, p50/p90/p99/p999 and conditional p9999 behavior, the 40-column balanced
Stage A model, all seven H1 and twenty H2 contrasts, all 270 H3 training and
540 pre-selection validation comparisons, and the reported 54
selected-minus-alternative comparisons. Known-null and constructively shifted
complete-block fixtures verify sidedness, sample covariance, block resampling,
studentization, empirical 95th max-T critical values, and the fixed H3 tie
order. The prospective-precision test consumes exact frozen family-width
curves and rejects malformed or outcome-derived substitutes.

The complete synthetic end-to-end fixture contains 12 training and 8
validation blocks, exactly 180 cells per active block, immutable content
hashes, Stage 12 reconciliation evidence, and Stage 14 access grants. Its
expected H1/H2 signs, six H3 selections, 54 validation contrasts, diagnostic
separation, and canonical report hash are asserted. A same-seed rerun must be
byte-identical. Additional fixtures exercise ties, low-tail censoring, valid
`FULL`, an incomplete active block, a retained invalid original plus complete
replacement, replacement-budget exhaustion, sealed validation, mixed
protocol versions, bad hashes, invalid joins, missing cells, and attempted
cell repair. Blocked validity gates are retained as non-inferential outputs;
prohibited or malformed evidence is rejected rather than filtered.

Only `STAGE-A-OFFLINE-ANALYSIS-SYNTHETIC-v1` input is admitted in Stage 15.
Every generated machine report must say `SYNTHETIC_KNOWN_ANSWER_ONLY`; the
human report must say `SYNTHETIC FIXTURE ONLY` and that it contains no
empirical findings. Both list software/config/input/output identities and preserve primary versus
sensitivity separation. The production artifact adapter, custody exercise,
and exact measured-release requalification remain Stage 16 work. The analysis
label must pass both supported compiler/library matrices and every applicable
ASan/UBSan and TSan preset.

### 19. Generated-code acceptance

For each package/build, inspect and hash the generated boundaries for queue publication/observation, prefetch site/target/form/distance, wait relaxation, termination flag, immutable record loads, private checksum update, timestamp boundaries, static specialization, and absence of virtual dispatch, treatment branch, allocation, I/O, logging, or unexpected calls. Source, object, executable, compiler, flags, standard-library, linker, disassembler, rule-set, and report hashes travel together. The test must include negative fixtures or mutated builds proving the checks detect missing/moved operations.

Stage 6 status: the queue probe still passes four direct adapter symbols. The
workload probe adds the consumer action and R1/R2 producer/consumer plus L1
consumer sites. GNU Binutils 2.46 and LLVM 22.1.6 show the two immutable record
loads, fixed branch-free mixer, and exact target-before-demand ordering with no
unexpected call, record store, `lock`, `xchg`, or `mfence`; both reject the
deliberate call mutant. Q13 now fixes one x86 `PAUSE`; its release probe must
show exactly one instruction in GNU and LLVM views and reject the two-PAUSE/
`sched_yield` mutant. Platform prefetch instructions and the package-specific
combined worker remain later generated-code gates. Stage 11
adds two fixed append bodies: GNU Binutils 2.46 and LLVM 22.1.6 both verify no
unexpected call, lock, memory exchange/fence, or syscall and both reject the
deliberate storage call mutant. Stage 10 source/static analysis fixes u32
release/acquire termination and compile-time backend binding but does not
mistake a fake specialization for the measured-release audit.

### 20. Clean-environment build and verification

From a documented clean environment with network access disabled, recreate dependencies, build artifacts, fixtures, validator outputs, and generated-code reports solely from tracked inputs and recorded versions. Compare source/build/protocol/dependency hashes and licenses and run the complete non-performance test suite. Stage 3 provides the local/CI commands in `README.md`; later phases extend the same presets and checks rather than inventing separate entry points.

### 21. Synthetic end-to-end dry run

Use a small explicitly synthetic fixture namespace to exercise planning, schedules, lifecycle, private streams, sealing, join, manifests, failure injection, status gates, and derived provenance. It must not be called a pilot, use confirmatory namespaces, tune treatment parameters, or support a performance claim. Its acceptance is structural correctness only.

### 22. Dependency and provenance tests

- Fail configure/verification for an unrecorded dependency, missing immutable source hash, unknown license, network fetch, or incompatible license decision.
- Bind queue implementation files to the accepted provenance/mode record and paper-to-source semantic map.
- Verify that independent queue implementation imports no third-party queue source or mechanically derived code.
- Verify every generated source/table has a tracked generator, inputs, version, deterministic regeneration command, output hash, review classification, and stale-output check.

### 23. Plane and privilege isolation tests

- Prove the worker call graph cannot reach config/schema parsers, general allocators, filesystem/network/console APIs, compression, reconciliation, or analysis.
- Run negative mutants that add each prohibited call and require rejection.
- Verify the measurement process has no platform-control or validation-custody privilege.
- Exercise denied/partial platform operations, independent readback mismatch, rollback failure, inaccessible validation data, and crash/restart at every artifact handoff.
- Confirm requested-state fields never populate verified-state fields without independent evidence.

### 24. Stage 16 independent verification and bundle proof

Stage 16 starts from clean preset build directories and a recorded
pre-provisioned dependency prefix. GCC/libstdc++ and Clang/libc++ must each
configure, build, and pass the complete development and release CTest inventory.
Both ASan/UBSan and both applicable TSan matrices must pass; the established
managed-ptrace LeakSanitizer limitation and Clang TSan allocation-interceptor
collision are reported, never relabelled as coverage.

Run the protocol/schema/canonical, schedule golden, queue provenance/stress,
storage format/schema/large-stream, calibration, reconciliation, orchestration,
analysis, formatting, static-analysis, dependency/license, pinned-CI, and
release-policy checks. The focused synthetic disposition set must include
success, valid `FULL`, low `N_eff`, partial lifecycle and storage failure,
failed exact join, exact 180-cell generation, seal chronology, and complete
replacement/budget refusal. None is empirical evidence.

Review queue, workload, timestamp, and bounded-writer component bodies in
source and with both accepted disassemblers. Each strict checker must reject
its deliberate mutant. A missing production executable or final combined
worker is recorded as a pilot blocker; component results cannot be promoted to
an integrated-worker pass.

Build `STAGE16-STAND-BUNDLE-v1` twice into distinct append-only output
directories and require identical outer SHA-256 values. Verify the external
sidecar, extract into a new directory, run the internal complete-file inventory
and hash verifier, then run `cpu_prefetch_smoke` and
`cpu_prefetch_preflight --self-test`. Inspect the manifest, source archive,
version metadata, compile commands, runtime dependency record, schemas,
protocol, null-valued example, no-license notice, dependency inventory, SPDX
SBOM, validators, readiness report, and runbook. The bundle must explicitly
deny pilot and confirmatory authority and contain no frozen platform value.

### 25. Q13 runner-entry admission and relax checks

The runner suite must prove exact `(0,1)` near and `(0,26)` far mapping, all
five and only five static packages, and one controller-side dispatch before
the generic measurement executor. The capture backend package and template
package must agree at compile time. There is no runtime package selection in a
worker operation.

Admission negatives cover every missing evidence kind, duplicate kind and
artifact ID, unknown field/enum, unaccepted profile/relax/pair/package,
source/binary/stand/binding drift, dirty source, zero limit, stale binding,
mutable/ineligible evidence, absent/non-regular/symlink input, and byte/hash
disagreement. Only the combined trust-anchor plus file-hash path may construct
the ticket; field validation alone never arms a runner. The CLI self-test must
state `execution=NOT_AUTHORIZED` and expose no run command.

The release `runner-relax-codegen-check` uses both accepted disassemblers,
requires exactly one `PAUSE`, forbids calls/fences/syscalls in the relax body,
and proves rejection with a two-`PAUSE`/scheduler-call mutant. This is not the
still-required full affined combined-worker audit.

### 26. Q14/Q15-P0 local release, qualification, and authority checks

Owner-preparation tests require each bind/readback/actual-CPU check to run once
on its worker before the barrier and before private-stream first touch. Any
producer or consumer mismatch must cancel the barrier, report a pre-run worker-
preparation failure, make zero attempts, and retain partial evidence. Fakes are
mandatory for repository verification; no test may change host affinity.

Qualification builders use synthetic inputs with exact clock sample/window/
exchange counts, atomic widths/alignment/lock-free flags, actual CPU/migration
counts, and three-region before/during/after residency evidence. Positive
artifacts must be canonical and byte-stable. Short counts, syscalls,
migrations, wrong/unavailable pages, binding mismatch, malformed hashes, or
missing sources must remain invalid or ineligible.

The future authorization schema must accept only exact stand qualification or
one of four dependency-ready phases. Negatives cover omnibus/wildcard/latest/
unresolved targets, overlapping authority roles, invalid expiry, identical
durability domains, scientific inputs in Q15, missing predecessors, run-count
drift, confirmatory namespaces, and enabled confirmatory/retry/top-up/repair
permissions. Passing the validator never issues an authority.

Q15-P0 adds runner/admission v3 regression tests proving that legitimate idle
and drain work cannot expire by poll count. It also adds the model-restricted
hardware-prefetch plan/transaction and evidence-schema tests described above.
No test opens `/dev/cpu/*/msr`, changes affinity, accesses the candidate stand,
or performs dynamic qualification.

Both accepted disassemblers recursively inspect all ten static producer and
consumer operation shapes. D-047 requires exact empty, `PREFETCHW`, or
`PREFETCHT0` vectors by package/role and rejects wrong-write, wrong-read,
duplicate-read, and allocation/scheduler mutants. Source checks bind the ring
slot target calculations and the linked acquire/prefetch/event-demand order.
Only a strict `PASS` report carrying
`X86-64-PREFETCHW-PREFETCHT0-v1` can pass the candidate gate. The candidate
creator separately rejects dirty source, missing/non-PASS reports, overwrite,
authority-bearing manifests, or omitted runner/qualification artifacts. No
pilot candidate is eligible until all checks pass from a clean exact revision.

### 27. Q15-S3 dynamic-component software checks

All Q15-S3 verification is repository-local. Platform and perf fakes must
prove the exact raw request, one reset/enable/traversal/disable/read/close
lifecycle, no retry/fallback, mapping → bind → no-THP → affinity/readback →
first-touch order, exhaustive residency snapshots, conservative thread-fault
bracketing, raw clock ordering, and every partial failure. A global allocation
hook must show zero allocation in both counter-enabled region variants.

Session tests cover the only legal H0 → seal → H1 → restore → finalize order,
literal pointer and content identity, complete source/profile/platform hashes,
distinct peer credentials, sealed-Q15-R and later-Q15-W binding, exact complete
values, expiry, disconnect, content mutation, illegal transitions, immutable
completion, and retention of partial transitions plus the first terminal
failure. Frame tests cover exact U32BE length, canonical JCS-I64 bytes, bounds,
truncation, malformed JSON, and length mismatch.

Collector tests derive eligibility from raw evaluator/sample/backend results;
no API accepts a generic `passed=true`. They cover the seven exact IDs,
actual queue/termination types, full clock sample counts and ordering, CPU
migration, all-page three-point residency, all three PRFCHW CPUs and distinct
GCC/Clang dual-disassembler reports, complete three-CPU prestates, independent
writer/auditor readback, and incomplete evidence that cannot be eligible.

The existing traversal codegen gate remains mandatory. The additional runtime
gate uses GNU Binutils and accepted LLVM objdump to require exactly indirect
enable → one accepted traversal call → indirect disable. Duplicate traversal
and software-prefetch mutants must be rejected. Sanitizer runs may execute only
the fake/synthetic label; real PMU, affinity, NUMA, MSR, stand, qualification,
calibration, pilot, measurement, and confirmatory paths are prohibited.

## Evidence order

Verification proceeds from import/dependency checks through schema/unit/property checks, queue/refinement/concurrency checks, sanitizers, platform/timing/generated-code gates, lifecycle/storage/reconciliation integration, clean-room build, and synthetic dry run. Pre-pilot acceptance requires all applicable layers to pass with immutable evidence, zero unresolved sanitizer/correctness findings, a qualified eligible platform, and no unapproved suppression or unavailable mandatory capability.

## Software evidence versus scientific evidence

Passing tests shows that the implementation conforms to the frozen contract under tested environments. Calibration and treatment-blind pilot evidence may freeze platform-dependent parameters after software acceptance. Only authorized, valid, complete confirmatory blocks analyzed under the sealed protocol can support empirical scientific claims.
