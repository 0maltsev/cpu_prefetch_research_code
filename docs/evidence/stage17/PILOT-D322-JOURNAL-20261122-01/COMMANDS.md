# D322 verification commands

Repository root: `/home/omaltsev/research/cpu_prefetch_research_code`.
All checks are local software verification; none contacts or measures the stand.

The direct journal suite used the frozen native image:

```sh
PYTHONPATH=tools:tests:build/ext007-toolchain-20261101/python/lib/python3.14/site-packages \
python3 -B tests/test_stage17_s180_journal_v1.py \
  --worker build/stage17-s180-release-34247ce/cpu_prefetch_runner
```

The registered suites used the existing dev tree and its native cold layout
interface. The invocation ran outside the managed local IPC restriction:

```sh
build/ext007-toolchain-20261101/root/usr/bin/ctest \
  --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure \
  -R '^runner\.s180_(journal|authority|archive_reservation|archive_channel|checkpoint)_v1$'
```

The registered invocation prepended the partial toolchain `root/usr/bin` to
PATH, used its `root/usr/lib` as LD_LIBRARY_PATH, and set PYTHONPATH to the
absolute tools, tests and pinned schema-dependency directories. Repository
checks used the same partial toolchain and pinned schema dependencies:

```sh
build/ext007-toolchain-20261101/root/usr/bin/cmake \
  --build build/stage17-s180-native/dev-gcc16 --target \
  format-check protocol-check schema-fixture-check canonical-check \
  queue-provenance-check runner-schema-check qualification-schema-check
```

Final direct suite: exit0,15 cases. Final registered suites: exit0,5 suites,
45 cases. Repository checks: exit0. Exact elapsed times and registered detailed
output are retained. Initial failed negative-test expectations are retained
separately and described in REPORT.md. Final source AST, whitespace and manifest
checks are recorded in `final-checks.json`.
