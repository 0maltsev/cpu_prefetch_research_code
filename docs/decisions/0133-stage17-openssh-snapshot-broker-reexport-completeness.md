# ADR-0133: Stage 17 OpenSSH snapshot broker re-export completeness

- **Status:** `ACCEPTED`
- **Decision ID:** D-133
- **Classification:** implementation correctness, incomplete re-export in
  an additive successor introduced this same session (ADR-0132), action-
  time attribute resolution
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` read-only preflight action can
  execute

## Context

Unlike ADR-0130/ADR-0131/ADR-0132, which each fixed a latent defect that
predated this session, this defect was introduced by ADR-0132's own
`tools/stage17_openssh_parent_snapshot_v4.py`, in this same session. When
building `v4` as an additive successor to `v3.py`, `pin_bound_input` was
correctly given a fresh copy (retargeting its `MECHANISM` constant), and
`validate_identity_parseability`, `verify_snapshot`, and `close_snapshots`
were correctly re-exported unchanged -- but `verify_local_openssh_parent_
procfd_capability`, a fourth function `v3.py` defines (not re-exported
from its own predecessor, since its body constructs `supervisor.
SupervisorLease()` and therefore needed its own copy when `v3` was
written for ADR-0131), was omitted entirely.

After a fourth real `S17-EXT-001` resolution was genuinely admitted
against the ADR-0132 chain (journal at `/home/omaltsev/stage17-owner-
evidence/stage17-operational-evidence-4/`, `AUTHORIZED_FOR_READ_ONLY_
PREFLIGHT`, 1 resolution, 1 transition, `action_ready: true`), the
owner's real `--execute` retry failed immediately with:

```
stage17-read-only-preflight-v12: FAIL: PRE_MARKER_PREPARATION_BLOCKED:
AttributeError: module 'stage17_openssh_parent_snapshot_v4' has no
attribute 'verify_local_openssh_parent_procfd_capability'
```

confirmed directly, not assumed, by grepping `v4.py` for the name and
finding it absent. The real journal was confirmed unaffected before and
after: no marker was created, `/home/omaltsev/stage17-owner-evidence/
ext001-preflight-output/` remained empty, and the journal stayed at
`AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, 1 resolution/1 transition.

`verify_local_openssh_parent_procfd_capability`'s own body (in `v3.py`)
was checked directly: it sets `result["mechanism"]` to the hardcoded
literal `"LINUX_PARENT_PROCFD_OPENSSH_SUBREAPER_QUIESCENT-v2"`, not to
the module-level `MECHANISM` name -- so it does not depend on ADR-0132's
change at all, and is safe to re-export unchanged rather than needing a
fresh copy.

## Decision

Add `tools/stage17_openssh_parent_snapshot_v5.py` as an additive
successor to `stage17_openssh_parent_snapshot_v4.py`, re-exporting every
`v4` name unchanged and additionally re-exporting `verify_local_openssh_
parent_procfd_capability = immediate_predecessor.verify_local_openssh_
parent_procfd_capability` (an alias, not a fresh copy, since the function
does not read `MECHANISM` or any other version-varying free variable).

`tools/stage17_read_only_preflight_executor_v17.py` is an additive
successor to `_v16.py`, identical except `import stage17_openssh_parent_
snapshot_v5 as snapshot_broker`. `current_semantic`, `process_supervisor`,
and `current_journal`'s own generation stay exactly as `v16` left them,
except `current_journal` is proactively rebound to whatever journal
generation `cli_v11.py` uses once this ADR's own preflight-plan/
operational-policy successors exist, applying the same lockstep lesson
ADR-0130/ADR-0131/ADR-0132 already established. `EXECUTOR_ID` updates to
`v17`.

A new preflight-plan policy successor (mirroring `v18`) rebinds
`implementations.executor` to `v17` and `implementations.openssh_
snapshot_broker` to `v5`, a new operational-policy successor (mirroring
`v26`) binds the new files' real hashes, and `cli_v11.py`'s `journal_
runtime` import and `author-ext001` policy path are repointed so a new
real `S17-EXT-001` admission uses the corrected chain. As ADR-0130/
ADR-0131/ADR-0132's own Effects sections already establish for the same
structural reason: the fourth real resolution admitted under ADR-0132's
chain is pinned to `openssh_snapshot_broker` = `v4` forever, so it can
never be executed by `v5` either. A **fifth** real `S17-EXT-001`
admission, against this new chain, will be required before a real
execution can succeed. Sealing a new real bundle (mirroring `v8`/`v9`/
`v10`) containing this fix is also required.

## Effects

Fixes the specific, real, reproduced `AttributeError` that stops any real
preflight execution from ever reaching its capability proof, on any real
host. No scientific design, transport mechanics, credential handling,
security guarantee, or SSH/fixed six-observation action plan changes --
only completing `v4`'s own re-export surface to match `v3`'s. This does
not by itself make the fourth resolution executable (it is pinned to
`v4`'s incomplete module forever, same structural reason as prior ADRs);
it only removes a defect that would otherwise reproduce on any real host,
including a fifth resolution admitted after this fix.

## Verification and supersession

Acceptance requires: a positive regression proving `v5.verify_local_
openssh_parent_procfd_capability` is present and identical to `v3`'s
(via `is` identity, since it is an alias); confirmation, via a
programmatic `dir()` diff (not eyeballed) between `v3` and `v5`, that
every name any real caller actually references via `snapshot_broker.*`
(checked directly by grepping the whole `tools/` tree, not assumed) is
present in `v5` -- the diff also surfaces `v3`-only internal helpers
(`_direct_children`, `_quiesce_capability_children`, `POLL_NS`, etc.)
that `verify_local_openssh_parent_procfd_capability` already uses
correctly from within `v3`'s own module and that no other caller
references by name, which do not need separate re-export; a regression
proving `v4`'s own chain (and `check_stage17_executor_v13/v14/v15/
v16_action_readiness.py`) are completely unaffected and importable/
usable exactly as before; confirmation via `git diff` that no file in
any previously accepted or accepted-adjacent closure changed. Any later
change to this module's re-export surface requires another prospective
successor under the same standard applied since ADR-0108.
