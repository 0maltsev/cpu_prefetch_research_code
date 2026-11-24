# Verification commands

From the repository root using the provisioned toolchain (no downloads):

```sh
export S180_TOOLCHAIN="$PWD/build/ext007-toolchain-20261101/root/usr"
export PATH="$S180_TOOLCHAIN/bin:$PATH"
export LD_LIBRARY_PATH="$S180_TOOLCHAIN/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests"
cmake --build build/stage17-s180-native/dev-gcc16 --target \
  cpu_prefetch_s180_io_tests cpu_prefetch_runner cpu_prefetch_runner_tests \
  cpu_prefetch_pilot_capture_tests cpu_prefetch_calibration_tests \
  cpu_prefetch_archive_channel_tests cpu_prefetch_s180_channel_fixture -j2
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  "$S180_TOOLCHAIN/bin/ctest" --test-dir build/stage17-s180-native/dev-gcc16 \
  --output-on-failure -j2 \
  -R '^runner\.(s180\.|s180_|archive_channel\.|archive_channel_v1$|formal_archive_(custody_v1|runtime_v1|broker_v1|jobs_v1)$|formal_checkpoint_v1$)'
build/stage17-s180-native/dev-gcc16/cpu_prefetch_runner_tests
build/stage17-s180-native/dev-gcc16/cpu_prefetch_pilot_capture_tests
build/stage17-s180-native/dev-gcc16/cpu_prefetch_calibration_tests
python3 -B tests/test_stage17_s180_plan_prepare_v1.py \
  --worker build/stage17-s180-native/dev-gcc16/cpu_prefetch_runner
clang-tidy -p build/stage17-s180-native/dev-gcc16 \
  src/calibration/native_pilot_capture.cpp src/runner/stage17_s180_input.cpp \
  src/runner/stage17_s180_session.cpp tests/stage17_s180_io_test.cpp \
  tests/stage17_s180_input_test.cpp tools/runner_main.cpp
# After correcting optional access in the new test:
clang-tidy -p build/stage17-s180-native/dev-gcc16 tests/stage17_s180_input_test.cpp
cmake --build build/stage17-s180-native/dev-gcc16 --target cpu_prefetch_s180_io_tests -j2
build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_io_tests \
  --gtest_filter='S180Input.*:S180ProspectiveLayout.*' --gtest_color=no
PYTHONPATH="$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages" \
  cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check runner-schema-check
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check
```

Run the retained matrix script for each of `asan-ubsan-gcc`, `tsan-gcc`,
`asan-ubsan-clang`, `tsan-clang`. It records configure/build/test phases separately
and selects the32 affected cases (`-S180Worker.*`). ASan uses the existing
managed-ptrace `detect_leaks=0` convention. The unchanged supervisor's procfs
checks run inside a user/PID namespace; no host sudo is used.
