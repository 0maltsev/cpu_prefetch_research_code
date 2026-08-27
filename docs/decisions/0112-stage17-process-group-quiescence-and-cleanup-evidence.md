# ADR-0112: Stage 17 process-group quiescence and cleanup evidence

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Decision ID: `STAGE17-PROCESS-GROUP-QUIESCENCE-AND-CLEANUP-EVIDENCE-v1`
- Classification: implementation/security/process-lifecycle boundary; no scientific effect
- Owner: repository, pilot-governance, platform, release, and custody owner
- Gate: before any future `S17-EXT-001` resolution or read-only action
- Supersedes: ADR-0111 only for process-group quiescence and cleanup evidence

## Context

Executor v5 reaped a normally exited transport leader and treated that result
as proof that the transport process group was gone. A same-process-group
descendant could close or redirect all three pipes, survive the leader, and
remain alive after a successful receipt. Sending a signal after reaping the
leader would introduce a PGID-reuse race. Separately, failure schema v5
required `child_reaped=true` and did not represent the executor's reachable
cleanup-failure state. The executor suppressed failure-record validation or
retention errors and then closed credential snapshots.

These are engineering and evidence-ordering defects. They do not change the
fixed observations, experiment design, stand state, or Stage 18 chronology.

## Options considered

1. Check `killpg(pgid, 0)` after ordinary `wait()`. Rejected because leader
   reap releases the PID/PGID and permits signalling an unrelated reused group.
2. Treat pipe EOF as group completion. Rejected because descendants may close
   or redirect all inherited pipes.
3. Run every transport under a dedicated Linux subreaper, observe leader exit
   with `waitid(WNOWAIT)`, hold the zombie leader until the group is quiescent,
   terminate descendants, reap adopted children, and reap the leader last.
   Accepted.
4. Keep one failure schema that cannot express cleanup states and suppress
   retention errors. Rejected.
5. Version lifecycle evidence and add a create-exclusive typed fallback that
   preserves the primary reason plus the failure-retention reason. Accepted.

## Decision

Future production admission uses policy v8, fixed action plan v6,
authorization/supporting-contract/envelope v8, verifier v8, executor v6, and
journal runtime v5. Attempt, observation receipt, failure, and completion
records advance to v6, v5, v6, and v5. A new failure-retention record v1 is
used only if the full failure envelope cannot be validated or retained.
Collector v2, snapshot broker v1, and all predecessors remain unchanged.

Before transport, executor v6 proves Linux subreaper, `/proc`, and
`waitid(WNOWAIT)` capability. The transport lease rejects ambiguous
pre-existing child ownership, enables subreaper mode, starts one new-session
leader, and never calls `poll()` or `wait()` before group cleanup. The final
authority guard remains immediately before `Popen`.

Cleanup observes leader exit without reaping it. The waitable zombie therefore
continues to reserve its PID and PGID while the supervisor independently scans
the process group and its adopted children. Remaining descendants are an
operational failure even if the leader exited zero. Cleanup sends bounded
`SIGTERM`, escalates to `SIGKILL`, reaps adopted children, proves no nonleader
group member or owned child remains, and only then reaps the leader. No group
signal is sent after leader reap. Transient `waitid`/`waitpid` interruption and
other injected wait errors remain in diagnostics and are retried by the
fail-stop reap barrier; it never returns a false proof.

Receipt, failure, completion, and snapshot closure occur only after both
`leader_reaped=true` and `process_group_gone=true`. Terminal cleanup outcomes
are versioned and accepted by the associated schemas. The primary transport
reason remains primary; cleanup diagnostics supplement it. If the complete
failure record cannot be validated or retained, executor v6 writes a distinct
create-exclusive typed fallback binding the attempt, authority, resolution,
transition, plan, runtime closure, primary reason, and retention error. If both
retention paths fail, the executor reports both errors and never silently
claims evidence retention.

The fixed argv, `shell=False`, six ordered observations, stop-first, one
attempt, zero retry, durable marker, parent-procfd credential snapshots,
180-second deadline, partial retention, and Stage 18 denial remain unchanged.
All predecessor-version markers continue to block replay.

## Scientific and compatibility effect

Scientific effect: none. Queue, schedule, observation, measurement, and
analysis semantics are unchanged.

Compatibility effect: future `S17-EXT-001` evidence must use the v8/v6/v5
closure. Policy v1 through v7, plan v1 through v5, authorization and envelope
v1 through v7, executor v1 through v5, verifier v3 through v7, journal runtime
v1 through v4, record schemas, ADR-0104 through ADR-0111, protocol snapshots,
journal snapshots, and D-099 through D-108 remain byte-identical and readable
under their own versions. They are not current action authority.

## Authority boundary

This ADR authorizes repository-local implementation and synthetic/local-
process verification only. It creates no authorization, resolution,
transition, evidence, credential, stand access, preflight, qualification,
calibration, pilot, measurement, or Stage 18 authority.
