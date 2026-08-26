# ADR-0108: Stage 17 one-shot runtime and durability boundary

- **Status:** Accepted for repository-local implementation by the Stage 17A.3
  task authorization; it grants no stand, transport, preflight, calibration,
  pilot, measurement, or Stage 18 authority.
- **Decision ID:** ADR-0108
- **Classification:** implementation, security, durability, and operational
  governance; no scientific semantics change.
- **Owner:** repository and pilot owner.
- **Gate:** before any `S17-EXT-001` production action.

## Context

The immutable v3 evidence-admission successor fixed owner-controlled command
semantics, but the action boundary remained fail-open in seven ways: execution
trusted caller-selected evaluation time, OpenSSH could expand verified path
tokens, approved executable paths were not compared with loaded modules,
collector input errors could occur after the one-shot marker, post-marker
exceptions did not always produce typed failure evidence, the marker directory
was not durably synchronized, and the 180-second limit was applied only as six
independent per-command limits.

## Options considered

1. Patch the committed v1 executor and v3 verifier in place. Rejected because
   those bytes are accepted predecessor evidence and must remain immutable.
2. Treat the defects as runbook cautions. Rejected because the production
   boundary would remain fail-open and non-machine-checkable.
3. Add a versioned successor with fixed action plan v2, semantic policy v4,
   verifier v4, executor/collector v2, and typed durable action records.
   Selected.

## Decision

The v4 admission policy is a hash-bound successor to policy v3 and ADR-0107.
It binds this ADR, every new schema, fixed action plan v2, and the actual loaded
repository runtime closure. It retains the immutable graph, catalog, genesis,
resolution schema, protocol, and Stage 18 chronology.

Production execution has no caller-controlled authority time. The executor
reads actual UTC from the system clock immediately before the marker and
requires `issued_at <= actual_now < expires_at`. Explicit `as_of_utc` remains
available only to non-executing prospective/status evaluation.

OpenSSH option paths are normalized absolute paths with no whitespace,
controls, percent expansion, dollar expansion, braces, quotes, backslash,
tilde, comma, or configuration separator. Local `ssh -G` is the only permitted
OpenSSH execution in repository tests and must report the exact admitted
known-hosts and identity paths.

Action readiness requires a caller-supplied description of the actually loaded
executor, collector, verifier, journal, predecessor helper, and pilot-artifact
verifier modules. The verifier checks their real nonsymlink source paths and
bytes against policy bindings; executor and collector paths must equal the two
contract-approved execution paths.

All six programs, the exact SSH argv, fixed output names, typed inputs, hashes,
and exact second-precision capture time are validated before the marker. The
evidence root is owner-owned and not group/other writable. Execution pins it
with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, creates fixed children relative to the
directory descriptor with `O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC`, fsyncs marker
bytes, then fsyncs the parent directory before any transport call.

After the marker, every operational failure retains the marker and attempts one
create-exclusive typed failure record. No failure permits delete or retry. A
single monotonic 180-second deadline covers marker creation, transport, output
retention, receipts, and completion. Each transport receives the smaller of
30 seconds and the remaining global time.

Attempt, observation receipt, failure, and completion records bind the
authorization, resolution, transition, action plan, implementation hashes,
program and SSH argv hashes, output hashes, actual UTC timestamps, durations,
zero-retry policy, and `stage18_authority=false`.

## Scientific effect

None. The observation family, queue/measurement behavior, protocol data model,
and scientific lifecycle are unchanged. This decision only makes the
pre-pilot read-only operational boundary fail-closed and crash-aware.

## Compatibility effect

All v1/v2/v3 definitions, policies, schemas, plans, ADR-0104 through ADR-0107,
and historical evidence remain byte-identical and readable. New operational
admission requires policy v4 records and v2 runtime modules; v3 evidence cannot
silently authorize the v4 executor.

## Risks and mitigations

- System wall-clock rollback can reject otherwise valid authority; fail-closed
  rejection is intentional and requires a new prospective authorization, not a
  retry.
- Filesystem failure can prevent the typed failure record itself; the durable
  marker remains authoritative and permanently blocks a second attempt.
- OpenSSH implementations can differ; local option expansion is checked with
  the exact installed `/usr/bin/ssh -G` without making a connection.

## Supersession rule

Any change to authority time, OpenSSH argv, action programs, record schemas,
runtime bindings, directory-FD storage, durability ordering, retry policy, or
global deadline requires a new ADR, policy, plan, schemas, and implementation
versions. ADR-0108 never authorizes stand access or a later lifecycle phase.
