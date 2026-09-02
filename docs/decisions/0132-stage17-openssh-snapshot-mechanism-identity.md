# ADR-0132: Stage 17 OpenSSH snapshot mechanism identity

- **Status:** `PROPOSED`
- **Decision ID:** D-132
- **Classification:** implementation correctness, latent defect in already-
  accepted production code, action-time attempt-marker schema conformance
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` read-only preflight action can
  execute

## Context

After ADR-0130 and ADR-0131 fixed two real, action-time-only defects and a
third real `S17-EXT-001` resolution was genuinely admitted (journal at
`/home/omaltsev/stage17-owner-evidence/stage17-operational-evidence-3/`,
`AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, 1 resolution, 1 transition,
`action_ready: true`), the owner's real `--execute` retry got further
than either prior attempt -- past the `/proc/1/ns/pid` privilege
requirement and past the kernel-thread crash -- and failed with a new,
different error, still before any marker was created or the journal
changed:

```
stage17-read-only-preflight-v12: FAIL: attempt marker schema error at
$/pinned_openssh_inputs/known_hosts/snapshot_mechanism:
'LINUX_PARENT_PROCFD_OPENSSH_SUBREAPER_QUIESCENT-v2' was expected
```

The root cause was traced directly, not assumed: `pin_bound_input` in
`tools/stage17_openssh_parent_snapshot_v1.py` hardcodes each pinned
input's own `metadata["snapshot_mechanism"]` to the module-level constant
`MECHANISM = "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1"`. This function is
re-exported unchanged by `_v2.py` and `_v3.py` (`pin_bound_input =
predecessor.pin_bound_input`), so every version through `v3` still emits
the `v1` identity for this field, regardless of which capability-proof
wrapper (`v2`'s subreaper quiescence, `v3`'s kernel-thread tolerance) is
actually in use around it.

Diffing the attempt-marker schema across versions shows this is a real,
deliberate mismatch, not a false alarm: `config/schemas/stage17-read-
only-preflight-attempt-v8.schema.json`'s shared `$defs/snapshot.
properties.snapshot_mechanism` correctly required the `v1` constant, but
`-v9.schema.json` (and the currently active `-v10.schema.json`) bumped it
to the `v2` constant -- consistently with `openssh_consumption_
capability.mechanism`, `.fixture_process_quiescence.mechanism`, and
`process_supervisor_capability.mechanism`, all of which already correctly
report `v2` identities. The schema's intent is clear and self-consistent:
once the whole capture happens under the `v2` (or later) capability
layer's guarantees, every mechanism-tagged field in the marker -- not
just the top-level capability-proof summary -- should say so. The
corresponding code change to `pin_bound_input` was simply never made when
that schema version shipped.

This is the third distinct real defect surfaced tonight purely by a
genuine execution attempt reaching further than any prior one: no marker
was ever created before, this specific code path (`pin_bound_input`'s
real construction of `known_hosts`/`transport_identity` metadata, as
opposed to a hand-constructed synthetic fixture) had never been exercised
end to end by anything -- self-tests build synthetic attempt-marker
documents directly rather than calling `pin_bound_input`, so this gap sat
undetected since schema `v9` shipped. The real journal was confirmed
unaffected before and after the failed attempt: no marker was created,
`/home/omaltsev/stage17-owner-evidence/ext001-preflight-output/` remained
empty, and the journal stayed at `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, 1
resolution/1 transition.

## Decision

