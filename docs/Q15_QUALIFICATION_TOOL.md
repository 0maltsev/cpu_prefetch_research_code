# Q15 qualification-tool boundary

Status: **`D052_CONTRACT_FROZEN; CLEAN_NO_AUTHORITY_RELEASE_SEAL_AUTHORIZED`**

Protocol: `2.0.0-pre.2`

Decision: Q15-S1 / ADR-0051

## Purpose and non-authority boundary

`cpu_prefetch_q15_tool` is separate from the sealed measurement candidate. Its
profile is `Q15-FIXED-QUALIFICATION-TOOL-v1`. Merely building, possessing,
transferring, hashing, or self-testing this executable grants no permission to
access a stand or MSR device.

The local implementation exposes only:

- a pure self-test and fixed-scope description;
- complete-value reads from MSR `0x1A4` on CPUs `0`, `1`, and `26`, after an
  exact CPUID family-06/model-55H gate;
- one-CPU H1 application from a complete three-CPU prestate using only
  `prestate | 0x0f`; and
- one-CPU complete H0 restoration, with an exact-current-value precondition.

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
failure handling. CLI self-tests and schema tests use no device operation.

## Bundle profile

The `q15-qualification-tool-bundle` target is distinct from
`pilot-candidate-bundle`. Its manifest:

- contains no `cpu_prefetch_runner` measurement executable;
- binds the qualification-tool profile and hardware-prefetch mapping;
- sets dynamic qualification, MSR read, MSR write, scientific-schedule access,
  measurement command, pilot, and confirmatory authority to `false`;
- includes source/build provenance, schemas, blocked Q15-R/Q15-W preparation
  records, no-license notice/SBOM, internal SHA-256 inventory, and outer
  sidecar; and
- refuses dirty source and append-only overwrite.

A clean archive is sealable only from the single authorized D-052/Q15-S1
revision after all repository checks pass. ADR-0052 freezes the exact regular-
stream, pointer-dependent, and seven-collector contract in
`config/q15/q15-probe-collector-contract-v1.json`. The bundle carries and
hash-binds that contract, but it does not carry collector/probe executables and
grants no dynamic authority. Those implementations, generated-code evidence,
hashes, and exact prospective commands remain later Q15-R/Q15-W inputs.

## Split authorization records

`cpu-prefetch-q15-qualification-authorization/1` is the only prospective Q15
authority format after ADR-0051. It has distinct `Q15_R_READ_ONLY` and
`Q15_W_APPLY_PROBE_RESTORE` phases. New omnibus v2 `STAND_QUALIFICATION`
documents are rejected; historical v1/v2 schemas remain readable.

The checked preparation records are:

- `config/q15/q15-r.preparation.json`; and
- `config/q15/q15-w.preparation.json`.

They use `cpu-prefetch-q15-authorization-preparation/1`, have status
`BLOCKED_INPUTS_REQUIRED`, retain null tool-release hashes, enumerate missing
exact inputs, and set every authority flag to `false`. They cannot validate as
an authorization. Q15-W additionally remains dependent on a sealed Q15-R
authorization/evidence set and the three complete prestates.
