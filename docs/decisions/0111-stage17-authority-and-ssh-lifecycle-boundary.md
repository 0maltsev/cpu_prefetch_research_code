# ADR-0111: Stage 17 authority and SSH lifecycle boundary

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Decision ID: `STAGE17-AUTHORITY-AND-SSH-LIFECYCLE-BOUNDARY-v1`
- Classification: implementation/security/lifecycle boundary; no scientific effect
- Owner: repository, pilot-governance, platform, release, and custody owner
- Gate: before any future `S17-EXT-001` resolution or read-only action
- Supersedes: ADR-0110 only for future authority guarding and child ownership

## Context

Executor v4 correctly rechecked system UTC after its durable marker, but then
performed two fallible snapshot locator/seal/size/SHA-256 verifications before
calling `Popen`. An authorization could expire during those checks and still
open transport. Its transport also acquired a child before placing all pipe,
selector, read, and write operations under one cleanup boundary. An exception
after `Popen` could return to the outer executor while the SSH child remained
alive, after which failure evidence was written and sealed snapshots closed.

Both failures are engineering defects. They do not authorize a change to the
fixed observations, scientific design, stand state, or Stage 18 chronology.

## Options considered

1. Recheck the clock in the outer executor immediately before calling the
   transport helper. Rejected: Python call and helper setup would remain an
   unguarded gap before `Popen`.
2. Retain the outer clock check and accept a small race. Rejected: authority is
   fail-closed and has no permitted grace period.
3. Move every fallible preparation before a guard executed inside the
   transport helper, make `Popen` the next operation, and bind UTC expiry to a
   conservative monotonic deadline. Accepted.
4. Let `Popen` children rely on interpreter/process exit. Rejected: failure
   evidence and snapshot closure would race a live transport.
5. Give the transport exclusive process-group ownership with bounded
   termination and reap in one `finally`. Accepted.

## Decision

Future production admission uses semantic policy v7, fixed action plan v5,
authorization/supporting-contract/envelope v7, verifier v7, executor v5, and
journal runtime v4. Attempt, receipt, failure, and completion records advance
to v5, v4, v5, and v4 because their authority-deadline and child-reap
semantics change. Snapshot broker v1 and collector v2 remain unchanged and
hash-bound.

Before each transport, executor v5 completes snapshot locator, seal, size, and
SHA-256 checks, output/deadline calculation, program rendering, schema loading,
and all other preparation. The transport helper creates its selector, takes a
fresh actual system-UTC sample, checks it against the issue/expiry interval and
the preceding sample, checks the monotonic authorization deadline and global
deadline cleanup reserve, and calls `Popen` as its next operation. No hashing,
schema work, rendering, or filesystem I/O occurs between that guard and
`Popen`.

The monotonic authorization deadline is derived conservatively from the final
pre-marker UTC sample and the corresponding monotonic sample. System UTC must
remain in `[issued_at, expires_at)`, may not roll back, and the monotonic
authorization deadline must remain live. The independent 180-second global
deadline reserves bounded cleanup time. Failure before `Popen` opens no child;
failure after the durable marker retains the marker and writes typed failure
evidence.

Every transport child starts a new session and process group. Once `Popen`
succeeds, the transport layer exclusively owns that group. A single
`try/finally` covers pipe setup, nonblocking configuration, selector
registration/select, stdin writes, stdout/stderr reads, timeout, cancellation,
and output limits. Any non-normal path sends bounded `SIGTERM`, escalates to
`SIGKILL`, and reaps before returning or raising. Repeated `Popen.wait`
timeouts fall back to `waitpid` reaping after `SIGKILL`. The global deadline
reserves the bounded TERM/KILL phase. If that reserve is exhausted, a final
blocking reap barrier takes precedence over returning with a live child; the
deadline overrun is itself retained as cleanup failure evidence and cannot
authorize more work. Cleanup errors are recorded alongside, and never replace,
the primary typed reason. Failure or receipt writing and snapshot closure occur
only after confirmed child reap.

No PID or credential bytes are serialized. The fixed argv, `shell=False`, six
ordered observations, stop-first, one attempt, zero retry, durable marker,
partial retention, and Stage 18 denial remain unchanged. Markers from v1
through v5 all block replay.

## Scientific and compatibility effect

Scientific effect: none. Queue, schedule, observation, measurement, and
analysis semantics are unchanged.

Compatibility effect: future `S17-EXT-001` evidence must use the v7/v5/v4
closure. Policies v1 through v6, plans v1 through v4, executor v1 through v4,
verifier v3 through v6, journal runtimes v1 through v3, record schemas and
drafts, ADR-0104 through ADR-0110, protocol snapshots, journal snapshots, and
D-099 through D-108 remain byte-identical and readable under their own
versions. They are not current action authority.

## Authority boundary

This ADR authorizes repository-local implementation and synthetic/local-
process verification only. It creates no authorization, resolution,
transition, evidence, credential, stand access, preflight, qualification,
calibration, pilot, measurement, or Stage 18 authority.
