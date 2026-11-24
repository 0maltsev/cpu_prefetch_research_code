# D323 local verification

Direct suite, first nine cases, expanded failed fixture case, then13 passes:

```sh
PYTHONPATH=tools:tests:build/ext007-toolchain-20261101/python/lib/python3.14/site-packages \
python3 -B tests/test_stage17_s180_source_provenance_v1.py
```

Final14-case S180 suite plus the two existing related suites:

```sh
build/ext007-toolchain-20261101/root/usr/bin/ctest \
  --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure \
  -R '^runner\.(s180_(source_provenance|plan_prepare)_v1|q16c_schedule_provenance_v2)$'
```

The invocation prepended the partial toolchain's root/usr/bin to PATH, used its
root/usr/lib as LD_LIBRARY_PATH and set PYTHONPATH to absolute tools, tests and
the pinned schema-dependency directory. Three suites/20 cases passed, exit0.
The complete run took86.856seconds on the PC; this is not a stand timing estimate.

Repository checks, same partial toolchain and pinned schema dependencies:

```sh
build/ext007-toolchain-20261101/root/usr/bin/cmake \
  --build build/stage17-s180-native/dev-gcc16 --target \
  format-check protocol-check schema-fixture-check canonical-check \
  queue-provenance-check runner-schema-check qualification-schema-check
```

All passed, exit0. Final AST/whitespace/native preservation/original-source
hashes and owned temporary-fixture cleanup are recorded in final-checks.json.
No command contacts or measures the stand. No native rebuild or qualification
was initiated by this change.
