# Q15 qualification-tool boundary

Status: **`Q15_S3_CLEAN_COMPONENT_RELEASE_VERIFIED; FIXED_CONTROLLER_ABSENT; NO_AUTHORITY`**

Protocol: `2.0.0-pre.2`

Decisions: Q15-S1/Q15-S3; ADR-0051 and ADR-0054 through ADR-0056

## Purpose and non-authority boundary

`cpu_prefetch_q15_tool` is separate from the sealed measurement candidate. Its
profile is `Q15-FIXED-QUALIFICATION-TOOL-v1`. Merely building, possessing,
transferring, hashing, or self-testing this executable grants no permission to
access a stand or MSR device.

The local implementation exposes only:

- a pure self-test plus fixed and dynamic-scope descriptions;
- complete-value reads from MSR `0x1A4` on CPUs `0`, `1`, and `26`, after an
  exact CPUID family-06/model-55H gate;
- one-CPU H1 application from a complete three-CPU prestate using only
  `prestate | 0x0f`; and
- one-CPU complete H0 restoration, with an exact-current-value precondition.

The Q15-S3 build also links fixed components for the exact raw-PMU pass,
literal same-buffer phase-spanning session, and seven registered collector
kinds. Their production Linux calls remain behind fakeable seams. No
no-authority CLI command starts a session or collector; exact controller argv,
endpoint, release hashes, roles, limits, and custody are deliberately deferred
to the later clean release and Q15-R/Q15-W records.

There is no path, MSR-address, mask, CPU-list, schedule, namespace, queue,
calibration, pilot, measurement, or confirmatory selector. There is no retry or
silent fallback. Each dynamic invocation requires a syntactically valid exact
authorization SHA-256 in its argv for evidence binding, but the executable does
not claim to validate the detached signature or grant authority. The external
controller, OS role/capability boundary, and exact Q15-R/Q15-W record remain the
authority seam.

The write command deliberately does not self-verify. ADR-0051 requires a
separate auditor identity and read-only process to capture the complete
readback. Q15-W must bind each apply command to its inverse and independent
readback commands, restore successful applications in reverse order, and
quarantine the stand if restoration cannot be independently proved.
Any error after a write is attempted, including close failure, leaves the
actual state uncertain. The external controller must preserve the partial
evidence, attempt only the prospectively bound inverse under Q15-W, require
independent complete-value restoration readback, and quarantine on any
remaining uncertainty; a tool error is never proof that no mutation occurred.

## Safe repository-local commands

These commands do not open `/dev/cpu/*/msr`:

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target cpu_prefetch_q15_tool \
  cpu_prefetch_q15_tool_tests qualification-schema-check
ctest --preset dev-gcc -L q15 --output-on-failure
build/dev-gcc/cpu_prefetch_q15_tool --self-test
build/dev-gcc/cpu_prefetch_q15_tool --describe-fixed-scope
build/dev-gcc/cpu_prefetch_q15_tool --describe-dynamic-scope
cmake --build --preset dev-gcc --target q15-dynamic-implementation-check
cmake --build --preset release-gcc --target q15-runtime-codegen-check
```

Do not run a dynamic option from this document. Exact dynamic argv may appear
only in a later signed Q15-R or Q15-W authorization whose executable and bundle
hashes, stand identity, roles, targets, limits, outputs, custody, stop rules,
and validity interval are complete.

## Adapter verification

The file-operation boundary tests use in-memory fake state. They prove fixed
paths `/dev/cpu/{0,1,26}/msr`, fixed offset `0x1A4`, read-only write rejection,
CPUID decoding, exact complete-value application/restoration, stale-state
rejection, wrong-CPU rejection, broad-plan rejection, and open/read/write/close
failure handling. Q15-S3 fakes additionally prove the exact counter request and
single lifecycle, allocation-free counted region, affinity/NUMA/memory-policy
ordering, exhaustive residency/fault boundaries, same-buffer state/peer/hash/
expiry/disconnect rules, bounded canonical frames, and all seven
observation-derived collectors. CLI self-tests and schema tests use no device
operation.

## Bundle profile

The `q15-qualification-tool-bundle` target is distinct from
`pilot-candidate-bundle`. Its manifest:

- contains no `cpu_prefetch_runner` measurement executable;
- binds the qualification-tool, D-053 probe, D-054..D-056 dynamic profiles and
  hardware-prefetch mapping;
- sets dynamic qualification, MSR read, MSR write, scientific-schedule access,
  measurement command, pilot, and confirmatory authority to `false`;
- includes source/build provenance, schemas, blocked Q15-R/Q15-W preparation
  records, no-license notice/SBOM, internal SHA-256 inventory, and outer
  sidecar; and
- refuses dirty source and append-only overwrite.

The authorized clean Q15-S3 commit is
`7a9262987d4c52df95e9ed2ddc09cfa0d214b198`. Its verified no-authority archive
is `cpu-prefetch-q15-qualification-tool-2.0.0-7a92629-clean-542e64956985.tar.gz`
(4138818 bytes), SHA-256
`20acaded8002c130db725369c67013582dbcfccbd826a033a14658281387f848`.
The Q15 executable SHA-256 is
`0e0e7a9c8fb52c9540fa93bb6a9f83dafe96e26927247ee122c0a5691ef7814a`.
Its 101-file clean-extraction verification and four non-authorizing self-tests
pass. The bundle contains and hash-binds D-052 through D-056, the dynamic
profile, collector library/schema, and both strict code-generation reports.

The clean Q15-S3 v1 release intentionally exposes no production controller
command for the phase-spanning session/collectors. Q15-R-P1 subsequently
accepted D-057 through D-060 and the repository now contains the fixed
controller core and no-authority CLI. Clean commit
`a75bcdd0367d79f8ee0496c55edda74311c9ef7d` produced the verified
controller-bearing v2 archive
`cpu-prefetch-q15-qualification-tool-2.0.0-a75bcdd-clean-b4438745f3ca.tar.gz`
(4247166 bytes), SHA-256
`48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035`.
Its 118-file internal verification and five non-authorizing self-tests pass;
its manifest still grants no authority. Accepted D-061 through D-064
[`operational-prerequisite bundle`](Q15_R_OPERATIONAL_PREREQUISITE_DECISION_BUNDLE.md)
binds this release as base evidence only. The operational adapter is implemented
in the repository but not in this clean archive. Another clean operational
release, actual role/custody/trust evidence, and a later approved signed Q15-R
remain mandatory.

## Split authorization records

`cpu-prefetch-q15-qualification-authorization/1` remains the split preparation
format from ADR-0051. ADR-0057 adds
`cpu-prefetch-q15-qualification-authorization/2` for the future fixed
`Q15_R_READ_ONLY` controller: it uses a canonical core plus detached SSHSIG and
independent verification evidence. Q15-W remains separately authorized and is
not enabled by v2. Omnibus `STAND_QUALIFICATION` documents are rejected;
historical schemas remain readable.

The checked preparation records are:

- `config/q15/q15-r.preparation.json`; and
- `config/q15/q15-w.preparation.json`.

They use `cpu-prefetch-q15-authorization-preparation/1`, have status
`BLOCKED_INPUTS_REQUIRED`, retain null tool-release hashes, enumerate missing
exact inputs, and set every authority flag to `false`. They cannot validate as
an authorization. Q15-W additionally remains dependent on a sealed Q15-R
authorization/evidence set and the three complete prestates.
