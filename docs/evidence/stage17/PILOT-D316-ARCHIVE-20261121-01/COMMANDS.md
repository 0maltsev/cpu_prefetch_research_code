# Local software verification commands

Run from the repository root. No command below accesses the stand or starts an
experiment. The toolchain/dependencies were already provisioned. The namespace
wrapper allows the unchanged supervisor to inspect actual procfs and held child
identities without host root. It is a local test environment, not platform proof.

```sh
export S180_TOOLCHAIN="$PWD/build/ext007-toolchain-20261101/root/usr"
export PATH="$S180_TOOLCHAIN/bin:$PATH"
export LD_LIBRARY_PATH="$S180_TOOLCHAIN/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests"

cmake --build build/stage17-s180-native/dev-gcc16 --target \
  cpu_prefetch_s180_channel_fixture cpu_prefetch_s180_io_tests \
  cpu_prefetch_archive_channel_tests cpu_prefetch_runner_tests \
  cpu_prefetch_schedule_source_tests -j2

unshare --user --map-root-user --pid --fork --mount-proc setsid \
  "$S180_TOOLCHAIN/bin/ctest" --test-dir build/stage17-s180-native/dev-gcc16 \
  --output-on-failure -j2 \
  -R '^runner\.(s180\.|s180_|archive_channel\.|archive_channel_v1$|formal_archive_(custody_v1|runtime_v1|broker_v1|jobs_v1)$|formal_checkpoint_v1$)'

build/stage17-s180-native/dev-gcc16/cpu_prefetch_runner_tests
build/stage17-s180-native/dev-gcc16/cpu_prefetch_schedule_source_tests

clang-tidy -p build/stage17-s180-native/dev-gcc16 \
  src/runner/stage17_archive_channel.cpp \
  src/runner/stage17_s180_channel_sink.cpp \
  src/runner/stage17_s180_native_session.cpp \
  tests/stage17_s180_channel_test.cpp tests/stage17_s180_channel_fixture.cpp

PYTHONPATH="$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages" \
  cmake --build build/stage17-s180-native/dev-gcc16 --target \
  format-check protocol-check schema-fixture-check canonical-check queue-provenance-check
```

The retained `build-s180-io-matrix.py` was invoked once per variant using its
original `/tmp/build-s180-io-matrix.py` path:

```sh
python3 -B /tmp/build-s180-io-matrix.py asan-ubsan-gcc
python3 -B /tmp/build-s180-io-matrix.py tsan-gcc
python3 -B /tmp/build-s180-io-matrix.py asan-ubsan-clang
python3 -B /tmp/build-s180-io-matrix.py tsan-clang
```

All commands in the final verification exited0. Initial environment and fixture
failures are retained separately and described in REPORT.md. The earlier19-case
D315 results are not substituted for these fresh23-case sanitizer results.
