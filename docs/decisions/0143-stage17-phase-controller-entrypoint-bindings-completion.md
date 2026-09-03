# 0143. Stage 17 phase-controller entrypoint bindings completion

Status: ACCEPTED

## Context

The second real Q15-R attempt, using the phase-controller journal-
reachability fix from ADR-0142 and a fresh, owner-signed authorization,
failed immediately when handed off for real execution:

```
/tmp/cpu-prefetch-stage16-deps/python/bin/python3: can't open file
'/home/omaltsev/stage17-owner-evidence/stage17-operational-evidence-15/
admission-root/tools/stage17_q15_session_controller_v8.py':
[Errno 2] No such file or directory
```

No stand contact occurred: `python3` failed to open the entrypoint file
before spawning anything. Direct inspection of the real, rendered
`stage17-operational-evidence-admission-policy-v35.json` traced the cause:
`author_stage17_policy_v35.py`'s `ROOTS` still literally lists
`stage17_phase_controller_v9` and `stage17_q15_session_controller_v6` --
unchanged by ADR-0142. `stage17_phase_controller_v11` did make it into the
rendered `runtime_closure`, but only incidentally: `discover_python_
closure` walks real Python `import` statements transitively from every
root, and `stage17_operational_cli_v11` (itself a root) now `import`s
`stage17_phase_controller_v11` directly, so `v11` was picked up as a
transitive dependency of `cli_v11.py`, not because anything intentionally
pinned it. `stage17_q15_session_controller_v7.py` and `v8.py`, however,
are never imported by anything -- they are standalone CLI entrypoints
invoked directly from the shell (`python3 stage17_q15_session_controller_
v8.py --start`), not library modules any other file imports. They were
therefore never discoverable, never bound, and consequently never copied
by `create_stand_bundle.py` (which only copies files listed in the
policy's own `bindings`/`runtime_closure`) into any sealed bundle -- not
even the bundle ADR-0142 itself was accepted alongside, since that bundle
(v17) predates `stage17_phase_controller_v11.py` and `stage17_q15_
session_controller_v7.py`/`v8.py` entirely.

The real, non-mutating `prepare_action(...)` call used to "verify" the
ADR-0142 fix earlier in this session was itself unknowingly contaminated:
the shell's working directory was still the live `tools/` tree, so
Python's `sys.path` resolved `stage17_phase_controller_v11` from the live
repository, not from the frozen admission root the real execution script
actually uses. It did not prove what it was believed to prove.

## Decision

Add `tools/stage17_semantic_verifier_v36.py`, a pure additive successor
to `v35` that changes no `verify_input` dispatch logic at all -- only
`POLICY_PATH`, which now points at a new policy generation.

Add `tools/author_stage17_policy_v36.py`, whose `ROOTS` is `predecessor.
ROOTS` (unchanged, since this ADR does not move the read-only-preflight
executor/journal generation itself) but whose `SUCCESSOR_BINDINGS` now
explicitly pins `tools/stage17_phase_controller_v11.py`, `tools/stage17_
q15_session_controller_v7.py`, and `tools/stage17_q15_session_controller_
v8.py` as real bindings -- the same mechanism ADR-0127 originally used to
pin `stage17_phase_controller_v3.py` through `v6.py`, and every phase-
controller/Q15-session-controller generation since, none of which have
ever been reachable via the real import graph either.

Add `tools/stage17_state_journal_v32.py`, importing `stage17_semantic_
verifier_v36` and reassigning `semantic`/`SEMANTIC_POLICY_PATH` down the
same fixed five-hop predecessor chain `v31.py` already used, so real
`admit-resolution` calls actually resolve through the new policy.

`stage17_operational_cli_v11.py`'s own `import stage17_state_journal_v31
as journal_runtime` moves to `v32`. No `author-ext001` policy-path change
is needed: the read-only-preflight-plan policy (`S17-EXT-001`) is
completely unaffected by this fix.

## Consequences

- A fresh Q15-R attempt requires a new authorization, a new owner
  signature, and a freshly resealed bundle (containing this policy
  generation and the three now-pinned entrypoint files) before it can
  even reach real execution -- the second authorization (session `-15B`,
  `AUTH-15B`) was consumed by this real, safe, no-stand-contact failure
  and is not reused.
- Moving `cli_v11.py`'s own `journal_runtime` forward, as this ADR does,
  is the same edit that has twice before (ADR-0138 -> ADR-0139, ADR-0140
  -> ADR-0141) immediately stranded the read-only-preflight executor
  family's own hardcoded journal import. ADR-0142 additionally proved the
  phase-controller family carries an identical hardcoded-import gap. Both
  are expected to require an immediate follow-up, tracked separately.
