# ADR-0137: Stage 17 executor journal reachability follow-up

- **Status:** `ACCEPTED`
- **Decision ID:** D-137
- **Classification:** implementation correctness, defect in ADR-0136's
  own implementation this same session, journal-reachability gap class
  already established by ADR-0130 and re-applied since
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` action-readiness check (local
  or real `--execute`) can succeed against a journal admitted under the
  ADR-0136 chain

## Context

Unlike ADR-0130 through ADR-0135, which each fixed a defect discovered
via a real, admitted resolution's real execution attempt, this defect
was caught locally, read-only, before any real stand contact: running
this session's own established local safety check (`executor._prospective_
validation`) against the twelfth real admission (freshly materialized
from the real, sealed `v14` bundle) failed immediately with `bindings
config__schemas__stage17-runtime-release-provenance-v5_schema_json file
identity/size drifted`, tracing back through `stage17_state_journal_v25.py`
-- still bound to `stage17_semantic_verifier_v29.py`, the outer policy
generation ADR-0136 superseded.

`tools/stage17_read_only_preflight_executor_v19.py`'s own `import
stage17_state_journal_v25 as current_journal` was never updated when
ADR-0136 moved `cli_v11.py`'s own `journal_runtime` import to `v26.py`:
exactly the reachability-gap class ADR-0130 first established and
ADR-0131 through ADR-0135 each had to re-apply, missed once more here
because ADR-0136 correctly reasoned that `S17-EXT-001`'s own executor,
collector, and preflight-plan policy needed no *logic* change, but
incorrectly concluded from that they needed no new *generation* either
-- the executor's own journal import still has to track whichever
journal generation `cli_v11.py` itself uses, independent of whether any
other part of the executor changes.

No real stand action was attempted or affected: the twelfth admission's
`admit-resolution`/`append-transition` steps themselves succeeded for
real (the journal reached state `000002`); only the local, read-only,
side-effect-free safety check this session runs before ever handing off
a real `--execute` script caught this, before any script was handed off.

## Decision

`tools/stage17_read_only_preflight_executor_v20.py` is an additive
successor to `v19.py`, identical except `import stage17_state_journal_v27
as current_journal` (was `v25`) and `EXECUTOR_ID` updated to `v20`. No
other change: `current_semantic` stays `stage17_read_only_preflight_
semantic_verifier_v20.py`, imported directly, exactly as `v19` had it;
the collector stays `v3`.

`tools/stage17_read_only_preflight_semantic_verifier_v22.py` is an
additive successor to `v21.py`, a pure `IMPLEMENTATION_PATHS` rebind
(`"executor"` to `v20`) with no logic change, following the same
established convention: `evaluate_s17_ext_001_action_readiness_v20`
keeps its existing name unchanged (re-exported as-is), and `verify_s17_
ext_001_semantics_v22` is a deliberate alias of `v21`'s own `verify_s17_
ext_001_semantics_v21`.

`tools/stage17_semantic_verifier_v31.py` is an additive successor to
`v30.py`, rebinding `S17-EXT-001`'s own dispatch to `stage17_read_only_
preflight_semantic_verifier_v22.py` (`preflight.verify_policy_v22`/
`verify_s17_ext_001_semantics_v22`); `S17-EXT-002`'s dispatch stays
completely unchanged, still `stage17_operational_semantics_v6.verify_
manifest_v6` (ADR-0136's own fix, untouched by this follow-up).

`tools/stage17_state_journal_v27.py` completes the lockstep: bound to
`stage17_semantic_verifier_v31.py`. `cli_v11.py`'s `journal_runtime`
import moves to `v27.py` and `author-ext001`'s `policy_path` literal
moves to the new preflight-plan policy `v22.json`.

As every prior ADR in this chain already establishes for the same
structural reason: the twelfth real resolution, already admitted under
the ADR-0136 chain, is permanently pinned to `executor_v19`/journal `v26`
forever and can never be executed by this fix either. A **thirteenth**
real `S17-EXT-001` admission, against this new chain, will be required.
Sealing a new real bundle (mirroring `v8` through `v14`) containing this
fix is also required, and its extracted tree will need to be staged on
the stand again.

## Effects

Fixes the real, reproduced local action-readiness failure that stops
even the pre-execution safety check from succeeding against any
resolution admitted under the ADR-0136 chain, let alone a real
`--execute`. Narrowly scoped: only the executor's own journal import and
the two pure-rebind wrappers it requires change; no observation, no
archive-identity, no runtime-tool-identity, and no `S17-EXT-002` logic
changes at all. Does not by itself make the twelfth resolution
executable (permanently pinned to the old wiring, same reason as every
prior ADR); it only removes a defect that would otherwise reproduce on
any real host, including a thirteenth resolution admitted after this fix.

## Verification and supersession

Acceptance requires: a positive regression proving the local action-
readiness check succeeds against a resolution admitted through the live
`author-ext001`/`admit-resolution` wiring under this new chain; a
regression proving the `v19`/`v21` chain (and every prior `check_stage17_*`
regression) remain completely unaffected and importable/usable exactly
as before; confirmation via `git diff` that no file in any previously
accepted or accepted-adjacent closure changed, and specifically that
`stage17_operational_semantics_v6.py` and the `S17-EXT-002` dispatch
path ADR-0136 introduced are untouched. Any later change to which
journal generation the executor consults requires another prospective
successor under the same standard applied since ADR-0108.
