# CPU Prefetch Research Code

This repository has completed the **Stage 6 deterministic-workload slice** for
protocol **`2.0.0-pre.1`**. It contains the Stage 3 build foundation, Stage 4
typed protocol model, and independently authored bounded SPSC ring and
linked/recycler queue cores with provenance, refinement, model, stress,
sanitizer, and dual-disassembler evidence. It also contains deterministic event
records, working-set construction, integrity inputs, and exact `R0/R1/R2/L0/L1`
package mechanisms. It contains no schedule generator, measurement loop,
hardware-control implementation, raw-data writer, or scientific analysis.

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
by both development/ASan matrices and GCC TSan, and Clang TSan runs the other 51
tests.

Release and future stand-foundation package:

```sh
cmake --preset release-gcc
cmake --build --preset release-gcc
ctest --preset release-gcc
cmake --build --preset release-gcc --target release-policy-check
cmake --build --preset release-gcc --target queue-codegen-check
cmake --build --preset release-gcc --target workload-codegen-check
cmake --build --preset release-gcc --target package
```

The strict queue and workload code-generation targets require both GNU objdump
and LLVM 22 `llvm-objdump`. The workload probe covers the consumer mixer and
R1/R2/L1 target sites; each target requires its call-injection negative mutant
to be rejected. Audit targets may retain partial local reports, but only strict
dual-tool results close the gate.

The release policy rejects `-march=native`, `-mtune=native`, `-Ofast`, and
`-ffast-math`. Coverage is not configured because no coverage policy has been
accepted. The package contains only the smoke binary, foundation and
typed-protocol, queue, and workload libraries, headers, protocol/queue
provenance records, Stage 6 construction documentation, build metadata,
dependency inventory, and no-license notice.

## Created targets and metadata

- `cpu_prefetch_foundation`: minimal build/version identity library;
- `cpu_prefetch_protocol`: typed records, exact-value JSON, strict loading, and
  record-local semantic validation;
- `cpu_prefetch_queue`: independent ring and linked/recycler queue cores with
  explicit release/acquire, layout, lock-free, and quiescent-audit boundaries;
- `cpu_prefetch_workload`: independent Philox/HMAC deterministic streams,
  aligned immutable event arenas, working-set/footprint construction,
  integrity byte grammars, and five static package policies;
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
- `cpu_prefetch_rapidcheck_smoke`: fixed-seed framework and exact-uint64
  canonicalization properties;
- `format-check`, `static-analysis`, `protocol-check`,
  `schema-fixture-check`, `canonical-check`, `queue-provenance-check`,
  `queue-codegen-audit`, strict `queue-codegen-check`, strict
  `workload-codegen-check`, `document-check`,
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

## CI boundary and next safe action

[`ci.yml`](.github/workflows/ci.yml) uses only a full-commit-pinned checkout
action and pre-provisioned self-hosted Linux x86-64 runners. CI calls the
commands above and performs no dependency download; runner policy must disable
dependency-network access after source checkout. Runner availability and
provisioning are external platform operations.

Stage 6 is complete. Q6 accepted the D-027 bundle in
[`docs/STAGE7_DECISION_BUNDLE.md`](docs/STAGE7_DECISION_BUNDLE.md), and
ADR-0029 is `ACCEPTED`. The exact next safe activity is **Stage 7 schedule
implementation**. Timing, measurement, pilot, and confirmatory behavior remain
prohibited until their later lifecycle gates.
