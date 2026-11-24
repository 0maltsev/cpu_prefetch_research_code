# Verification commands

The native source is an isolated clean worktree of34247ce under
`build/stage17-s180-release-source-34247ce`; build output is
`build/stage17-s180-release-34247ce`. Use the existing full runtime's compiler,
startup objects and binutils; the smaller toolchain prefix alone is insufficient
for identical release provenance. No dependencies were downloaded.

```sh
export S180_TOOLS="$PWD/build/ext007-toolchain-20261101/root/usr"
export S180_RUNTIME="$PWD/build/ext007-runtime-20261101/root/usr"
export S180_NATIVE_SOURCE="$PWD/build/stage17-s180-release-source-34247ce"
export S180_RELEASE="$PWD/build/stage17-s180-release-34247ce"
export PATH="$S180_RUNTIME/bin:$PATH"
export LD_LIBRARY_PATH="$S180_RELEASE/binutils-libs:$S180_TOOLS/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
"$S180_TOOLS/bin/cmake" -S "$S180_NATIVE_SOURCE" -B "$S180_RELEASE" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER="$S180_RUNTIME/bin/g++" \
  -DCMAKE_PREFIX_PATH="$S180_RUNTIME" -DCPU_PREFETCH_RAPIDCHECK_REVISION=ff6af6f \
  -DPython3_EXECUTABLE=/usr/bin/python3.14 -DCMAKE_LINKER="$S180_RUNTIME/bin/ld" \
  -DCPU_PREFETCH_GNU_OBJDUMP="$S180_RUNTIME/bin/objdump" \
  -DGTest_DIR="$S180_RUNTIME/lib/cmake/GTest" \
  -DRapidCheck_INCLUDE_DIR="$S180_RUNTIME/include" \
  -DRapidCheck_LIBRARY="$S180_RUNTIME/lib/librapidcheck.a"
"$S180_TOOLS/bin/cmake" --build "$S180_RELEASE" --target \
  cpu_prefetch_runner cpu_prefetch_s180_io_tests cpu_prefetch_stage17_archive_encoder \
  queue-codegen-check workload-codegen-check timing-codegen-check storage-codegen-check \
  runner-relax-codegen-check runner-combined-codegen-check q15-runtime-codegen-check \
  discovery-codegen-check -j2
python3 -B tools/check_s180_codegen.py --binary "$S180_RELEASE/cpu_prefetch_runner" \
  --source-root "$S180_NATIVE_SOURCE" --output "$S180_RELEASE/s180_codegen_report-final.json" \
  --gnu-objdump "$S180_RUNTIME/bin/objdump"
python3 -B tests/test_stage17_s180_codegen.py \
  --report "$S180_RELEASE/s180_codegen_report-final.json" \
  --binary "$S180_RELEASE/cpu_prefetch_runner" --source-root "$S180_NATIVE_SOURCE" --rule-root .
"$S180_TOOLS/bin/ctest" --test-dir "$S180_RELEASE" --output-on-failure -j2 \
  -R '^runner\.(s180\.|s180_worker_cli$|s180_plan_prepare_v1$|s180_authority_v1$)'
# Six real-IPC fixtures outside the managed SO_PEERCRED restriction:
"$S180_RELEASE/cpu_prefetch_s180_io_tests" --gtest_color=no \
  --gtest_filter='S180Channel.*:S180Worker.ActualSealedFdEntryReachesOnlyTheSeparatelyLinkedSoftwareBackend:S180Worker.RealWorkerSinkChecksDurableCustodyBytesBeforeReturningFromAck'
```

The build-local`binutils-libs` consists only of symlinks to existing full-runtime
libraries starting with libbfd/libopcodes/libsframe/libctf/libzstd/libz.so/
libjansson. Exact names/targets/size/hashes are in`toolchain-observation.json`.
It intentionally excludes the old libc/libm; no system library was replaced.
The initial compiler-change CMake cache reset required the configure command
again with its explicit Release/dependency inputs. Failed attempts are retained.

Both missing disassembler paths were explicitly supplied to the new CLI; it
returned3 with`BLOCKED_MISSING_TOOL`. The same correctly pinned candidate was
also checked with the unchanged formal CLI to retain its actual duplicate-root
failure. The new aggregate CMake command is inspected in`target-command-binding.json`;
direct CLI invocations above are the actual verification performed.

Format/protocol/canonical targets were run on the current repository using the
provisioned toolchain and pinned Python schema dependencies. Both new Python
files were parsed with ast;`git diff --check` passed. A separate read-only SSH
Python query recorded boot, rootfs space, memory and native process-name matches.
It performed no qualification, schedule generation or experiment.
