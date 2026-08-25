# Q15-R stand-prestate collector

Status: `IMPLEMENTED_REPOSITORY_LOCAL_NO_EXECUTION_AUTHORITY`

Q15-R-P4-D and ADR-0069 accept
`Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1`. The implementation provides a
fakeable executor/clock seam and a system executor, but repository verification
uses only fake evidence and the two non-executing CLI modes. Merely building or
packaging the executable grants no authority to run it.

## Fixed scope

The contract contains 25 ordered commands, `P4R-001` through `P4R-025`. Each
uses an absolute executable and literal argv. There is no shell, glob, inherited
environment, arbitrary path, network operation, account/key/path mutation,
access probe, PMU/MSR access, affinity/NUMA control, calibration, pilot,
measurement, or confirmatory operation. The environment is exactly `LANG=C`,
`LC_ALL=C`, and `TZ=UTC0`.

The commands observe the kernel and hostname; the accepted group and four
principal names; accepted setup executable metadata and hashes; `/dev/md3` and
the accepted primary/trust path metadata; mounts; filesystem space; and
collector-tool metadata. Exit status 2 for absent `getent` entries and status 1
for absent metadata/mount/space targets are retained as accepted observations.
Absence is evidence and never causes creation or repair.

Each command has separate 1 MiB stdout and stderr bounds and a 30-second
timeout. The complete capture is bounded to 16 MiB and the canonical artifact
to 64 MiB. The separately imposed total watchdog is 900 seconds. There are zero
retries. The first rejected command stops collection and produces a canonical
partial artifact.

## Artifact and integrity contract

Every observation retains command ID and kind, exact argv, UTC start/end,
launch and timeout states, exit or signal status, capture errors, acceptance,
and complete stdout/stderr bytes encoded as lowercase hex. The artifact binds
the opaque capture ID, exact authorization and collector-binary SHA-256 values,
the frozen contract SHA-256, full source revision, D-065 release archive,
protocol version, and stand ID.

Serialization uses `JCS-I64-v1`. `artifact_sha256` is SHA-256 over canonical
bytes with that field set to 64 zeroes. An authorized custody wrapper must
write the canonical stdout and detached sidecar to the exact destinations in a
later Q15-R-P4-R; the collector itself creates no file or directory.

`validate_q15_r_prestate.py` is the offline, read-only artifact validator. It
rejects duplicate JSON members, noncanonical bytes, schema/version/hash drift,
an inexact command prefix, forged acceptance or failure state, bound overflow,
continued collection after failure, and a mismatched zero-self SHA-256. The
no-authority qualification-tool bundle binds the validator's own SHA-256.
That successor uses `Q15-QUALIFICATION-TOOL-BUNDLE-v3`; historical v1/v2
profiles remain verifiable under their original requirements.

## Authority gates

[`q15-r-p4-r.preparation.json`](../config/q15/q15-r-p4-r.preparation.json)
contains the exact invocation shape but has eight null inputs and is
`NOT_ISSUED`. A clean collector-bearing release, exact stand and time binding,
named authority, literal custody destinations, detached signature, independent
review, and separate explicit approval are required before any collection.

[`q15-r-p4-k.preparation.json`](../config/q15/q15-r-p4-k.preparation.json) is a
separate blocked record for the offline signer/custody action. It cannot be
combined with P4-R. Neither preparation authorizes stand access, transfer,
installation, filesystem mutation, keys, setup, access probes, Q15-R/Q15-W,
platform controls, calibration, pilot, measurement, or confirmatory work.

## Safe repository-local verification

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target cpu_prefetch_q15_prestate_tests cpu_prefetch_q15_prestate_collector
ctest --test-dir build/dev-gcc --output-on-failure -R '^Q15StandPrestate\\.|^q15\\.prestate_collector_'
cmake --build --preset dev-gcc --target q15-r-p4-d-implementation-check
./build/dev-gcc/cpu_prefetch_q15_prestate_collector --self-test
./build/dev-gcc/cpu_prefetch_q15_prestate_collector --describe-contract
```

These commands do not call `--collect`. The real collection entry remains
closed until a later exact signed Q15-R-P4-R is issued and explicitly approved.
After such an authorization produces a custody artifact, its runbook must bind
the validator to the exact artifact, contract, and schema paths. No executable
validator invocation is valid while those literal custody paths remain null.
