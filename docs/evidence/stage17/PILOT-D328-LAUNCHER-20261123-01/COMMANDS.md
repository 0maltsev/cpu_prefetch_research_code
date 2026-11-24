# D328 verification commands

Use the existing provisioned toolchain and dependency prefixes; no network fetch,
stand command or production measurement entry is used. The isolated user/PID
namespace preserves the supervisor's original procfs and real-IPC checks.

```sh
export PATH="$PWD/build/ext007-toolchain-20261101/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/build/ext007-toolchain-20261101/root/usr/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
cmake -S . -B build/stage17-s180-native/dev-gcc16
cmake --build build/stage17-s180-native/dev-gcc16 \
  --target cpu_prefetch_s180_launcher_fixture -j2
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure -j2 \
  -R '^runner\.s180_(launcher|parent|archive_broker|archive_reservation|authority|journal|archive_channel|checkpoint|verified_sources)_v1$'
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check
clang-tidy -p build/stage17-s180-native/dev-gcc16 tests/stage17_s180_launcher_fixture.cpp
```

Python development/debug allocation:

```sh
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_launcher_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --endpoint build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_launcher_fixture \
  --describer build/stage17-s180-release-34247ce/cpu_prefetch_runner
```

GCC ASan/UBSan on the new test-only C++ endpoint, using the existing cached
ADDRESS_UNDEFINED configuration:

```sh
cmake -S . -B build/stage17-s180-native/asan-ubsan-gcc
cmake --build build/stage17-s180-native/asan-ubsan-gcc \
  --target cpu_prefetch_s180_launcher_fixture -j2
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -B tests/test_stage17_s180_launcher_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --endpoint build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_launcher_fixture \
  --describer build/stage17-s180-release-34247ce/cpu_prefetch_runner \
  --sanitized-endpoint build/stage17-s180-native/asan-ubsan-gcc/cpu_prefetch_s180_launcher_fixture \
  LauncherTests.test_sanitized_cpp_harness_parses_exact_sealed_context_and_all_sources -v
```

The sanitizer case passes actual sealed request/context/source FDs directly to
the software endpoint, with detect_leaks=0 and UBSan halt_on_error=1 in its test
environment. It applies no production AS ceiling to ASan's shadow address space.
No sanitizer or test backend can be selected through the production launch API.

The ordinary fixture uses explicit caller admission/provenance fixtures through
the private transport seam. Native/source/hash/channel/codec/ledger/process
operations are real; scientific admission and environment hardware actions are
not fabricated as empirical evidence. All fifteen ordinary cases run, with no
skipped inherited fixture class. The existing nineteen broker cases are still
run independently. The initial compile/static errors and outer fixture deadline
failure are retained before their corrections.

Checks also verify the original D233 base source is unchanged, frozen native
size/hash and source checkout remain unchanged/clean, AST and whitespace pass,
and owned temporary test directories have been removed. No raw observations
were transferred to the PC and no stand evidence was deleted.
