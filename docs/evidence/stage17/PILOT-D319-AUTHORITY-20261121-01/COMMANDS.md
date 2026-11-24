# Verification commands

Use the existing local dependencies, without network fetches:

```sh
export S180_TOOLCHAIN="$PWD/build/ext007-toolchain-20261101/root/usr"
export PATH="$S180_TOOLCHAIN/bin:$PATH"
export LD_LIBRARY_PATH="$S180_TOOLCHAIN/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
python3 -B tests/test_stage17_s180_authority_v1.py \
  --worker build/stage17-s180-native/dev-gcc16/cpu_prefetch_runner
cmake --build build/stage17-s180-native/dev-gcc16 --target \
  cpu_prefetch_runner cpu_prefetch_s180_io_tests format-check protocol-check \
  schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check -j2
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  "$S180_TOOLCHAIN/bin/ctest" --test-dir build/stage17-s180-native/dev-gcc16 \
  --output-on-failure -j2 \
  -R '^runner\.(s180\.|s180_|archive_channel\.|archive_channel_v1$|formal_archive_(custody_v1|runtime_v1|broker_v1|jobs_v1)$|formal_checkpoint_v1$)'
# Fresh schema check after final opaque-ID grammar alignment:
cmake --build build/stage17-s180-native/dev-gcc16 --target protocol-check
```

The unchanged supervisor tests use an isolated user/PID namespace for procfs
inspection; host sudo is unnecessary. The authority suite needs actual local
`/usr/bin/ssh-keygen` and creates/removes only temporary test-only keys.
AST parsing of both new Python files and `git diff --check` also passed.
No stand command or scientific measurement was executed.
