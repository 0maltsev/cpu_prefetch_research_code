# D330 commands

No fetch/install, native rebuild, stand connection or measurement command.
Use the existing provisioned prefixes; omitting PYTHONPATH selects the host's
unaccepted rpds-py version and is preserved as the initial check failure.

```sh
export PATH="$PWD/build/ext007-toolchain-20261101/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/build/ext007-toolchain-20261101/root/usr/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
cmake -S . -B build/stage17-s180-native/dev-gcc16
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_archive_bundle_profile_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder -v
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure -j2 \
  -R '^runner\.(archive_bundle_profile_v1|formal_archive_runtime_v1|formal_archive_broker_v1|s180_(archive_bundle_profile|archive_broker|archive_reservation|parent|launcher|environment|authority|journal)_v1)$'
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check
git diff --check
```

The isolated software suites use the real procfs supervisor, IPC credentials and
codec processes. New profile tests use a software fixture license and interpreter
image; these fixture files are not distributed or promoted to stand evidence.
The later clean component uses the recorded actual license/runtime and existing
release encoder. Its source revision is separate from the frozen native worker.
The package CLI can only assemble a cold archive component; there is no hardware,
native-worker launch, schedule generation, qualification or retry command.

AST and preservation checks cover all changed Python files, unchanged original
archive profile/materializer/runtime/custody, frozen core, native source/protocol,
approved blueprint and identity manifest. Text-log retention normalizes trailing
whitespace/EOF only and records original hashes. Initial failures remain visible.
