# D327 verification commands

Use already provisioned dependencies; no downloads or stand commands. Existing
namespace requirements are unchanged. The managed boundary and ordinary host
supervisor diagnostics are retained; successful IPC tests run outside the
managed restriction inside a new user/PID namespace, without host sudo.

```sh
export PATH="$PWD/build/ext007-toolchain-20261101/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/build/ext007-toolchain-20261101/root/usr/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
cmake -S . -B build/stage17-s180-native/dev-gcc16
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure -j2 \
  -R '^runner\.s180_(parent|archive_broker|archive_reservation|authority|journal|archive_channel|checkpoint)_v1$'
cmake --build build/stage17-s180-native/dev-gcc16 --target \
  format-check protocol-check schema-fixture-check canonical-check \
  queue-provenance-check runner-schema-check qualification-schema-check
```

The standalone parent run used the same actual two native fixture paths:

```sh
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -B tests/test_stage17_s180_parent_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --channel-fixture build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_channel_fixture -v -f
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_parent_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --channel-fixture build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_channel_fixture
```

The final12-case source adds an explicit foreign-programme guard to the prior
11-case pass. Final registered and debug-mode evidence uses this final source.
The original archive fixture now declares its existing90s archive allowance in
its synthetic capture budget so the new parent can enforce the same bound;
all19 original/reserved broker cases pass unchanged in behavior.

Only the test-only channel endpoint and accepted encoder run. The production
measurement CLI is never invoked. Native frozen-image preservation, AST syntax,
evidence bindings, whitespace and scoped PC fixture cleanup are checked before
the authorized local commit. Stand evidence and original calibration are untouched.
