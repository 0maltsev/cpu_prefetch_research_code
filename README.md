# CPU Prefetch Research Code

This repository has completed the **Stage 11 raw-storage software slice** for
protocol **`2.0.0-pre.1`**. It contains the Stage 3 build foundation, Stage 4
typed protocol model, and independently authored bounded SPSC ring and
linked/recycler queue cores with provenance, refinement, model, stress,
sanitizer, and dual-disassembler evidence. It also contains deterministic event
records, working-set construction, integrity inputs, and exact `R0/R1/R2/L0/L1`
package mechanisms, the accepted offline deterministic schedule generator and
fail-closed C++ decoder, and the D-009 clock reader, boundary-capture,
qualification-evaluator, and offline interval components. Stage 9 adds typed
Linux inventory/capability/placement/control evidence, dry-run planning,
independent readback, restoration, and canonical platform manifests. Stage 10
adds an explicit lifecycle projection, preparation/warm-up/reset evidence,
two-worker start barrier, one-attempt fake-backed open-loop executor,
release/acquire termination, drain/watchdog paths, and partial-failure
consequences. Stage 11 adds exact fixed physical rows, preallocated independent
observation streams, integrity/envelope records, checked storage budgets, and a
crash-aware append-only two-copy local backend. It contains no eligible-pair
qualification, production state-changing stand adapter, reconciliation,
authorized scientific run, or scientific analysis.

The exact D-010/D-020 physical-storage contract is documented in
[`docs/STAGE11_STORAGE_DECISION_BUNDLE.md`](docs/STAGE11_STORAGE_DECISION_BUNDLE.md).
Q9 accepted it as ADR-0032 and ADR-0033. The local implementation and software
verification pass. Concrete stand capacity, page residency, real independent
failure domains/custody, and operational recovery remain Phase 16 evidence.

The repository owner selected **no license**. See
[`docs/NO_LICENSE_GRANT.md`](docs/NO_LICENSE_GRANT.md) and ADR-0021. There is no
`LICENSE` file and no permission to copy, modify, or distribute
repository-authored material.

## Scientific source of truth

The immutable imported snapshot is in
[`protocol/2.0.0-pre.1/`](protocol/2.0.0-pre.1/). Start with:

1. [`EXPERIMENT_IMPLEMENTATION_SPEC.md`](protocol/2.0.0-pre.1/EXPERIMENT_IMPLEMENTATION_SPEC.md);
2. [`PROTOCOL_FREEZE_CHECKLIST.md`](protocol/2.0.0-pre.1/PROTOCOL_FREEZE_CHECKLIST.md);
3. [`handoff/README.md`](protocol/2.0.0-pre.1/handoff/README.md);
4. [`docs/TRACEABILITY_MATRIX.md`](docs/TRACEABILITY_MATRIX.md).

`protocol/2.0.0-pre.1/PAPER_AGENTS.md` is imported evidence, not a repository
instruction file. Stage B and Stage C remain outside scope. Development and
synthetic checks support software correctness only and never empirical claims.

## Toolchain and offline inputs

ADR-0022 constrains the Stage 3 baseline to CMake 4.3.x, Ninja 1.13.x, Python
3.14.x, Git 2.54.x, GCC 16.1.x/libstdc++ primary, and Clang/LLVM
22.1.x/libc++ secondary. OpenSSL 3.6.x supplies SHA-256/HMAC-SHA-256.
GoogleTest 1.17.0, RapidCheck `ff6af6f`, and Python jsonschema 4.26.0 are
test-only inputs. The exact dependency/source/license
inventory is [`config/dependencies.json`](config/dependencies.json).

Configuration never downloads dependencies. Install the recorded inputs into
the system prefix or an offline prefix, then point each toolchain at its
ABI-compatible prefix:

```sh
export CPU_PREFETCH_DEPS_ROOT=/opt/cpu-prefetch-deps/gcc16
export PYTHONPATH="$CPU_PREFETCH_DEPS_ROOT/usr/lib/python3.14/site-packages"
```

