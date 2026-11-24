# EXT007 local verification, 2026-11-01

Scope: development-machine software verification. No diagnostic, calibration,
pilot, confirmatory run, operational transition, or stand mutation occurred.
The source base is `0454d00`; this evidence describes the subsequent ADR-0183
working-tree changes, not a clean qualified release.

## Implemented and verified

`discovery_session.hpp` coordinates the same two threads through preparation,
warm-up, bounded consumer drain, shared/private logical reset, a separate
measurement start, and final drain. Eleven real-ring tests use synthetic
time. They cover successful reconciliation, preparation rejection/exception,
origin failure/overflow, warm-up validation, each private-reset failure,
warm-up drain failure, measurement clock failure, capacity exhaustion,
invalid plans, and a post-capture exception. A rejected consumer reset
initially produced the wrong start-failure classification; the regression
now preserves it as a warm-up failure and starts no measurement.

| Fresh check | Result |
| --- | --- |
| GCC 16.1.1 development calibration | 46/46 pass |
| Clang 22.1.6/libc++ 22.1.6 development calibration | 46/46 pass |
| GCC ASan/UBSan and TSan calibration | 46/46 pass in each |
| Clang/libc++ ASan/UBSan and TSan calibration | 46/46 pass in each |
| GCC runner and Q15 affected suites | 29/29 and 12/12 pass |
| Existing lifecycle suite | 26/26 pass |
| RapidCheck smoke/refinement suite | Six checks, 100 generated cases each, pass |
| New session header/test formatting and clang-tidy | Pass, no user-code diagnostics |
| Immutable protocol/schema integrity | Three snapshots, 54 artifacts, 12 authoritative hashes, 21 imported and 377 implementation schemas pass |
| Imported schema fixtures | 35 positive and 32 negative pass |
| Canonical fixtures | Three shared cases pass |
| Discovery selector | 13 tests pass |
| Calibration mapping/policy | v54 reproduces; two mappings, six output families, 36 output mutants, six request mutants, eight malformed prestates pass |

Prospective v54 replay remains `PREPARED`, zero resolutions, ten missing
inputs, and `pilot_ready=false`. This is checked-in genesis verification,
not a new validation or migration of the external six-resolution journal.

Sanitizer runs use the repository options, including `detect_leaks=0` during
both ASan build-time GoogleTest discovery and execution. The first fresh
ASan discovery failed because the manual build invocation omitted that
required environment variable; the corrected build and full tests pass.
No additional source check or sanitizer was disabled to obtain a pass.

Fresh global formatting still fails on unchanged `src/platform/platform.cpp`,
`tests/platform_model_test.cpp`, and
`tools/q15_qualification_evidence_tool_main.cpp`. The focused runner static
check reproduces the unchanged `spin_wait_nanoseconds` exception diagnostic
and two optional-access diagnostics in `tests/runner_model_test.cpp`.
Those five files match the source base exactly; the new session header/test
passes its own strict checks. These baseline failures remain release blockers.

## Restored tools and remaining release limitations

The system now exposes GCC 16.2.1, Clang 23.1.4, CMake 4.4.5, Git 2.56.0,
and glibc 2.44. The old temporary prefix no longer exists. Accepted compiler,
runtime, build, and test packages were recovered into the ignored persistent
workspace prefix `build/ext007-toolchain-20261101/`. Publisher signatures
were verified against the system Arch public keyring before extraction.
Its ASCII-armored form was dearmored into the isolated prefix for `gpgv`;
the system keyring was not modified. JsonCpp 1.9.6 supplies the old CMake
binary's required `libjsoncpp.so.26` and retains its recorded MIT/public-domain
licenses. All restored package hashes, signature hashes, signing fingerprints,
and source-file hashes are in [toolchain-restoration.json](toolchain-restoration.json).

The four libc++/test-source downloads and all five Python package inputs
matched the unchanged hashes in `config/dependencies.json`. The exact Python
packages are isolated in `<prefix>/python`; configure/build/test perform no
download. The initial protocol check rejected the host's newer `rpds-py`;
it passes with the pinned environment. GCC and Clang use separate compatible
GoogleTest/RapidCheck installations.

From the repository root, source the local activation file before commands:

```sh
source build/ext007-toolchain-20261101/activate.sh
cmake --preset dev-gcc \
  -DCMAKE_CXX_COMPILER="$ext007_toolchain_root/usr/bin/g++" \
  -DGIT_EXECUTABLE="$ext007_toolchain_root/usr/bin/git" \
  -DPython3_EXECUTABLE="$PWD/build/ext007-toolchain-20261101/python/bin/python" \
  -DCPU_PREFETCH_CLANG_FORMAT="$ext007_toolchain_root/usr/bin/clang-format" \
  -DCPU_PREFETCH_CLANG_TIDY="$ext007_toolchain_root/usr/bin/clang-tidy" \
  -DGTest_DIR="$ext007_toolchain_root/usr/lib/cmake/GTest" \
  -DRapidCheck_INCLUDE_DIR="$ext007_toolchain_root/usr/include" \
  -DRapidCheck_LIBRARY="$ext007_toolchain_root/usr/lib/librapidcheck.a" \
  -DCPU_PREFETCH_RAPIDCHECK_REVISION=ff6af6f
cmake --build --preset dev-gcc --target cpu_prefetch_calibration_tests -j3
build/dev-gcc/cpu_prefetch_calibration_tests --gtest_brief=1
```

Other profiles were configured through their documented presets into
separate `build/ext007-<preset>` directories, using the same explicit tool
paths. Clang uses `<prefix>/clang-tests/usr` for GoogleTest/RapidCheck;
`CPU_PREFETCH_DEPS_ROOT=<prefix>/root` supplies pinned libc++ headers and
runtime through the existing Clang presets. ASan exports
`ASAN_OPTIONS=detect_leaks=0` before configure/build/test.

This prefix still uses host glibc 2.44 and does not establish conformity to
the accepted release dependency matrix. Existing global formatting/static
analysis blockers remain unwaived. The live diagnostic backend, actual NUMA
and integrity evidence, budgets/namespaces, outer watchdog, custody, new
qualified release/policy, and signed action admission still need integration.

## Stand access

An initial read-only SSH inspection returned the stand identity and found
no installed compiler or CMake. Three later attempts to refresh only the
retained v5-12 `status` command failed during SSH banner exchange, before
command execution, with exit 255. These attempts issued no experiment,
hardware write, retry of a stopped action, or operational transition. The
last validated six-resolution stand checkpoint remains dated 2026-10-30;
its present state has not been inferred from failed connections.
A separate authenticated `true` probe succeeded with `IPQoS=none`; it did
not validate the journal or establish that the connection failures are solved.
