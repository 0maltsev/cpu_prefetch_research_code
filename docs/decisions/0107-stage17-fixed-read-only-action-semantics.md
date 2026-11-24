# ADR-0107: Fixed read-only action semantics and transition-gated admission

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-26
- Decision ID: `STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v3`
- Classification: operational action semantics, one-shot execution, and
  evidence admission
- Decision owners: repository, pilot, platform, release, custody, and audit
  owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: ADR-0106 only for future `S17-EXT-001` semantic admission and
  action readiness; v1/v2 definitions and evidence remain immutable
- Lifecycle gate: before any new Stage 17 read-only preflight

## Context

Policy v2 proved file identities but still let an owner provide arbitrary
argv, stdin, remote-command, executable, and output-locator bytes. It also
treated an admitted resolution as action-ready before the graph transition,
accepted non-OpenSSH-shaped host-key bytes, and did not bind its verifier and
action implementations. Consequently a mutation command could pass a nominal
read-only authorization.

The accepted D-100 transport boundary and stand runbook already define the
required safe operations: fixed-token OpenSSH transport, exact archive and
sidecar verification, internal bundle verification, nonprivileged self-tests,
runtime identity observation, and inventory. No scientific choice is needed
to narrow the implementation to those existing requirements.

## Decision

Future `S17-EXT-001` evidence uses semantic-admission policy v3, envelope v3,
authorization v3, supporting contract v3, and the immutable
`STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v1`. Owner-controlled command,
argv, or stdin bytes do not exist in the v3 schemas. The owner may provide
only typed target, custody locator, capture identity/time, evidence-root,
actor, and authorization-window values. The repository-owned collector
deterministically renders stdin for the six fixed observations.

Policy v3 hash-binds policy v2, ADR-0106, every v3 schema, the fixed action
plan, the separate production semantic verifier, and the separate prospective
executor and collector implementations. The split avoids a self-hash cycle.
Any byte drift makes admission fail closed and requires a versioned successor.

The executor uses local `shell=False`, the exact pinned OpenSSH option profile,
one fixed remote token string, one attempt per observation, zero retries,
bounded output/time, stop-first behavior, and append-only partial retention.
The accepted D-100 remote login-shell boundary remains present only for the
fixed token string and contains no owner data or shell metacharacters. A
create-exclusive local attempt marker is written before the first transport
call. No production API accepts a transport implementation or fake backend;
tests may monkeypatch the internal call only from test code.

The single owner-supplied evidence root must preexist as a normalized,
nonsymlink directory outside the repository and outside `/etc`, `/proc`, and
`/sys`. Every output path is a repository-fixed child name. Prospective
executor and collector execution files must be nonsymlink executable regular
files byte-identical to their policy-bound repository sources.

Pinned host-key evidence must decode as the OpenSSH wire encoding of exactly
two length-prefixed fields: `ssh-ed25519` and a 32-byte public key, with no
trailing bytes. Its SHA-256 fingerprint covers the complete wire blob, and an
exact single-line known-hosts file is hash-bound separately.

`action_ready=true` for `S17-EXT-001` requires the admitted resolution, exact
transition 1, computed state `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, an explicit
live `as_of_utc`, no prior attempt marker or outputs, and fresh verification of
all policy, schema, plan, contract, authorization, host-key, and prospective
executable bytes. `PREPARED`, a later state, expiry, drift, or a marker returns
fail closed. A preflight cannot be repeated or inherited by a later state.

## Evidence

- Baseline reproduction accepted `/usr/bin/touch /tmp/STAGE17-MUTATION`, an
  `/etc` output, non-executable arbitrary implementation bytes, and
  `PREPARED / transition_count=0 / action_ready=true`.
- Disk-backed positive fixtures use only the fixed plan, executable copies of
  the repository implementations, and a structurally valid synthetic Ed25519
  wire blob; they grant no real authority.
- Negative fixtures cover mutating/shell/sudo/redirect/pipe/substitution
  command attempts, arbitrary argv/stdin, identity/hash/mode drift, unsafe
  roots, malformed host keys, policy/schema/plan/verifier drift, missing
  transition, expiry, and one-shot replay after partial failure.

## Scientific and compatibility effects

Scientific effect: none. No queue, workload, schedule, timestamp, calibration,
pilot value, treatment, estimand, or Stage 18 access rule changes.

Compatibility effect: v1/v2 definitions remain readable and hash-identical,
but future v1/v2 `S17-EXT-001` evidence is not action-admissible under v3. The
graph, catalog, genesis, journal format, historical snapshots, ADR-0104 through
ADR-0106, and D-099 through D-108 remain unchanged.

## Rollback or supersession

Never rewrite a predecessor definition or evidence record. Any command,
environment, timeout, output, executable, target, host-key, attempt, or
authority change requires a new prospective policy, plan, schema, and ADR with
complete hash lineage. Stage 18 chronology cannot be weakened by an
engineering successor.

## Protocol-amendment assessment

No protocol amendment is required. This closes an implementation-owned
fail-open action boundary without changing scientific semantics or granting
stand, preflight, qualification, calibration, pilot, measurement, or Stage 18
authority.
