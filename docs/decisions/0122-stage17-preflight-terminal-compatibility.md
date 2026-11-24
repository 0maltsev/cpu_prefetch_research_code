# ADR-0122: Stage 17 preflight capability quiescence and terminal compatibility

- **Status:** `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- **Decision ID:** D-122
- **Classification:** implementation correctness, process lifecycle, evidence
  retention, and operational compatibility
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any replacement `S17-EXT-001` transaction

## Context

The first policy-v12 action created its durable attempt-v8 marker and then
stopped before `Popen`.  The real local pipe-only OpenSSH capability proof had
left two short-lived `sshd` descendants adopted by the executor acting as PID
1.  The later `SupervisorLease.enter()` correctly rejected the unexpected
children with `PROCESS_SUPERVISOR_SETUP_FAILURE`.  No SSH transport or remote
observation occurred.

The failure could not be retained: attempt v8 admitted the exact twenty
policy-v12 runtime identities, but receipt v5, failure v6, fallback v1, and
completion v5 still admitted only seventeen.  Both full and fallback failure
validation therefore rejected the executor's actual twenty-key closure.  The
marker remains append-only and blocks reuse of that transaction.

## Decision

Preserve the policy-v12 authorization, resolution, transition, attempt marker,
and marker-only output root.  Admit a replacement transaction only through a
typed post-marker blocker that rehashes those bytes, records the observed
pre-transport supervisor failure, proves the output root still contains only
the marker, denies retry, and requires a new authorization and attempt ID.

Policy v13 and executor v11 bind:

- a v2 OpenSSH snapshot broker that enters subreaper mode before the local
  OpenSSH capability fixture and establishes an adopted-child reap barrier
  before returning;
- the unchanged six read-only operations and effective action plan v6;
- successor action plan v8, which changes only the capability/terminal
  evidence boundary;
- an exact named twenty-two-key runtime closure, including the immutable v1
  snapshot broker and v12 verifier helpers actually imported; and
- attempt v9, receipt v6, failure v7, failure-retention v2, and completion v6,
  all accepting exactly the same named runtime closure.

OpenSSH capability or child-quiescence failure occurs before the marker.  Any
post-marker operational failure must validate against the full terminal schema
or the typed fallback; failure to retain both remains a surfaced error rather
than a silent success.  All cross-version markers block reuse.

## Effects

There is no scientific effect and no new stand, control, calibration, pilot,
or Phase 18 authority.  The compatibility effect is fail-closed.  The
policy-v12 transaction is not retried.  A separately issued finite
authorization may create one replacement read-only transaction only after its
two predecessor blocker receipts and exact bytes are admitted.

## Verification and supersession

Acceptance requires real local OpenSSH/sshd pipe characterization showing the
v1 adopted-child leak, v2 quiescence followed by a successful supervisor
lease, exact-set positive/negative validation for every terminal record,
post-marker blocker lineage tests, all prior Stage 17 regressions, and a clean
verified candidate bundle.  Any later change to action semantics, authority,
runtime closure, process ownership, or record shape requires a prospective
versioned successor; scientific changes require a protocol amendment.
