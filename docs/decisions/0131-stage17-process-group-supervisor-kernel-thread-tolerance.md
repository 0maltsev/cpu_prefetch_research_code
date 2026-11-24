# ADR-0131: Stage 17 process-group supervisor kernel-thread tolerance

- **Status:** `ACCEPTED`
- **Decision ID:** D-131
- **Classification:** implementation correctness, latent defect in already-
  accepted production code, action-time capability-verification robustness
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` read-only preflight action can
  execute

## Context

After ADR-0130 fixed the executor's journal-reachability defect and a
second real `S17-EXT-001` resolution was genuinely admitted (journal at
`/home/omaltsev/stage17-owner-evidence/stage17-operational-evidence-2/`,
`AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, 1 resolution, 1 transition,
`action_ready: true`), the owner ran the real `--execute` retry from their
own terminal. It failed twice, at two different pre-marker checks, before
any network activity or marker creation:

1. `OPENSSH_CONSUMPTION_CAPABILITY_BLOCKED: quiescent OpenSSH capability
   proof failed`, root-caused (via a read-only diagnostic calling
   `stage17_openssh_parent_snapshot_v2.verify_local_openssh_parent_procfd_
   capability` directly) to `PermissionError: [Errno 13] Permission
   denied: '/proc/1/ns/pid'` inside `stage17_process_group_supervisor_v2.
   py`'s `_namespace_inode`. Reading another process's `/proc/<pid>/ns/pid`
   requires the same privilege `ptrace` would (same uid as the target, or
   `CAP_SYS_PTRACE`); the owner's shell had neither. This is a real,
   deliberate privilege requirement in already-accepted code, not a bug --
   confirmed by re-deriving the exact kernel check the failure traces to,
   not by assumption.
2. After the owner re-ran with `sudo setpriv --reuid=<self> --regid=<self>
   --clear-groups --inh-caps=+sys_ptrace --ambient-caps=+sys_ptrace --`
   (granting `CAP_SYS_PTRACE` to one process invocation while keeping
   their own uid, so the SSH-private-key ownership re-check --
   `metadata.st_uid != os.geteuid()` in `stage17_semantic_verifier_v5.py`
   -- still passes), the `/proc/1/ns/pid` check passed and a *different*
   failure appeared: `PRE_MARKER_PREPARATION_BLOCKED: SupervisorError:
   empty or nonpositive NSpgid`.

The second failure was root-caused directly, not assumed, via a read-only
diagnostic that ran `ProcfsIdentityModel._identity_at` against every PID
under `/proc` on the owner's real machine (217 hits, all reproduced with
full `/proc/<pid>/status` bytes). Every failing PID is a kernel thread
(`Kthread: 1`, parent `kthreadd`/PID 2 -- `oom_reaper`, `kworker/*`,
`kcompactd0`, `ksmd`, `khugepaged`, etc.). Kernel threads always report
`NSpgid: 0` in `/proc/<pid>/status`: correct, expected kernel behavior,
since a kernel thread structurally cannot belong to any process group.

`stage17_process_group_supervisor_v2.py`'s `_identity_at` only tolerates a
process *vanishing* mid-scan (`except SupervisorError as exception: if
isinstance(exception.__cause__, FileNotFoundError): return None; raise`).
The `nspgid = _parse_integer_vector(fields.get("NSpgid", ""), "NSpgid")`
call that raises `SupervisorError("empty or nonpositive NSpgid")` for a
kernel thread sits *outside* that guarded block, so it propagates
uncaught and aborts the entire `/proc` scan the instant `direct_children`/
`process_group_members` (called from both `verify_supervisor_capability`
and, via `stage17_openssh_parent_snapshot_v2.py`'s `_direct_children`, the
OpenSSH quiescence check too) reaches the first kernel thread.