For the secondary matrix, select a separate prefix whose GoogleTest and
RapidCheck libraries were built with Clang 22.1.x and libc++ 22.1.x. An empty
`CPU_PREFETCH_DEPS_ROOT` means dependencies are pre-provisioned under `/usr`.
The configure step fails on unsupported tool or asserted dependency revisions.

## Build, test, and verification commands

Primary clean development build:

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc
ctest --preset dev-gcc
```

Secondary clean development build:

```sh
cmake --preset dev-clang-libcxx
cmake --build --preset dev-clang-libcxx
ctest --preset dev-clang-libcxx
```

Repository checks, after configuring `dev-gcc`:

```sh
cmake --build --preset dev-gcc --target format-check
cmake --build --preset dev-gcc --target static-analysis
cmake --build --preset dev-gcc --target protocol-check
cmake --build --preset dev-gcc --target schema-fixture-check
cmake --build --preset dev-gcc --target canonical-check
cmake --build --preset dev-gcc --target schedule-check
ctest --preset dev-gcc -L timing --output-on-failure
ctest --preset dev-gcc -L platform --output-on-failure
ctest --preset dev-gcc -L lifecycle --output-on-failure
ctest --preset dev-gcc -L storage --output-on-failure
cmake --build --preset dev-gcc --target storage-format-check
cmake --build --preset dev-gcc --target storage-schema-check
cmake --build --preset dev-gcc --target queue-provenance-check
cmake --build --preset dev-gcc --target document-check
cmake --build --preset dev-gcc --target dependency-check
cmake --build --preset dev-gcc --target ci-check
```

Apply formatting explicitly with:

```sh
cmake --build --preset dev-gcc --target format
```

Sanitizer matrices:

```sh
cmake --preset asan-ubsan-gcc
cmake --build --preset asan-ubsan-gcc
ctest --preset asan-ubsan-gcc

cmake --preset tsan-gcc
cmake --build --preset tsan-gcc
ctest --preset tsan-gcc

cmake --preset asan-ubsan-clang-libcxx
cmake --build --preset asan-ubsan-clang-libcxx
ctest --preset asan-ubsan-clang-libcxx

cmake --preset tsan-clang-libcxx
cmake --build --preset tsan-clang-libcxx
ctest --preset tsan-clang-libcxx
```

The ASan presets set `ASAN_OPTIONS=detect_leaks=0` because LeakSanitizer cannot
run under this managed environment's ptrace boundary. AddressSanitizer and
UndefinedBehaviorSanitizer remain enabled. LeakSanitizer is not silently
claimed; a future eligible non-ptrace environment must add a separate leak gate
if leak checking is adopted. The Clang TSan runtime defines the same global
allocation symbols as the dedicated no-allocation hook, so that one test target
is deliberately absent only from `tsan-clang-libcxx`; the hook remains covered
by both development/ASan matrices and GCC TSan, and Clang TSan runs every other
configured test.

Release and future stand-foundation package:

```sh
cmake --preset release-gcc
cmake --build --preset release-gcc
ctest --preset release-gcc
cmake --build --preset release-gcc --target release-policy-check
cmake --build --preset release-gcc --target queue-codegen-check
cmake --build --preset release-gcc --target workload-codegen-check
cmake --build --preset release-gcc --target timing-codegen-check
cmake --build --preset release-gcc --target storage-codegen-check
cmake --build --preset release-gcc --target package

