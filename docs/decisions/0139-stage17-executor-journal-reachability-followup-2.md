# 0139. Stage 17 executor journal-reachability follow-up (2)

Status: ACCEPTED

## Context

ADR-0138 advanced `cli_v11.py`'s own `journal_runtime` to `stage17_state_
journal_v28` (importing `stage17_semantic_verifier_v32`) to reach its
S17-EXT-002 schema-binding fix. Exactly as ADR-0130, ADR-0133, and
ADR-0137 already established for this class of change, this left
`stage17_read_only_preflight_executor_v20.py`'s own `current_journal`
import pinned to `stage17_state_journal_v27` (importing `stage17_
semantic_verifier_v31`).

Since `_policy()` re-verifies every one of its binding's *live* bytes on
every real journal validation, and `cli_v11.py` is itself one of those
pinned bindings, `stage17_state_journal_v27` (via `stage17_semantic_
verifier_v31`) now sees `cli_v11.py`'s current bytes (moved for
ADR-0138) drift against what `v31.json`'s own frozen bindings recorded.
Caught locally, via a real regression-test failure
(`check_stage17_executor_v20_action_readiness.py --self-test`, which
exercises the executor's current wiring directly against the live tree)
-- not via any real stand contact, and not blocking the S17-EXT-002
admission itself, which resolves through `cli_v11.py`'s own `journal_
runtime` independently of the executor's hardcoded import.

This is the same reachability-gap class as before, just triggered by a
completely unrelated fix (S17-EXT-002's schema-binding completion)
advancing the same shared `cli_v11.py` rendezvous point that every
executor generation's own journal import must track in lockstep,
regardless of whether that generation's own logic is otherwise
untouched.

## Decision

Add `stage17_read_only_preflight_executor_v21.py`, a byte-for-byte copy
of `v20` except its own `import stage17_state_journal_v29 as
current_journal` (was `v27`) and `EXECUTOR_ID` bump -- `v29` is this same
ADR's own new journal generation, so the executor and `cli_v11.py` land
on the identical final journal generation once this ADR's implementation
completes, exactly as `v20`/`v27` matched at the end of ADR-0137.
`current_semantic` stays `stage17_read_only_preflight_semantic_verifier_
v20` directly (unchanged, no real logic change); the collector stays
`v3`.

Add `stage17_read_only_preflight_semantic_verifier_v23.py`, a pure
`IMPLEMENTATION_PATHS` rebind of `v22`: `executor` -> `v21.py`,
`state_journal` -> `v29.py`; `collector`/`process_group_supervisor`/
`openssh_snapshot_broker`/`semantic_verifier` keep `v22`'s own inherited
values. `evaluate_s17_ext_001_action_readiness_v20` re-exported
unchanged; `verify_s17_ext_001_semantics_v23` is a deliberate alias of
`v22`'s own `verify_s17_ext_001_semantics_v22` (a pure rebind reuses the
predecessor's logic unchanged, only redirecting which implementation
paths get pinned); `verify_policy_v23` is a fresh copy (it reads
version-specific module-level constants that cannot be aliased).

Add `stage17_semantic_verifier_v33.py`, re-intercepting `S17-EXT-001`
(delegating to `preflight_v23`) while `S17-EXT-002` and everything else
delegates unchanged to `predecessor.verify_input` (`v32`, ADR-0138's own
fix, untouched by this follow-up). `stage17_state_journal_v29.py` moves
the semantic import to `v33`; `cli_v11.py`'s `journal_runtime` moves to
`v29` and its `author-ext001` policy-path literal moves to the new
preflight-plan policy `v23.json`, in the same lockstep pattern already
established.

## Consequences

- This fix is bundled into the same forthcoming bundle reseal as
  ADR-0138, since both are needed before the fourteenth real admission
  can retry S17-EXT-002 against a freshly staged bundle that actually
  contains `stage17-operational-evidence-admission-policy-v32.json` (the
  prior real `admit-resolution` attempt failed with "repository evidence
  file is absent" against the thirteenth admission's bundle, sealed
  before ADR-0138 existed).
- The recurring lesson holds without exception: `current_journal` must be
  re-pointed at the latest journal generation every single time
  `cli_v11.py` moves forward, even when the triggering ADR has nothing to
  do with the executor's own logic.
