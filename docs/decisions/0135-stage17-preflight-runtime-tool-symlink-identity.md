# ADR-0135: Stage 17 read-only preflight runtime-tool symlink identity

- **Status:** `ACCEPTED`
- **Decision ID:** D-135
- **Classification:** implementation correctness, latent defect predating
  this session, fixed observation-program design assumption that does
  not hold on real hardware
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` read-only preflight action can
  execute against any stand where `/usr/bin/python3`, `/usr/bin/
  sha256sum`, or `/usr/bin/uname` is a symlink

## Context

The tenth real `S17-EXT-001` admission -- the first ever to reach past
`S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION`, following ADR-0134's
fix and the operational staging of the real, byte-verified v12 bundle's
*extracted* tree on the stand -- made genuine further progress: real
observations 1 through 4 all passed for real, including `S17-RO-
PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS` actually executing three real
Stage 17 binaries on the real stand (`cpu_prefetch_smoke`, `cpu_prefetch_
preflight --self-test`, `cpu_prefetch_qualification --self-test`, all
returning 0) -- the first time any real Stage 17 binary has run on the
real stand in this repository's history.

It then failed, real and reproduced, at `S17-RO-PREFLIGHT-005-RUNTIME-
TOOL-IDENTITIES` with `REMOTE_NONZERO_EXIT`/`RuntimeError: runtime file`.
Reading `tools/stage17_read_only_preflight_collector_v1.py`'s `render_
observation_program` for this observation (`OBSERVATION_IDS[4]`) shows
it checks six fixed paths -- `/usr/bin/python3`, `/usr/bin/sha256sum`,
`/usr/bin/uname`, and the three bundle binaries under `release/bin/` --
with `s=os.lstat(path);require(stat.S_ISREG(s.st_mode) and not stat.
S_ISLNK(s.st_mode),'runtime file')` for every one of them uniformly.
`os.lstat` never follows a symlink, so `stat.S_ISREG` is always false and
this check always fails whenever any of these six paths is itself a
symlink.

A real, read-only `stat -c '%F %N'` against the real stand (no writes,
no mutation) confirms all three fixed system-tool paths are symlinks
there:

```
symbolic link '/usr/bin/python3' -> 'python3.14'
symbolic link '/usr/bin/sha256sum' -> '../lib/cargo/bin/coreutils/sha256sum'
symbolic link '/usr/bin/uname' -> '../lib/cargo/bin/coreutils/uname'
```

This is ordinary, common Linux packaging (a per-version Python symlink;
coreutils consolidated into one shared binary, as `uutils-coreutils` and
similar do), not a stand misconfiguration. The three bundle binaries are
NOT symlinks (`S17-RO-PREFLIGHT-004` already proved they execute
correctly as plain files sealed inside the verified bundle), so this
check's assumption -- that every one of these six paths is always a
plain regular file, never a symlink -- holds for the bundle's own
sealed binaries but is false, structurally and permanently, for standard
system tools on real, modern Linux hosts. The check as written can never
pass on any such stand, real or otherwise.

`digest()` (the same collector preamble every observation program
shares) already opens paths with plain `open(path,'rb')`, which follows
symlinks by default -- so hashing a symlinked system tool through to its
real target already works; only the `os.lstat`/`S_ISLNK` rejection
itself is the blocker. `tools/stage17_read_only_preflight_collector_v2.py`
is a thin wrapper (`render_observation_program`) that validates the
capture timestamp and then delegates to `collector_v1.render_
observation_program` unchanged -- it does not itself branch per
observation, so the fix must live in a fresh copy of the whole dispatcher
function, the same class of "single function, one changed branch" fix
ADR-0132's `pin_bound_input` retargeting already established.

## Decision

Add `tools/stage17_read_only_preflight_collector_v3.py` as an additive
successor to `stage17_read_only_preflight_collector_v2.py`, re-exporting
`COLLECTOR_ID` (bumped to `-v3`), `OBSERVATION_IDS`, and `validate_exact_
second_utc` unchanged, and providing a fresh copy of `render_observation_
program` that is byte-identical to `v1`'s for every observation except
`OBSERVATION_IDS[4]`: the loop there splits the six fixed paths into two
groups. The three bundle binaries (`release/bin/cpu_prefetch_smoke`,
`.../cpu_prefetch_preflight`, `.../cpu_prefetch_qualification`) keep the
exact existing check -- `os.lstat`, `require(S_ISREG and not S_ISLNK)`
-- since they are sealed inside the hash-verified bundle and must never
legitimately be symlinks. The three fixed system-tool paths (`/usr/bin/
python3`, `/usr/bin/sha256sum`, `/usr/bin/uname`) instead use `os.stat`
(follows symlinks) and `require(S_ISREG(s.st_mode), 'runtime file')` --
dropping the symlink rejection for these three specifically, since a
symlink to the real interpreter/tool is the normal, expected shape on a
real host, and rejecting it can never be satisfied there. The recorded
identity (`path`, `size_bytes`, `sha256`, `mode`) reflects the *resolved*
regular file for these three -- the file that actually executes when the
path is invoked -- which is the more meaningful identity to pin, not a
weaker one: `digest()` was already hashing through the symlink either
way.

`tools/stage17_read_only_preflight_executor_v19.py` is an additive
successor to `v18.py`, identical except `import stage17_read_only_
preflight_collector_v3 as ...` at its `render_observation_program` call
site (currently `stage17_read_only_preflight_collector_v2`), with
`current_journal` proactively rebound to whatever journal generation
`cli_v11.py` uses once this ADR's own preflight-plan/operational-policy
successors exist, per the lockstep lesson ADR-0130 through ADR-0134
already established. `current_semantic` stays imported directly as
`stage17_read_only_preflight_semantic_verifier_v20.py`, exactly as
`v18.py` had it: the executor never imports the `IMPLEMENTATION_PATHS`-
rebind wrapper of the moment (`v16` through `v19` established this same
pattern relative to `v15` -- their own executors, `v14` through `v17`,
always imported `v15` directly). `EXECUTOR_ID` updates to `v19`.

`tools/stage17_read_only_preflight_semantic_verifier_v21.py` is an
additive successor to `v20.py`, used only by the *outer* registry
module's resolution-time dispatch (`stage17_semantic_verifier_v29.py`),
rebinding `IMPLEMENTATION_PATHS["executor"]` to `v19`, `IMPLEMENTATION_
PATHS["collector"]` to `v3`, and -- in lockstep, since `executor_v19.py`'s
own `current_journal` import moves too -- `IMPLEMENTATION_PATHS[
"state_journal"]` to `v25`. A pure rebind, not a logic change, so
`verify_s17_ext_001_semantics_v21` is a deliberate alias of `v20`'s own
`verify_s17_ext_001_semantics_v20`, exactly as `v16` through `v19`
already established for the same reason: its body never reads the
collector's or journal's own file identity beyond the generic
`implementations` closure check. `evaluate_s17_ext_001_action_readiness_
v20` keeps its existing name unchanged, re-exported as-is (not renamed to
`_v21`) -- the same convention this whole chain has used since `v15`'s
own fresh copy, since only `v20` (ADR-0134) and this file's own logic-
bearing successors ever earn a fresh copy of that function; a pure
`IMPLEMENTATION_PATHS` rebind never does. `verify_policy_v21` is a fresh
copy, following the same rationale `verify_policy_v16` through `v20`
themselves documented. A new preflight-plan policy successor `stage17-
read-only-preflight-evidence-admission-policy-v21.json` (authored from
`v21.py`'s own bindings) carries these three rebinds; a new operational-
policy successor (`stage17_semantic_verifier_v29.py`, mirroring `v28`)
binds the new files' real hashes; `cli_v11.py`'s `journal_runtime` import
and `author-ext001`'s `policy_path` literal are repointed so a new real
`S17-EXT-001` admission uses the corrected chain. As every prior ADR in this chain
already establishes for the same structural reason: the tenth real
resolution, already admitted and already spent (a real one-shot marker
was created and real SSH observations executed against it, so it cannot
be retried regardless of this fix), is permanently pinned to the old
`collector_v2` wiring and can never be executed by this fix either. An
**eleventh** real `S17-EXT-001` admission, against this new chain, will
be required before a real execution can succeed. Sealing a new real
bundle (mirroring `v8` through `v12`) containing this fix is also
required, and the new bundle's extracted tree will need to be staged on
the stand again, exactly as `v12`'s was.

## Effects

Fixes the real, reproduced, deterministic `REMOTE_NONZERO_EXIT`/`runtime
file` failure that stops the fixed action plan's fifth observation from
ever passing on any real host where `/usr/bin/python3`, `/usr/bin/
sha256sum`, or `/usr/bin/uname` is a symlink -- ordinary, not exotic,
Linux packaging. Narrowly scoped: only `OBSERVATION_IDS[4]`'s handling of
the three fixed *system*-tool paths changes; the three bundle-binary
paths in the same observation, every other observation, and the whole
SSH/fixed-action-plan structure are unchanged. Does not weaken bundle
integrity verification in any way -- the sealed bundle's own binaries
still must be plain, non-symlink files. Does not by itself make the
tenth resolution executable (it is pinned to `collector_v2` forever, same
structural reason as every prior ADR in this chain); it only removes a
defect that would otherwise reproduce on any real host, including an
eleventh resolution admitted after this fix.

## Verification and supersession

Acceptance requires: a positive regression proving `collector_v3.render_
observation_program` for `OBSERVATION_IDS[4]` accepts a symlinked
system-tool path (a real `os.symlink` fixture, not a mock) and records
the resolved target's real size/sha256, while still rejecting a
symlinked bundle-binary path exactly as `v2`/`v1` already do; a
regression proving `v2`'s own chain (and `check_stage17_executor_v13`
through `v18_action_readiness.py`) remain completely unaffected and
importable/usable exactly as before; confirmation via `git diff` that no
file in any previously accepted or accepted-adjacent closure changed.
Any later change to the fixed action plan's runtime-tool-identity
semantics requires another prospective successor under the same standard
applied since ADR-0108.