cmake --preset release-clang-libcxx
cmake --build --preset release-clang-libcxx --target timing-codegen-check
cmake --build --preset release-clang-libcxx --target storage-codegen-check
```

The strict queue, workload, timing, and storage code-generation targets require both GNU
objdump and LLVM 22 `llvm-objdump`. The workload probe covers the consumer mixer and
R1/R2/L1 target sites; each target requires its call-injection negative mutant
to be rejected. The timing probe covers the clock reader and enqueue/dequeue
boundary specializations for all five packages, plus all six D-009 negative
mutants. Audit targets may retain partial local reports, but only strict
dual-tool results close the gate.

The release policy rejects `-march=native`, `-mtune=native`, `-Ofast`, and
`-ffast-math`. Coverage is not configured because no coverage policy has been
accepted. The package contains only the smoke binary, foundation,
typed-protocol, queue, workload, schedule, timing, platform, lifecycle, and storage libraries, the
offline schedule generator, headers, protocol/queue provenance records, Stage
6/7 correctness, Stage 8 timing, Stage 9 platform-control, Stage 10 lifecycle,
and Stage 11 storage documentation,
implementation-owned derivation schema, build metadata, dependency inventory,
and no-license notice.

## Created targets and metadata

- `cpu_prefetch_foundation`: minimal build/version identity library;
- `cpu_prefetch_protocol`: typed records, exact-value JSON, strict loading, and
  record-local semantic validation;
- `cpu_prefetch_queue`: independent ring and linked/recycler queue cores with
  explicit release/acquire, layout, lock-free, and quiescent-audit boundaries;
- `cpu_prefetch_workload`: independent Philox/HMAC deterministic streams,
  aligned immutable event arenas, working-set/footprint construction,
  integrity byte grammars, and five static package policies;
- `cpu_prefetch_schedule`: validated immutable schedule decoding, suite and
  derivation binding, namespace-role separation, and common-family checks;
- `cpu_prefetch_timing`: compiler-fenced raw-clock reads, exact conversion,
  producer/consumer capture, offline interval equations, and qualification
  evaluators;
- `cpu_prefetch_platform`: read-only Linux topology/environment inventory,
  capability and exact Stage A placement validation, dry-run/injected apply,
  independent readback, reverse restoration, and rich/imported-schema manifest
  emission;
- `cpu_prefetch_lifecycle`: fail-closed internal state graph and imported-enum
  projection, preparation/warm-up/reset evidence, dedicated termination word,
  start barrier, and compile-time open-loop worker executor;
- `cpu_prefetch_storage`: bounded private observation streams, exact v1 raw
  codec/decoder, Stage 8/10 capture binding, integrity/envelope/ledger records,
  checked budgets, and append-only crash-aware local publication;
- `cpu_prefetch_smoke`: prints protocol, Git, compiler, and standard-library
  identity;
- `cpu_prefetch_foundation_tests`: GoogleTest identity contract;
- `cpu_prefetch_protocol_tests`: typed loading, semantic, canonical, lifecycle,
  block, access, and round-trip contracts;
- `cpu_prefetch_queue_tests`: FIFO, capacity, wrap, fixed-node-cycle,
  refinement, phase suspension, layout, rollover-assumption, and fault tests;
- `cpu_prefetch_queue_stress`: fixed-seed two-thread correctness stress only;
- `cpu_prefetch_workload_tests` and `cpu_prefetch_workload_noalloc`: workload
  known-answer, boundary, corruption, package-target, and prepared-path tests;
- `cpu_prefetch_schedule_tests` and `schedule.python_generator`: integrated
  golden, decoder, hash, namespace, common-family, schema, boundary, overflow,
  publication, and completion-independence tests;
- `cpu_prefetch_timing_tests`: fake/real clock, boundary, cross-thread,
  failure, overflow, equation, qualification-math, and queue-order tests;
- `cpu_prefetch_platform_tests`: topology/placement, capability/authority,
  dry-run/apply/readback/restoration fault, stale-state, and manifest tests;
- `cpu_prefetch_lifecycle_tests`: exhaustive transitions, partial artifacts,
  warm-start reset, start/publication races, exactly-one-attempt, cancellation,
  drain, watchdog, and deterministic concurrency tests;
- `cpu_prefetch_storage_tests`, `cpu_prefetch_storage_noalloc`, and
  `cpu_prefetch_storage_stress`: codec goldens/corruption, capacity and budget,
  immutable publication/recovery/finalization, hot-writer allocation, and
  independent-stream concurrency tests;
- `cpu_prefetch_rapidcheck_smoke`: fixed-seed framework and exact-uint64
  canonicalization properties;
- `format-check`, `static-analysis`, `protocol-check`,
  `schema-fixture-check`, `canonical-check`, `queue-provenance-check`,
  `queue-codegen-audit`, strict `queue-codegen-check`, strict
  `workload-codegen-check`, `timing-codegen-audit`, strict
  `timing-codegen-check`, `storage-format-check`, `storage-schema-check`, strict
  `storage-codegen-check`, `schedule-check`, `document-check`,
  `dependency-check`, `ci-check`, and `release-policy-check`;
- CMake `install` and CPack `package` targets.

Generated `version_metadata.json` contains the protocol version, full Git
revision, dirty state (including untracked source), exact compiler, standard
library, C++ standard, generator, and build type. It intentionally contains no
timestamp or absolute source/build directory. A package made from an uncommitted
tree also carries `-dirty` in its filename.

## Protocol model boundary

The unmodified imported schemas are the normative structural contracts. The
pinned Python validator checks those schemas and fixtures; the C++ loader then
constructs immutable typed records and applies record-local rules. Errors carry
stable categories, field paths, and rule IDs. Unknown versions, enum values,
fields, missing normative values, malformed IDs/hashes/units, duplicate JSON
keys, and unsupported numeric values fail closed.

Canonical `JCS-I64-v1` serialization preserves signed and unsigned 64-bit
integers exactly. The full type and deferral inventory is documented in
[`docs/PROTOCOL_MODEL.md`](docs/PROTOCOL_MODEL.md). Cross-record artifact lookup,
reconciliation, append-only lineage, and access chronology remain explicit
Stage 12/14 obligations behind `CrossRecordSemanticValidator`; schema validity
alone never claims those properties.

## Queue correctness boundary

The two machine-readable records in
[`config/queue-provenance/`](config/queue-provenance/) bind the canonical paper
sections/figures, official-artifact status, no-source-reuse mode, repository
no-license posture, source hashes, every declared adaptation, memory ordering,
atomic/layout requirements, claim limits, and generated-code status. The
complete happens-before and fixed-arena refinement argument is
[`docs/QUEUE_CORRECTNESS.md`](docs/QUEUE_CORRECTNESS.md). Development/sanitizer
execution is correctness evidence only and contains no operation timing or
rate.

## Workload-construction boundary

ADR-0025 through ADR-0028 freeze the accepted Q5 bundle. The exact stream
mapping, record layout, strong identity types, integrity byte grammars,
footprint rules, package hot operations, code-generation findings, and still
unresolved platform/calibration inputs are documented in
[`docs/WORKLOAD_CONSTRUCTION.md`](docs/WORKLOAD_CONSTRUCTION.md). Synthetic
fixture seeds prove deterministic software behavior only; they are not eligible
experiment inputs.

## Schedule-generation boundary

ADR-0029 fixes the offline
`POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1` suite. Python 3.14
generates complete immutable schedules before measurement; C++ accepts only a
fully decoded and validated deadline array. Exact numeric mapping, envelope and
derivation bindings, hashes, namespace rules, failure behavior, and synthetic
goldens are documented in
[`docs/SCHEDULE_GENERATION.md`](docs/SCHEDULE_GENERATION.md). No queue result,
clock reading, or treatment outcome can enter generation.

## Timing boundary

ADR-0030 fixes and Stage 8 implements
`LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1`: compiler-fenced
`CLOCK_MONOTONIC_RAW` reads, checked absolute-nanosecond to exact
relative-picosecond conversion, accepted-only `p`, successful-dequeue `q`, all
other imported producer/consumer boundaries, and offline checked equations.
Raw samples are never overhead-corrected. Qualification math rejects short
diagnostic samples as ineligible, and the release codegen check covers all five
packages and negative boundary/clock/fence/syscall mutants. The complete
contract and limitations are in [`docs/TIMING.md`](docs/TIMING.md).

Focused local commands are:

```sh
ctest --preset dev-gcc -L timing --output-on-failure
cmake --build --preset release-gcc --target timing-codegen-check
```

The second command requires both accepted disassemblers. Neither command
qualifies an experiment stand; the open Stage 9 operational/Phase 16 gate must
supply an explicit worker pair and the full traced/per-core/bidirectional
evidence.

## Lifecycle boundary

ADR-0031 implements Stage 10 without extending the imported lifecycle enum.
Every internal transition has a timestamp, actor, reason, and explicit
artifact consequences. Warm-up and measurement namespaces remain distinct;
logical reset preserves warm mappings/content and rejects allocation, remap,
retouch, or schedule regeneration. The producer performs one backend attempt
per due deadline; `FULL` is retained without retry. A dedicated lock-free u32
word release-publishes producer completion and the consumer acquire-observes it
before drain-to-empty. Recovery is explicit and only after finalization.

The exact graph, failure/artifact matrix, fake evidence, and unresolved
production bindings are in [`docs/LIFECYCLE.md`](docs/LIFECYCLE.md). Focused
software verification is:

```sh
ctest --preset dev-gcc -L lifecycle --output-on-failure
ctest --preset asan-ubsan-gcc -L lifecycle --output-on-failure
ctest --preset tsan-gcc -L lifecycle --output-on-failure
```

These runs are correctness evidence only. Stage 11 supplies the physical sink;
the final package/platform specialization still requires measured-release
generated-code review before pilot readiness.

## Raw-storage boundary

ADR-0032/0033 fix and Stage 11 implements
`RAW-OBS-U64LE-LP-RUNID-v1` and `RAW-OBS-NONE-TMP1-DUR2-v1`. Producer and
consumer workers append independently to fixed, explicitly prepared,
64-byte-aligned buffers. The append bodies write only precomputed row prefixes
and fixed little-endian words; they perform no allocation, filesystem I/O,
formatting, compression, locking, or dynamic growth. Overflow is sticky and
invalidating, never truncation presented as complete data.

Post-run code validates/decodes logical rows, emits canonical integrity and raw
envelopes, computes checked capacity proofs, and publishes immutable objects to
two explicit domains with independent reread SHA-256 evidence. A fresh process
can reopen an exact run in recovery-only mode and may promote only a staging
object whose expected size and hash match; it cannot publish a new object.
Partial finalization preserves only evidence that exists and never emits a
joined stream. The full mapping and remaining operational limits are in
[`docs/STORAGE.md`](docs/STORAGE.md).

Focused software verification is:

```sh
ctest --preset dev-gcc -L storage --output-on-failure
cmake --build --preset dev-gcc --target storage-format-check
cmake --build --preset dev-gcc --target storage-schema-check
cmake --build --preset release-gcc --target storage-codegen-check
```

The large synthetic storage check is correctness-only and reports no rate or
latency. Two local directories do not establish independent stand failure
domains, custody, or planned-run capacity.

## CI boundary and next safe action

[`ci.yml`](.github/workflows/ci.yml) uses only a full-commit-pinned checkout
action and pre-provisioned self-hosted Linux x86-64 runners. CI calls the
commands above and performs no dependency download; runner policy must disable
dependency-network access after source checkout. Runner availability and
provisioning are external platform operations.

Stage 9's software slice is complete under ADR-0018 and ADR-0019; see
[`docs/PLATFORM_CONTROL.md`](docs/PLATFORM_CONTROL.md) and the read-only
[`docs/STAND_RUNBOOK.md`](docs/STAND_RUNBOOK.md). Exact stand actuator,
authority, selected-pair/address readback, vendor-prefetch mapping/probes,
restoration, and dynamic clock evidence remain mandatory operational gates.
Stage 10's lifecycle and Stage 11's local storage slices are complete under
ADR-0031 through ADR-0033. The protocol and statistical owner accepted the
[`D-031/Q10` decision bundle](docs/STAGE12_D031_DECISION_BUNDLE.md), selecting
a versioned exhaustive blocker set with a non-priority multiple summary. Stage
12 remains blocked until that amended protocol snapshot is published or
supplied, imported alongside `2.0.0-pre.1`, and hash-verified. Measurement,
pilot, and confirmatory behavior remain prohibited until their later lifecycle
gates.
