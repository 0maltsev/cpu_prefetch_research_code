# D325 verification and bounded stand observations

New matcher tests, final14 cases:

```sh
PYTHONPATH=tools:tests:build/ext007-toolchain-20261101/python/lib/python3.14/site-packages \
python3 -B tests/test_stage17_s180_namespace_audit_v1.py
```

Final registered suites21 cases; original Q16c direct suite3 cases, all exit0:

```sh
build/ext007-toolchain-20261101/root/usr/bin/ctest \
  --test-dir build/stage17-s180-native/dev-gcc16 --output-on-failure \
  -R '^runner\.(s180_namespace_audit_v1|service_continuation_namespace_v1)$'
PYTHONPATH=tools:tests:build/ext007-toolchain-20261101/python/lib/python3.14/site-packages \
python3 -B tests/test_stage17_q16c_namespace_audit_v1.py
```

Registered execution prepended the partial toolchain root/usr/bin to PATH,
used its root/usr/lib as LD_LIBRARY_PATH and set PYTHONPATH to absolute tools,
tests and pinned schema dependencies. Repository checks used the same prefix:

```sh
build/ext007-toolchain-20261101/root/usr/bin/cmake \
  --build build/stage17-s180-native/dev-gcc16 --target \
  format-check protocol-check schema-fixture-check canonical-check \
  queue-provenance-check runner-schema-check qualification-schema-check
```

Read-only audit calls use default finite limits:64 contexts,1024 roots,
400,000 entries,200,000 files,96MiB/file,4GiB aggregate, depth64,
10million JSON nodes/file and300seconds. No caller exclusions:

```python
audit('local', repository_root, exact_frozen_blueprint)
audit('stand', Path('/home/omaltsev/stage17-owner-evidence'), exact_frozen_blueprint)
```

The stand's tested pre-wrapper auditor and unchanged public traversal source
were sent via authorized SSH stdin and executed in ephemeral Python modules
under `python3 -B -`. Exact transported source hashes are in its report; the
pre-wrapper source snapshot/diff is retained. No code was installed, namespace
registered, payload tree entered or stand evidence changed. The historical
plan transfer used the exact retained size/hash binding and no raw observations.

The resource survey used only statvfs/meminfo/comm names and bounded public
directory names. Program extent inventory used stat operations plus small
scope metadata, not raw contents. The separately authorized software timing
loaded the unchanged generator source over stdin and timed only5000 accepted
Philox/Decimal80 transforms per load under a disjoint SOFTWARE namespace/seed.
No complete schedule, pilot input, file, affinity or hardware state was created
or changed. Reports explicitly distinguish these observations from admission.

Native/source preservation, manifest consistency, exact prospective manifest
reproduction, final AST/whitespace and duplicate-report/fixture cleanup checks
are recorded in final-checks.json and pc-cleanup.json.
