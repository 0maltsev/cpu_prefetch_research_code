# ADR-0158: Stage 17 S17-EXT-001 preflight-policy binding fix

- **Status:** `ACCEPTED`
- **Decision ID:** D-158
- **Classification:** implementation correctness, latent defect in
  already-accepted production code, action-time reachability gap
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` authored after ADR-0157 can
  actually be admitted

## Context

The real, live standv2-22 journal was the first ever authored against
an admission root carrying ADR-0157's own fix (`cli_v11.py`'s `author-
ext001` now embeds `S17-EXT-001`'s envelope `semantic_policy` field from
`...policy-v28.json`). `author-ext001` itself succeeded for real
(`stage17-operational: PASS ext001_envelope=...`), but the immediately
following `admit-resolution --input-id S17-EXT-001` failed for real:
`stage17-operational: FAIL: S17-EXT-001 policy binding mismatch`.

Root-caused by direct code tracing, not assumed: `verify_input`'s own
`S17-EXT-001` branch is not handled by any of `stage17_semantic_verifier
_v39.py`'s successors (`_v40` through this session's own `_v42`/`_v43`)
-- it is intercepted once, terminally, inside `_v39.py` itself, via a
private `_verify_ext001` helper that reads `preflight.POLICY_PATH` and
calls `preflight.verify_policy_v27`/`preflight.verify_s17_ext_001_
semantics_v27`, where `preflight` is `_v39.py`'s own hardcoded `import
stage17_read_only_preflight_semantic_verifier_v27 as preflight` --
completely independent of `cli_v11.py`'s own `author-ext001` reference,
and never touched by either ADR-0156 or ADR-0157. So `author-ext001`
embedded `...policy-v28.json`'s binding into the envelope, while
`admit-resolution`'s own admission-time re-check still compared it
against `...policy-v27.json`'s -- a real, third, independent hardcoded
reference to the preflight-plan-policy generation, only reachable (and
therefore only observable) once a journal's `author-ext001` had already
moved past `v27`, which had never happened before `standv2-22`.

This is unrecoverable for standv2-22's own journal: `append_resolution`
writes the resolution record via exclusive create before running the
validation that failed (confirmed directly from `stage17_operational_
cli_v11.py`'s own code: the `_write_exclusive_at` call precedes the
`journal_runtime.validate_operational_journal` call that raised), so
that record is permanently, unrecoverably present. This mirrors exactly
the precedent ADR-0156's and ADR-0157's own Context sections already
recorded: a fresh journal, authored after the complete fix exists, is
required.

## Decision

Add, as an additive successor:

- `tools/stage17_semantic_verifier_v44.py`: re-exports every `v43` name
  unchanged except it monkey-patches `stage17_semantic_verifier_v39.
  preflight` to `stage17_read_only_preflight_semantic_verifier_v28`
  (ADR-0157's own file) rather than redefining `_verify_ext001`/`verify_
  input`, using the exact same technique `stage17_read_only_preflight_
  executor_v26.py` already used for `current_journal`: neither function
  needs its own logic to change, only which sibling module `preflight`
  refers to, and both already access it purely by attribute. `verify_
  policy_v44` adds one check beyond `v43`'s own (`v39.preflight is
  preflight`) confirming the monkey-patch actually took, on top of
  `v43`'s own required-file/closure checks, otherwise unchanged.
- `tools/stage17_state_journal_v38.py`: identical to `stage17_state_
  journal_v37.py` except importing `stage17_semantic_verifier_v44` as
  `semantic`.
- `tools/stage17_operational_cli_v11.py`'s `journal_runtime` import
  moves to `_v38` in place (this file's own established, now 30-times-
  repeated convention).
- A new outer operational-policy generation (`v44`, superseding `v43`)
  re-pins `cli_v11.py`'s latest hash. `v43.json` stays byte-for-byte
  frozen: standv2-22's own `S17-EXT-001` resolution record, though its
  admission ultimately failed, is real, permanent evidence of that
  journal's state at that moment, and nothing is served by disturbing
  the file it was checked against.

## Effects

Fixes the specific, real, reproduced rejection that stopped standv2-22's
own `S17-EXT-001` from ever being admitted once ADR-0157's `author-
ext001` fix was in place. No scientific design, hardware-safety
mechanism, credential handling, transport mechanics, or admission
semantics for any `S17-EXT-00N` input's actual *content* changes --
only which preflight-plan-policy generation `S17-EXT-001`'s own
admission-time re-check compares the envelope against. This does not
make standv2-22's existing chain executable; a fresh `S17-EXT-001`
admission against policy-v44 is required before any real Q16a/Q16b/Q16c
retry.

## Verification and supersession

Acceptance requires, all confirmed for real this session: (1) direct
code tracing to the exact hardcoded `preflight` import inside `_v39.py`,
confirmed via `v39.preflight is <v28 module>` after importing `_v44.py`;
(2) `verify_policy_v44` run for real against the actual rendered
`...policy-v44.json`, confirmed `PASS`; (3) a full pre-patch rehearsal
that this time also directly simulates `_verify_ext001`'s own envelope-
binding comparison (not file-hash drift alone), confirming the `author-
ext001`-computed `semantic_policy` binding and the `admit-resolution`-
computed `policy_path`/`policy_sha256` now genuinely agree; (4) `git
diff` confirming no previously-accepted file's bytes changed except
`stage17_operational_cli_v11.py` (its own established convention) and
`stage17-operational-evidence-admission-policy-v43.json`/ADR-0157
staying byte-for-byte untouched. Any later change to which preflight-
plan-policy generation `S17-EXT-001`'s admission-time check expects
needs another prospective successor under the same standard applied
since ADR-0108.
