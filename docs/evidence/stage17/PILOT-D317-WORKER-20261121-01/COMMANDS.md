# Verification commands

Run from the repository root with the existing provisioned dependencies:

```sh
export S180_TOOLCHAIN="$PWD/build/ext007-toolchain-20261101/root/usr"
export PATH="$S180_TOOLCHAIN/bin:$PATH"
export LD_LIBRARY_PATH="$S180_TOOLCHAIN/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests"

cmake --build build/stage17-s180-native/dev-gcc16 --target \
  cpu_prefetch_s180_io_tests cpu_prefetch_runner cpu_prefetch_runner_tests \
  cpu_prefetch_schedule_source_tests cpu_prefetch_archive_channel_tests \
  cpu_prefetch_s180_channel_fixture -j2

# Broader regression, before final expiry-rounding review:
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  "$S180_TOOLCHAIN/bin/ctest" --test-dir build/stage17-s180-native/dev-gcc16 \
  --output-on-failure -j2 \
  -R '^runner\.(s180\.|s180_|archive_channel\.|archive_channel_v1$|formal_archive_(custody_v1|runtime_v1|broker_v1|jobs_v1)$|formal_checkpoint_v1$)'

build/stage17-s180-native/dev-gcc16/cpu_prefetch_runner_tests
build/stage17-s180-native/dev-gcc16/cpu_prefetch_schedule_source_tests

# Final current code after the review/correction:
ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure -j2 \
  -R '^runner\.(s180\.|s180_worker_cli$)'

clang-tidy -p build/stage17-s180-native/dev-gcc16 \
  src/runner/stage17_s180_input.cpp src/runner/stage17_s180_worker.cpp \
  tests/stage17_s180_input_test.cpp tests/stage17_s180_session_test.cpp tools/runner_main.cpp
clang-tidy -p build/stage17-s180-native/dev-gcc16 \
  src/runner/stage17_s180_worker.cpp tests/stage17_s180_input_test.cpp

PYTHONPATH="$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages" \
  cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check
```

Each retained matrix script was invoked with `asan-ubsan-gcc`, `tsan-gcc`,
`asan-ubsan-clang` and `tsan-clang`. The original path for each was under `/tmp`:

```sh
# Full32-case baseline before the final rounding review:
python3 -B /tmp/build-s180-io-matrix.py VARIANT
# Rebuild final corrected code and run its3 affected cases:
python3 -B /tmp/verify-s180-epoch.py VARIANT
```

The second script selects `S180Worker.WholeSecond*`, `ActualSealed*` and `Window*`.
Its logs are distinct from the full baseline. ASan retains the existing managed
ptrace LeakSanitizer convention; no sanitizer or production guard is bypassed.
All final commands exited0. Native tests use actual local sockets/fork/PIDFDs;
the broader broker regression runs in an isolated user/PID namespace so its
unchanged supervisor can inspect procfs. No host sudo is required.

The only stand action was a read-only SSH Python query of UTC, boot ID, root
filesystem capacity and `cpu_prefetch` process-name matches. It generated no
schedules, changed no permissions/configuration and started no qualification or
experiment. Its exact output is retained separately.
