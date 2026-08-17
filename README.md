# CPU Prefetch Research Code

This repository is at **Stage 4: typed protocol/configuration model complete**
for protocol **`2.0.0-pre.1`**. It contains the Stage 3 build foundation plus a
C++20 typed logical model, strict loaders, record-local semantic validation,
Draft 2020-12 conformance fixtures, and deterministic canonical serialization.
It contains no queue, schedule generator, measurement loop, hardware-control
implementation, raw-data writer, or scientific analysis.

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
22.1.x/libc++ secondary. GoogleTest 1.17.0, RapidCheck `ff6af6f`, and Python
jsonschema 4.26.0 are test-only inputs. The exact dependency/source/license
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
if leak checking is adopted.

Release and future stand-foundation package:

```sh
cmake --preset release-gcc
cmake --build --preset release-gcc
ctest --preset release-gcc
cmake --build --preset release-gcc --target release-policy-check
cmake --build --preset release-gcc --target package
```

The release policy rejects `-march=native`, `-mtune=native`, `-Ofast`, and
`-ffast-math`. Coverage is not configured because no coverage policy has been
accepted. The package contains only the smoke binary, foundation and
typed-protocol libraries, headers, protocol model/version records, build
metadata, dependency inventory, and no-license notice.

## Created targets and metadata

- `cpu_prefetch_foundation`: minimal build/version identity library;
- `cpu_prefetch_protocol`: typed records, exact-value JSON, strict loading, and
  record-local semantic validation;
- `cpu_prefetch_smoke`: prints protocol, Git, compiler, and standard-library
  identity;
- `cpu_prefetch_foundation_tests`: GoogleTest identity contract;
- `cpu_prefetch_protocol_tests`: typed loading, semantic, canonical, lifecycle,
  block, access, and round-trip contracts;
- `cpu_prefetch_rapidcheck_smoke`: fixed-seed framework and exact-uint64
  canonicalization properties;
- `format-check`, `static-analysis`, `protocol-check`,
  `schema-fixture-check`, `canonical-check`, `document-check`,
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

## CI boundary and next stage

[`ci.yml`](.github/workflows/ci.yml) uses only a full-commit-pinned checkout
action and pre-provisioned self-hosted Linux x86-64 runners. CI calls the
commands above and performs no dependency download; runner policy must disable
dependency-network access after source checkout. Runner availability and
provisioning are external platform operations.

Stage 5 (queue provenance and correctness) is the exact next safe stage. It may
implement independently authored queue semantics and correctness evidence only.
Schedule generation, timing, measurement, pilot, and confirmatory behavior
remain prohibited until their later lifecycle gates.
