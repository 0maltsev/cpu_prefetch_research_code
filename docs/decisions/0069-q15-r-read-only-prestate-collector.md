# ADR-0069: Use one fixed read-only stand-prestate collector

- Status: `ACCEPTED_AND_IMPLEMENTED_REPOSITORY_LOCAL_NO_EXECUTION_AUTHORITY`
- Decision ID: D-069
- Accepted by: Q15-R-P4-D on 2026-08-25
- Classification: platform-evidence engineering
- Owners: platform, security, and audit owners
- Lifecycle gate: local verification before a separately approved Q15-R-P4-R
- Supersedes: the unresolved prestate acquisition method after ADR-0064

## Decision

Use `Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1`: 25 exact absolute argv
commands, a fixed `C`/UTC environment, no shell/glob/inherited environment,
30-second per-command timeout, 900-second external watchdog, bounded outputs,
no retry, stop-first-failure, and canonical partial retention. The commands
only observe kernel/host identity, roles, accepted setup paths and executable
metadata/hashes, mounts, and filesystem space. Missing objects are evidence.

Manual shell collection, a mutating/fixing collector, arbitrary commands or
paths, and remaining blocked were considered. The fixed method is selected.
The artifact retains exact argv, UTC boundaries, complete stdout/stderr bytes
as lowercase hex, exit status, source/release/authorization/contract/binary
bindings, and zero-self SHA-256. Its custody workflow creates the sidecar; the
collector itself emits canonical stdout and creates no path.

Scientific effect is none: prestate is eligibility evidence and cannot freeze
scientific values. Compatibility effect binds every command, limit, encoding,
binary/source/release/contract hash, stand ID, timestamp, raw output, and
artifact hash. The collector-bearing no-authority bundle is a versioned v3
successor; existing v1/v2 bundles keep their original verification contract.

## Authority and supersession

Local implementation, fake tests, sanitizers, and no-authority packaging are
authorized. Stand access and collector execution require a separate exact
Q15-R-P4-R. Any command, path, environment, limit, encoding, or failure-policy
change requires a new contract/ADR, clean release, and fresh prospectively
authorized evidence; stale evidence remains retained but ineligible.
