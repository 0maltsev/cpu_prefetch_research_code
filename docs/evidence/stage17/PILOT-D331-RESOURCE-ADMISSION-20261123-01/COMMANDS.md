# D331 verification commands

Use only the existing provisioned dependencies. No downloads, native rebuild,
qualification, source bank generation or measurement command is used.

```sh
export PATH="$PWD/build/ext007-toolchain-20261101/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/build/ext007-toolchain-20261101/root/usr/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
cmake -S . -B build/stage17-s180-native/dev-gcc16
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_resource_admission_v1.py \
  --worker build/stage17-s180-release-34247ce/cpu_prefetch_runner -v
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_environment_v1.py -v
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure -j2 \
  -R '^runner\.s180_(resource_admission|resource_plan|environment|verified_sources|plan_prepare|journal|authority|parent|launcher|archive_broker|archive_reservation)_v1$'
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check
git diff --check
```

The resource test's positive flow uses private owned-source construction for tiny
software bytes and explicit hardware/memory/rlimit/free-space doubles. Actual
descriptor sealing/closure, native description, codec bounds and locked stores
remain real. No report/double can pass the production entry's object-type gates.
The portable CTest takes its built runner; the direct debug run uses the frozen
release. This establishes software behavior, not actual qualified resources.

AST and byte-preservation checks cover changed modules/tests and the unchanged
native image, clean detached source checkout, protocol/C++ sources, original
archive runtime/custody/profile, frozen isolation core and approved identities.
Text-log retention normalizes trailing whitespace/EOF with original hashes.

Read-only stand status uses direct SSH with BatchMode, one15s connection attempt,
ProxyCommand=none and ProxyJump=none. A fixed Python script reads current boot,
native process comm names, root isolation, S180 cgroup presence, original journal
hash and filesystem availability. It performs no MSR/systemd write or data copy.