Add `tools/stage17_openssh_parent_snapshot_v4.py` as an additive
successor to `stage17_openssh_parent_snapshot_v3.py`, re-exporting every
`v3`/`v1` name unchanged except `pin_bound_input`, which is a faithful
copy of `v1`'s implementation with exactly one change: the module-level
`MECHANISM` constant this module defines is `"LINUX_PARENT_PROCFD_
OPENSSH_SUBREAPER_QUIESCENT-v2"` instead of `v1`'s `"LINUX_SEALED_MEMFD_
PARENT_PROCFS-v1"` -- a fresh copy, not an alias, for the same free-
variable-resolves-via-defining-module reason ADR-0126 already recorded:
`pin_bound_input`'s body reads `MECHANISM` as a bare name resolved
against whichever module it is *defined* in. Every other check in
`pin_bound_input` (ownership/permission verification, size/hash
reverification, sealed-memfd creation and seal verification, procfs
locator construction) is byte-identical to `v1`'s. `verify_snapshot`,
`validate_identity_parseability`, `close_snapshots`, and every helper
function are re-exported unchanged, since none of them read `MECHANISM`.

`tools/stage17_read_only_preflight_executor_v16.py` is an additive
successor to `_v15.py`, identical except `import stage17_openssh_parent_
snapshot_v4 as snapshot_broker` (the `_v1` helper import stays
unchanged). `current_semantic` (`v15`), `current_journal`, and
`process_supervisor` (`v3`, ADR-0131's unrelated fix) stay exactly as
`v15` left them; `EXECUTOR_ID` updates to `v16`.

A new preflight-plan policy successor (mirroring `v17`) rebinds
`implementations.executor` to `v16` and `implementations.openssh_
snapshot_broker` to `v4`, a new operational-policy successor (mirroring
`v25`) binds the new files' real hashes, and `cli_v11.py`'s `journal_
runtime` import and `author-ext001` policy path are repointed so a new
real `S17-EXT-001` admission uses the corrected chain -- the exact same
additive, non-promoting cascade ADR-0130/ADR-0131 already established.
As those ADRs' own Effects sections already establish for the same
structural reason (`_verify_loaded_runtime`'s strict per-role name/hash
match against whatever preflight-plan policy the admitted resolution's
envelope pins): the third real resolution admitted under ADR-0131's chain
is pinned to `openssh_snapshot_broker` = `v3` forever, so it can never be
executed by `v4` either. A **fourth** real `S17-EXT-001` admission,
against this new chain, will be required before a real execution can
succeed. Sealing a new real bundle (mirroring `v8`/`v9`) containing this
fix is also required, for the same reason those bundles were required for
ADR-0130/ADR-0131.

## Effects

Fixes the specific, real, reproduced attempt-marker schema rejection that
stops any real preflight execution from ever writing its durable marker,
on any real host -- not just the owner's own terminal. No scientific
design, transport mechanics, credential handling, security guarantee, or
SSH/fixed six-observation action plan changes -- only which mechanism
identity string each pinned input's own snapshot metadata reports. This
does not by itself make the third resolution executable (it is pinned to
`v3`'s stale identity forever, same as ADR-0130/ADR-0131's prior
resolutions); it only removes a defect that would otherwise reproduce on
any real host, including a fourth resolution admitted after this fix.
Given this is the third distinct real defect found only once execution
reached further than any prior attempt, a fourth real attempt may
similarly surface a further, not-yet-reached defect; this ADR does not
claim the real execution path is otherwise proven correct beyond the
point tonight's attempts have actually reached.

## Verification and supersession

Acceptance requires: a positive regression proving `pin_bound_input`
(via the new `v4` module) produces `snapshot_mechanism = "LINUX_PARENT_
PROCFD_OPENSSH_SUBREAPER_QUIESCENT-v2"` for a real pinned input, verified
against the actual attempt-marker schema (`v10`) rather than a hand-
waved mock; a regression proving `v1`/`v2`/`v3`'s own chain (and
`check_stage17_openssh_snapshot_consumption.py`, `check_stage17_executor_
v13/v14/v15_action_readiness.py`) are completely unaffected and
importable/usable exactly as before; confirmation via `git diff` that no
file in any previously accepted or accepted-adjacent closure changed; and,
before any real retry, a dry-run local construction of a real pinned
input's metadata, validated directly against the real attempt-marker
schema, succeeding. Any later change to which mechanism identity this
metadata reports requires another prospective successor under the same
standard applied since ADR-0108.
