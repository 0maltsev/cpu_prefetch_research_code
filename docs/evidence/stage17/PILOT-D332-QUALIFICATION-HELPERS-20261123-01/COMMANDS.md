# D332 commands

Build only auxiliary executables, using the same existing full-runtime compiler
and filtered binutils libraries as D320. Never edit the clean native source tree
or target the frozen measurement executable for this diagnostic fix.

```sh
export S180_QUAL_TOOLS="$PWD/build/ext007-toolchain-20261101/root/usr"
export S180_QUAL_RUNTIME="$PWD/build/ext007-runtime-20261101/root/usr"
export S180_QUAL_RELEASE="$PWD/build/stage17-s180-release-34247ce"
export PATH="$S180_QUAL_RUNTIME/bin:$PATH"
export LD_LIBRARY_PATH="$S180_QUAL_RELEASE/binutils-libs:$S180_QUAL_TOOLS/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
"$S180_QUAL_TOOLS/bin/cmake" --build "$S180_QUAL_RELEASE" --target \
  cpu_prefetch_q15_tool cpu_prefetch_q15_clock_qualification_tool \
  cpu_prefetch_q15_qualification_evidence_tool cpu_prefetch_clock_vdso_probe_tool -j2
"$S180_QUAL_TOOLS/bin/cmake" --build "$S180_QUAL_RELEASE" --target \
  cpu_prefetch_q15_controller cpu_prefetch_q15_prestate_collector cpu_prefetch_preflight -j2
```

Only --self-test is executed for the six diagnostic helpers; fixed-tool
--describe-fixed-scope is metadata only. The first evidence-helper invocation
fails its stale profile comparison; preserve that result before fixing source.
No --qualify-pair, --collect, --probe, MSR action, native session or preflight
execution is used. The standalone preflight is built, not executed.

For the corrected development build and the existing GCC ADDRESS_UNDEFINED
configuration, use the smaller toolchain prefix bin/lib (not its full old libc):

```sh
export PATH="$PWD/build/ext007-toolchain-20261101/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/build/ext007-toolchain-20261101/root/usr/lib"
cmake -S . -B build/stage17-s180-native/dev-gcc16
cmake --build build/stage17-s180-native/dev-gcc16 \
  --target cpu_prefetch_q15_qualification_evidence_tool -j2
ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure \
  -R '^q15\.qualification_evidence_tool_self_test$'
cmake -S . -B build/stage17-s180-native/asan-ubsan-gcc
cmake --build build/stage17-s180-native/asan-ubsan-gcc \
  --target cpu_prefetch_q15_qualification_evidence_tool -j2
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 \
  build/stage17-s180-native/asan-ubsan-gcc/cpu_prefetch_q15_qualification_evidence_tool --self-test
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check
git diff --check
```

The final six-helper matrix substitutes only the corrected development evidence
helper for its broken frozen counterpart. It captures every exit code and SHA,
then verifies the native binary unchanged. These are not release-qualified or
empirical results. LSan is disabled under the managed ptrace boundary as required
by the repository; ASan and UBSan remain active.
