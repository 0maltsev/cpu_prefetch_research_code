# 0153. Stage 17 EXT-006 `v21` bundle-profile recognition fix

Status: ACCEPTED

## Context

Investigating `S17-EXT-006` (the next unattempted admission after `S17-
EXT-005`'s first-ever real success on journal `standv2-14`) before
drafting any live script, rather than discovering requirements one
burned journal at a time the way `S17-EXT-005` had to be, found a real,
code-confirmed blocker rather than an admission-bookkeeping gap:

`tools/create_stand_bundle.py`'s own `STAGE17_PROFILE` constant --
`"STAGE17-PILOT-CANDIDATE-BUNDLE-v21"` -- is the literal `bundle_profile`
value every real bundle this whole engagement has built actually
carries. The real, active `S17-EXT-006` dispatcher (`verify_s17_ext_006`
in `tools/stage17_semantic_verifier_v22.py`, confirmed as the terminal
override reachable from the live policy chain through `v39` by reading
every `verify_input` predecessor hop from `v39` down) verifies the
archive via `tools/stage17_pilot_candidate_artifact_v5.py`'s
`RECOGNIZED_PROFILES` -- a frozen set of exactly `{v4, v5, v6,
HERMETIC-DRY-RUN-v2, v3}`. `v21` is not in it. The authoring side is
narrower still: `tools/stage17_operational_cli_v11.py`'s
`author-ext006-contract` calls `tools/stage17_pilot_candidate_
artifact_v4.py`'s `build_contract_v4`, whose own `verify_extracted_
bundle_v4` recognizes only `{v4, HERMETIC-DRY-RUN-v2}` -- so a live
attempt would have failed at authoring time, before ever reaching
admission.

`tools/stage17_pilot_candidate_artifact_v6.py` already lists
`"STAGE17-PILOT-CANDIDATE-BUNDLE-v21"` in its own `RECOGNIZED_PROFILES`
(ADR-0129), but was never paired with the `S17-EXT-006`-specific
contract functions (`build_contract_v4`/`verify_pilot_candidate_
artifact_v4`, last defined in `v4`, carried forward unchanged as
`predecessor`-only names in `v5`/`v6`). `v6` only retargeted the
*separate* release-receipt pair (`build_extracted_release_receipt_v6`/
`verify_extracted_release_receipt_v6`) that `S17-EXT-002`/`S17-EXT-003`
use through a different call site
(`stage17_operational_semantics_v7.py`). No accepted module ever
combined `v6`'s broadened bundle-profile whitelist with the `S17-EXT-006`
contract pair itself -- confirmed by reading every `stage17_pilot_
candidate_artifact_v*.py` file's function list directly, not inferred
from a version number.

## Decision

Add `tools/stage17_pilot_candidate_artifact_v7.py`: faithful copies of
`v4`'s `build_contract_v4`/`verify_pilot_candidate_artifact_v4`, renamed
`build_contract_v7`/`verify_pilot_candidate_artifact_v7`, retargeted only
to call `v6`'s `verify_extracted_bundle_v6` instead of the frozen `v4`
module's own narrower function. `build_contract_v4` is re-exported as a
compatibility alias (the same technique `v5.py` already used) so `tools/
stage17_operational_cli_v11.py`'s existing `author-ext006-contract` call
site keeps working after only its import line moves.

Add `tools/stage17_semantic_verifier_v40.py`: an additive successor to
`v39` that re-intercepts `S17-EXT-006` (delegating every other input,
`S17-EXT-001` included, straight to `predecessor.verify_input`) and
retargets its `release_verifier` from `stage17_pilot_candidate_
artifact_v5` to the new `v7` module. Every other check inside `verify_
s17_ext_006` is byte-identical to `v22`'s own implementation. Add
`config/schemas/stage17-operational-evidence-admission-policy-v40.
schema.json` and `tools/author_stage17_policy_v40.py`, both trivial
version-bump copies of the `v39` pair, with `v40`'s own `required`
runtime-closure set additionally pinning `tools/stage17_pilot_
candidate_artifact_v7.py`.

`tools/stage17_state_journal_v35.py` moves its own hardcoded `semantic`
import from `stage17_semantic_verifier_v39` to `_v40`. `tools/stage17_
operational_cli_v11.py` moves its own hardcoded `pilot_artifact` import
from `stage17_pilot_candidate_artifact_v4` to `_v7`. Neither file's
call sites change -- only the import bindings move, the same "cli_v11.py's
own journal_runtime moves" pattern `author_stage17_policy_v39.py`'s own
docstring already documents as the established mechanism for reaching a
new outer policy generation without editing call-site spellings. `pilot_
artifact.` is used in exactly three places in the CLI (lines 749, 753,
786 as of `v11.py`), all three exclusively on the `S17-EXT-006` path, so
retargeting the import cannot affect `S17-EXT-002`/`S17-EXT-003`, which
reach `stage17_pilot_candidate_artifact_v6.py` through the separate,
untouched `stage17_operational_semantics_v7.py` call site.

## Consequences

- Journal `standv2-14` (5 resolutions admitted: `S17-EXT-001` through
  `S17-EXT-005`) cannot carry this fix in place. Confirmed by a real,
  local test against a writable copy of its actual `admission-root`
  (never the real evidence-of-record itself): moving `stage17_state_
  journal_v35.py`'s own hardcoded `semantic` import forces `tools/
  author_stage17_read_only_preflight_policy_v27.py` to be re-rendered
  (it independently pins that exact file's bytes into its own
  `IMPLEMENTATION_PATHS["state_journal"]` binding), and the re-rendered
  policy's new bytes no longer match the `policy_sha256` `S17-EXT-001`'s
  own already-admitted journal record was validated against at admission
  time -- `stage17-operational: FAIL: S17-EXT-001 policy binding
  mismatch`. This is true even though `state_journal_v35.py`'s own
  *behavior* is completely unchanged; only its bytes moved.
- This is not a new problem this fix introduced -- it is the same reason
  every `S17-EXT-005` burn this session (`standv2-11`/`-12`/`-13`) was
  followed by a *fresh* journal rather than a retry on the same one: a
  bundle/policy-identity change always requires re-admitting the cheap
  inputs (`S17-EXT-001` through `S17-EXT-003`) against the new identity.
- An earlier version of this section claimed the already-captured real
  Q15-W hardware evidence could be reused for the fresh journal without a
  new live session. That was wrong, and reading the real captured attempt
  file directly (not inferring from code) disproves it: `standv2-14`'s
  own `stage17-q15_w-attempt-v4.json` embeds `release_resolution_id`/
  `release_resolution_sha256` bound to that journal's own specific
  `S17-EXT-003` resolution record, an `evidence_root_binding` carrying
  that journal's exact absolute evidence path and inode, and a
  `runtime_sha256` for the old worker binary -- which will differ from
  the new bundle's worker binary even though no C++ changed, because the
  binary bakes its own git commit hash into its self-attested runtime
  identity. None of these can be satisfied by a different journal. A
  fresh journal genuinely requires a fresh live `S17-EXT-004`
  (qualification-evidence artifacts can reuse the same *raw* Q15-R
  measurement bytes, just re-wrapped with the new bundle's identity, but
  the manifest itself still needs the new journal's own Q15-R session
  output), a fresh live Q15-R session, and a fresh live Q15-W session --
  the same real hardware cost every prior `standv2-N` attempt already
  paid. The real path to `S17-EXT-006` is: reseal a bundle carrying this
  fix (done), start a fresh journal, replay `S17-EXT-001` through
  `S17-EXT-003`, run a fresh live Q15-R session, admit `S17-EXT-004`, run
  a fresh live Q15-W session, admit `S17-EXT-005`, then attempt
  `S17-EXT-006`.
- This fix was found by tracing the real `verify_input` dispatch chain
  and every `stage17_pilot_candidate_artifact_v*.py` file's actual
  function list end to end, before writing or running any live script --
  the same discipline the `S17-EXT-005` admission saga (three burned
  journals, ADR history this doc's own predecessor entries record)
  established was necessary for a never-before-reached admission step.
  No hardware or one-shot action was taken to find this; the entire
  investigation was local, read-only source inspection.
