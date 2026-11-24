# ADR-0110: Stage 17 OpenSSH-consumed snapshot locator

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Decision ID: `STAGE17-OPENSSH-CONSUMED-SNAPSHOT-LOCATOR-v1`
- Classification: implementation/security boundary; no scientific effect
- Owner: repository, pilot-governance, platform, release, and custody owner
- Gate: before any future `S17-EXT-001` resolution or read-only action
- Supersedes: ADR-0109 only for future credential-consumption admission

## Context

ADR-0109 correctly sealed the exact known-hosts and transport-identity bytes,
but executor v3 passed their descriptors to `/usr/bin/ssh` and named them as
`/proc/self/fd/N`. A real local OpenSSH characterization demonstrates that
OpenSSH performs descriptor hygiene equivalent to `closefrom(3)` early in
`main()`. On the development host, inherited memfd 3 was absent and inherited
memfd 4 had been reused as a proxy pipe when a local post-hygiene observer ran.
The previous `ssh -G`, mocked transport, and generic Python-child checks did
not cross this OpenSSH-specific consumption boundary.

The experiment protocol does not select an engineering locator. The choice
must preserve exact bytes, fail closed before the one-shot marker when the
local platform cannot support it, and grant no stand or later-phase authority.

## Options considered

1. Continue `/proc/self/fd/N` plus `pass_fds`. Rejected: OpenSSH closes or
   reuses those descriptors before consuming either configured file.
2. Recreate immutable temporary pathname files. Rejected: ordinary files do
   not provide an equivalent kernel-enforced immutability guarantee and add
   cleanup/replacement races.
3. Hold sealed memfds in the executor and name them through the executor's
   procfs-visible process directory. Accepted: OpenSSH may close all of its own
   descriptors while reopening exact sealed bytes from the live parent.
4. Stop permanently. Rejected because option 3 is demonstrable locally with
   actual OpenSSH and has an explicit fail-closed capability boundary.

## Decision

Future production admission uses semantic policy v6, fixed action plan v4,
authorization/supporting-contract/envelope v6, verifier v6, executor v4, and
journal runtime v3. Attempt, receipt, failure, and completion records advance
to v4, v3, v4, and v3 respectively. The latter three successors bind the v4
attempt marker, twelve-member runtime closure, consumed credential hashes, and
local OpenSSH capability-report hash. Collector v2 remains unchanged and
hash-bound.

Executor v4 opens and verifies each owner source exactly once before the
marker, copies the exact bytes to an anonymous memfd, sets mode `0600`, and
requires `F_SEAL_WRITE`, `F_SEAL_GROW`, `F_SEAL_SHRINK`, and `F_SEAL_SEAL`.
It discovers the PID visible in the mounted procfs from the numeric target of
`/proc/self`, never by assuming that `os.getpid()` has the same namespace
value. It names a snapshot as `/proc/<procfs-visible-parent>/fd/N` and keeps
the descriptor open until the SSH child has terminated. No credential
descriptor is inherited by the child.

Before marker creation the executor verifies:

- `/proc/self` and the selected parent process directory identify the same
  live process directory;
- the reopened locator is a regular file owned by the executor, has the same
  device/inode, mode, size, seals, bytes, and SHA-256 as the snapshot;
- the local OpenSSH suite can consume disposable synthetic Ed25519 host and
  client snapshots through this locator after its own descriptor hygiene;
- the exact owner identity snapshot is parseable without disclosing private
  bytes, and the exact known-hosts snapshot remains structurally bound;
- no predecessor or current one-shot marker/output exists.

The capability test uses `/usr/bin/ssh` and `/usr/sbin/sshd -i` connected only
by a local `ProxyCommand` pipe. It creates disposable synthetic keys in a
private temporary directory, mutates their source files after snapshotting,
and requires successful public-key authentication and strict host-key
verification. It opens no socket and contacts no network or stand. Missing or
denied procfs, missing local tools, unsafe locator identity, parse failure, or
any capability mismatch blocks before marker and transport.

All potentially slow capability, semantic, hash, render, compile, and schema
work still completes before the final actual-UTC sample. The second actual-UTC
sample remains after durable marker creation and immediately before first
transport. Expiry, not-yet-valid authority, or rollback at that boundary
retains a typed failure and opens no transport. The single 180-second
monotonic deadline, create-exclusive file and parent fsync, six observations,
`shell=False`, stop-first, partial retention, one attempt, zero retries, and
Stage 18 denial remain unchanged.

Executor v4 admits only policy-v6 evidence. Executor v3 remains byte-immutable
and cannot admit a v6 envelope. Every attempt marker from v1 through v4 blocks
future action readiness, so a version change cannot reset one-shot state.

## Scientific and compatibility effect

Scientific effect: none. Queue, schedule, observation, measurement, and
analysis semantics are unchanged. The change only makes the already selected
read-only transport consume the bytes that admission verified.

Compatibility effect: future `S17-EXT-001` evidence must use the v6/v4/v3
closure. Every v1-v5 policy/schema/plan/runtime predecessor, ADR-0104 through
ADR-0109, protocol snapshot, journal snapshot, and D-099 through D-108 record
remains byte-identical and readable under its own version. None is current
production authority.

## Authority boundary

This ADR authorizes repository-local implementation and synthetic/local-pipe
verification only. It creates no authorization, resolution, transition,
evidence, credential, stand access, qualification, calibration, pilot,
measurement, or Stage 18 authority.
