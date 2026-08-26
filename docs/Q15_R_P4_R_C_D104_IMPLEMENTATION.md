# Q15-R P4-R-C D-104 implementation record

Status: **`IMPLEMENTED_LOCAL_NO_ACTION_AUTHORITY_BLOCKED_ON_REMOTE_RUNTIME_IDENTITY`**

This record implements the repository-local scope accepted for D-100 through
D-103. It is not an action authorization and contains no signature or stand
evidence.

## Fixed implementation

`tools/execute_d104_p4_r_c.py` provides only four modes:

- `--self-test`, which uses a fake backend and no network;
- `--describe-contract`, which emits the canonical 13-step contract;
- `--execute`, which is dormant behind exact authorization, signature,
  pre-execution review, local input, expiry, and remote-runtime gates; and
- `--review-result`, which is a separate local append-only result review.

The transport uses local `shell=False`, pinned OpenSSH options, a strict
allowlist of five fixed command families, one attempt per identifier, bounded
thread-drained stdout/stderr, and zero retry. Fixed remote Python programs run
under an empty `LANG=C`, `LC_ALL=C`, `TZ=UTC0` environment and use explicit
runtime checks, never disableable assertions. Archive/sidecar upload uses
create-exclusive `dd`; extraction rejects unsafe/duplicate members, does not
preserve archive owner/mode, restores only the exact collector to root-owned
mode `0700`, and verifies internal hashes before execution.

The exact D-099 five-file custody root is the only allowed predecessor state.
Collector stdout, stderr, sidecar, receipt, review, and failure paths must all
be absent. Collection and review are separate operations. Failure records
retain bounded remote output as lowercase hex plus hashes, forbid retry and
cleanup, and never fabricate a collector artifact.

## Verification commands

```sh
cmake --preset dev-gcc
cmake --build --preset dev-gcc --target \
  q15-r-p4-r-c-d104-implementation-check protocol-check
ctest --preset dev-gcc -R q15.p4_r_c_executor_no_network_self_test \
  --output-on-failure
```

The implementation checker validates D-100 through D-103 acceptance, all
eight D-104 schemas/templates, exact source/input hashes, six authority/schema
mutations, synthetic success/failure envelopes, the complete fake graph, every
remote stop point, corruption and semantic mutants, create-exclusive behavior,
forbidden shell commands, and the still-null action/runtime inputs.

## Mandatory stop and next gate

D-102 makes tool bytes compatibility identity. D-099 did not capture the
stand's `/usr/bin/env`, `/usr/bin/python3`, `/usr/bin/dd`, Python standard
library/tar runtime, or their dependency identity. Consequently
`REMOTE_RUNTIME_ACCEPTANCE_SHA256` is `None`, and even a syntactically issued
authorization stops before signature verification or transport creation.

The next safe step is a prospective, separately signed and approved read-only
runtime-evidence acquisition and review. After its immutable evidence is
accepted, a clean successor may bind those bytes and prepare an exact D-104
P4-R-C action. No key use, stand access/mutation, staging, collection, P4-R-C,
P5, Q15, platform control, calibration, pilot, measurement, or confirmatory
work is authorized here.
