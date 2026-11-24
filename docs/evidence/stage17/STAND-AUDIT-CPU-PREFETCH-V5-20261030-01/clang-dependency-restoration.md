# Local Clang dependency restoration, 2026-10-30

Scope: development-machine software verification only. No stand mutation,
calibration, diagnostic capture, release qualification, or execution authority.
The vanished `/tmp/cpu-prefetch-stage16-deps` prefix was not reconstructed
under its old name. The new isolated prefix is
`/tmp/cpu-prefetch-ext007-deps.dRlOzG`.

The unchanged `config/dependencies.json` supplies the licenses and expected
hashes. All four archives below matched before extraction/build:

| Input | SHA-256 |
| --- | --- |
| `libc++-22.1.6-1-x86_64.pkg.tar.zst` | `07ae178a8991f22b955b6e8a5c047c4f75139e4878a133468f3a648fc443ede6` |
| `libc++abi-22.1.6-1-x86_64.pkg.tar.zst` | `13d52d67ebb42e9e2bd3bbc2af966b3b4ecb60f901b19674070d52b992e977ae` |
| GoogleTest `v1.17.0` | `65fab701d9829d38cb77c14acdc431d2108bfdbf8979e40eb8ae567edf10b27c` |
| RapidCheck `ff6af6fc683159deb51c543b065eba14dfcf329b` | `7ae7a8d59560f94eb68ed09fda59abd9871fe3b0cfc5acc60506de506289aa24` |

The libc++ packages came from `archive.archlinux.org/packages/l/libc++/`
and `archive.archlinux.org/packages/l/libc++abi/`. Source archives came from
`https://codeload.github.com/google/googletest/tar.gz/refs/tags/v1.17.0`
and `https://codeload.github.com/emil-e/rapidcheck/tar.gz/ff6af6fc683159deb51c543b065eba14dfcf329b`.
The RapidCheck short-ref archive has a different archive-directory prefix
and failed its hash check. It was retained separately and was not extracted
or built. The full-commit archive above matches the recorded source exactly.
No dependency manifest or expected hash was changed. No queue source was
downloaded.

Verified libc++ package `usr/` trees were extracted beneath `libcxx/`.
GoogleTest and RapidCheck were separately configured with Ninja,
`/usr/bin/clang++` 22.1.6, `-stdlib=libc++`,
`-isystem <prefix>/libcxx/usr/include/c++/v1`,
`-L<prefix>/libcxx/usr/lib -Wl,-rpath,<prefix>/libcxx/usr/lib`,
release mode, upstream tests/examples disabled, and installed under
`<prefix>/clang-prefix`. GCC dependencies were not replaced with these
ABI-incompatible libraries. The system Python is `/usr/bin/python3` 3.14.5.

Repository configuration uses the documented presets with explicit local
cache overrides, and performs no download:

```sh
dep_prefix=/tmp/cpu-prefetch-ext007-deps.dRlOzG
cmake --preset dev-clang-libcxx \
  -DPython3_EXECUTABLE=/usr/bin/python3 \
  "-DCMAKE_CXX_FLAGS=-isystem $dep_prefix/libcxx/usr/include/c++/v1" \
  "-DCMAKE_EXE_LINKER_FLAGS=-L$dep_prefix/libcxx/usr/lib -Wl,-rpath,$dep_prefix/libcxx/usr/lib" \
  "-DGTest_DIR=$dep_prefix/clang-prefix/lib/cmake/GTest" \
  "-DRapidCheck_INCLUDE_DIR=$dep_prefix/clang-prefix/include" \
  "-DRapidCheck_LIBRARY=$dep_prefix/clang-prefix/lib/librapidcheck.a"
cmake --build --preset dev-clang-libcxx --target \
  cpu_prefetch_calibration_tests cpu_prefetch_q15_tool_tests cpu_prefetch_runner_tests -j3
```

Set `LD_LIBRARY_PATH=<prefix>/libcxx/usr/lib` for local execution so the
loader also resolves the transitive `libc++abi.so.1`. Development suites
passed 25 calibration, 12 Q15, and 29 runner tests. Sanitizer presets use
the same explicit overrides and separate build directories; their results
must be recorded after execution, not inferred from successful configuration.
The rebuilt Clang ASan/UBSan and TSan executables were subsequently run with
`--gtest_brief=1`; both matrices passed all 66 affected tests with exit zero
and no sanitizer findings. ASan used `ASAN_OPTIONS=detect_leaks=0` as required
by the managed ptrace boundary. The release combined-prefetch codegen gate
also passed GNU and LLVM disassembly, 16 operations, and five negative mutants.
