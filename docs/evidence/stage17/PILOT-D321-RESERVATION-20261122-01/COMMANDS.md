# Verification commands

Use existing provisioned dependencies; no downloads:

```sh
export S180_TOOLS="$PWD/build/ext007-toolchain-20261101/root/usr"
export PATH="$S180_TOOLS/bin:$PATH"
export LD_LIBRARY_PATH="$S180_TOOLS/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
python3 -B tests/test_stage17_s180_archive_reservation_v1.py
python3 -B tests/test_stage17_s180_authority_v1.py \
  --worker build/stage17-s180-release-34247ce/cpu_prefetch_runner
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -B tests/test_stage17_s180_archive_broker_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --channel-fixture build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_channel_fixture
# The additional drift case was added after the combined18-case pass and run alone:
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -B tests/test_stage17_s180_archive_broker_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --channel-fixture build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_channel_fixture \
  ReservedS180BrokerTests.test_changed_admission_blocks_retained_custody_verification
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check protocol-check \
  schema-fixture-check canonical-check queue-provenance-check runner-schema-check qualification-schema-check
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  "$S180_TOOLS/bin/ctest" --test-dir build/stage17-s180-native/dev-gcc16 \
  --output-on-failure -j2 \
  -R '^runner\.(s180_(archive_reservation|authority|archive_channel|checkpoint)_v1|formal_archive_(custody|runtime|broker|jobs|registry)_v1|formal_checkpoint_v1|archive_channel_v1)$'
```

The initial combined broker invocation had18 cases. Current full invocations
include the additional19th case. The native test fixtures and supervisor run
outside the managed IPC restriction, inside a user/PID namespace; no stand or
host sudo is involved. Filesystem fixtures use the real repository build disk
because /tmp has less than the unchanged16GiB reserve.

The original81c4838 S180 store was read through `git show`, compiled into an
isolated local module and given explicit unknown EXT009. Its SHA/typed stop is
retained in`s180-reservation-original-stop.json`. AST parsing, the exact unchanged
D233 base bytes, no C++/protocol diff and unchanged native SHA were also checked.
`git diff --check` is required before the local commit. There were no stand commands.
