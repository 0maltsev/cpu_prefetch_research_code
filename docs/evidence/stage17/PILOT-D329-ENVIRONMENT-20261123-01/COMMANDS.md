# D329 verification commands

Use the recorded provisioned dependencies without fetching packages. The user/
PID namespaces below isolate software fixtures from the host supervisor. They
do not connect to the stand or change host cgroups/systemd/MSRs.

```sh
export PATH="$PWD/build/ext007-toolchain-20261101/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/build/ext007-toolchain-20261101/root/usr/lib"
export PYTHONPATH="$PWD/tools:$PWD/tests:$PWD/build/ext007-toolchain-20261101/python/lib/python3.14/site-packages"
cmake -S . -B build/stage17-s180-native/dev-gcc16
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_environment_v1.py -v
PYTHONMALLOC=debug unshare --user --map-root-user --pid --fork --mount-proc setsid \
  python3 -X dev -B tests/test_stage17_s180_launcher_v1.py \
  --encoder build/stage17-s180-native/dev-gcc16/cpu_prefetch_stage17_archive_encoder \
  --endpoint build/stage17-s180-native/dev-gcc16/cpu_prefetch_s180_launcher_fixture \
  --describer build/stage17-s180-release-34247ce/cpu_prefetch_runner
unshare --user --map-root-user --pid --fork --mount-proc setsid \
  ctest --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure -j2 \
  -R '^runner\.s180_(environment|launcher|parent|archive_broker|archive_reservation|authority|journal|archive_channel|checkpoint|verified_sources)_v1$'
cmake --build build/stage17-s180-native/dev-gcc16 --target format-check \
  protocol-check schema-fixture-check canonical-check queue-provenance-check \
  runner-schema-check qualification-schema-check
python3 -B build/stage17-s180-operator-prep/describe-managed-packet.py
git diff --check
```

The packet script is preserved here; its build-path output duplicates were
removed after byte/hash verification against this evidence directory. It runs
only the frozen native read-only layout command and codec compressBound; it
does not allocate original sources, compress observations or start a window.
The original full180 control metadata and prior hardware reference are retained
in D326's evidence directory. Original blueprint/identity files are unchanged.

AST checks cover both changed modules/tests and the unchanged frozen core.
Size/SHA checks verify the frozen6151832-byte native image, exact23863-byte core,
clean detached native source checkout, unchanged protocol/C++/source identities
and base D233 custody. Log-normalization records original and retained hashes;
only trailing whitespace/newline normalization is applied to text logs. Initial
placement failures are retained independently of passing final logs.

The read-only stand observation records actual file metadata/hash, current
boot/online CPUs, root cpuset controls, apt unit states, Python executable and
filesystem free bytes. It performs no qualification or hardware/system changes.
