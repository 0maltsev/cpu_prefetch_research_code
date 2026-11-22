# D324 local verification commands

Direct suite (10, then13, then14 cases as coverage was added; all pass):

```sh
PYTHONPATH=tools:tests:build/ext007-toolchain-20261101/python/lib/python3.14/site-packages \
python3 -B tests/test_stage17_s180_verified_sources_v1.py
```

Four related registered suites,46 cases, exit0:

```sh
build/ext007-toolchain-20261101/root/usr/bin/ctest \
  --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure \
  -R '^runner\.s180_(verified_sources|source_provenance|plan_prepare|journal)_v1$'
```

The command prepended the partial toolchain root/usr/bin to PATH, set its
root/usr/lib as LD_LIBRARY_PATH and used absolute tools, tests and pinned
schema-dependency directories as PYTHONPATH. Exact elapsed times and detailed
case counts are retained. These local times are not a stand estimate.

Repository checks use the same partial toolchain and pinned schema dependencies:

```sh
build/ext007-toolchain-20261101/root/usr/bin/cmake \
  --build build/stage17-s180-native/dev-gcc16 --target \
  format-check protocol-check schema-fixture-check canonical-check \
  queue-provenance-check runner-schema-check qualification-schema-check
```

All pass, exit0. Final AST/whitespace/unchanged-source/native preservation and
owned temporary-fixture cleanup are recorded in final-checks.json. No command
contacts or measures the stand, rebuilds the native worker or revalidates raw
research observations.