This defect was never caught before tonight because every prior exercise
of this code -- self-tests, the hermetic rehearsal, this session's own
Claude Code sandbox -- ran inside a private PID namespace where host
kernel threads are not visible in `/proc` at all. The owner's real
machine, running the executor directly against the host's own `/proc`, is
the first environment that has ever actually walked a `/proc` tree
containing kernel threads through this code path. The real, already-
admitted second resolution's journal and evidence were confirmed
unaffected by both failures: no marker was created, `/home/omaltsev/
stage17-owner-evidence/ext001-preflight-output/` remained empty, and the
journal stayed at `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, 1 resolution/1
transition, before and after each attempt.

## Decision

Add `tools/stage17_process_group_supervisor_v3.py` as an additive
successor to `stage17_process_group_supervisor_v2.py`, re-exporting every
`v2` name unchanged and replacing only `_identity_at`'s handling of a
kernel thread: after the existing `FileNotFoundError`-tolerant block, wrap
the `nspgid = _parse_integer_vector(...)` call so that a `SupervisorError`
whose message is exactly `"empty or nonpositive NSpgid"` also returns
`None` (not a process-group member) instead of propagating. This does not
weaken `verify_supervisor_capability`'s actual security guarantee: the
real fixture leader/children it verifies are ordinary user processes with
real, positive `NSpgid` values by construction, so they are matched
exactly as before; only kernel threads -- which can never be a match for
any user session's process group -- are now skipped instead of aborting
the whole scan. `nspid` stays parsed and checked exactly as `v2` did (its
value is never `0`/empty for a kernel thread in the real evidence above,
so no corresponding tolerance is needed there); this is a narrow,
principled fix scoped to the one field actually observed to break.

Because `stage17_openssh_parent_snapshot_v2.py`'s own `_direct_children`
calls the identical `model.direct_children()` method, and Python resolves
`supervisor`/`process_supervisor` as free variables against the module
that *defines* the calling function (not the module that imports it --
the same lesson ADR-0126 already recorded), the fix is only reachable if
every caller's own `supervisor`/`process_supervisor` import moves to
`v3`. This requires:

- `tools/stage17_openssh_parent_snapshot_v3.py`: additive successor to
  `_v2.py`, re-exporting everything unchanged except `import stage17_
  process_group_supervisor_v3 as supervisor`.
- `tools/stage17_read_only_preflight_executor_v15.py`: additive successor
  to `_v14.py`, re-exporting everything unchanged except `import stage17_
  process_group_supervisor_v3 as process_supervisor` and `import stage17_
  openssh_parent_snapshot_v3 as snapshot_broker` (the `_v1` helper import
  stays as-is). `current_semantic` (`v15`) and `current_journal` (`v20`)
  are unaffected and stay exactly as ADR-0130 left them. `EXECUTOR_ID`
  updates to `v15`.
- A new preflight-plan policy successor (mirroring `v16`) rebinding
  `implementations.executor` to `v15` and `operational_implementations.
  pid_namespace_supervisor` to `v3`, a new outer operational-policy
  successor (mirroring `v24`) binding the new files' real hashes, and
  `cli_v11.py`'s `journal_runtime` import and `author-ext001` policy path
  repointed to that new generation -- the exact same additive,
  non-promoting cascade ADR-0130 already established and already proved
  correct once. As ADR-0130's own Effects section already establishes for
  this exact structural reason (`_verify_loaded_runtime`'s strict
  per-role name/hash match against whatever preflight-plan policy the
  admitted resolution's envelope pins): the second real resolution
  admitted under ADR-0130's chain is pinned to `pid_namespace_supervisor`
  = `v2` forever, so it can never be executed by `v3` either. A **third**
  real `S17-EXT-001` admission, against this new chain, will be required
  before a real execution can succeed. Sealing a new real bundle
  (mirroring `v8`) containing this fix is also required, for the same
  reason `v8` was required for ADR-0130.

## Effects

Fixes the specific, real, reproduced crash that stops `verify_supervisor_
capability`/the OpenSSH quiescence check from ever completing on any real,
non-namespaced host with kernel threads visible in `/proc` -- which is to
say, on any real stand machine, not just the owner's own terminal. No
scientific design, transport mechanics, credential handling, security
guarantee, or SSH/fixed six-observation action plan changes -- only which
processes are tolerated as "not a match" while scanning for the real
fixture leader/children. This does not by itself make the second
resolution executable (see Context/Decision above); it only removes a
defect that would otherwise reproduce on any real host, including a third
resolution admitted after this fix.

## Verification and supersession

Acceptance requires: a positive regression proving `_identity_at` returns
`None` (not raise) for a real or synthetic process whose `NSpgid` is `0`,
using the exact real evidence already captured above (a kernel-thread
`/proc/<pid>/status` fixture) rather than a hand-waved mock; a regression
proving `v2`'s own chain (and `check_stage17_pid_namespace_supervisor.py`,
`check_stage17_executor_v13/v14_action_readiness.py`) are completely
unaffected and importable/usable exactly as before; confirmation via `git
diff` that no file in any previously accepted or accepted-adjacent closure
changed; and, before any real retry, a dry-run local capability check
(`verify_supervisor_capability()`/`verify_local_openssh_parent_procfd_
capability()`) run directly against the real target machine's own `/proc`,
succeeding end to end. Any later change to which kernel-visible process
states this scan tolerates requires another prospective successor under
the same standard applied since ADR-0108.
