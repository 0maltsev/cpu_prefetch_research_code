# ADR-0128: Stage 17 pilot-candidate artifact profile recognition

- **Status:** `PROPOSED`
- **Decision ID:** D-128
- **Classification:** implementation correctness, latent gap in already-
  accepted production code, `S17-EXT-006` archive/sidecar admission
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-006` transaction can admit a
  `STAGE17-PILOT-CANDIDATE-BUNDLE-v5` or later archive

## Context

While continuing the hermetic Stage 17 rehearsal through `S17-EXT-002`,
`tools/stage17_pilot_candidate_artifact_v4.py`'s `verify_extracted_bundle_v4`
was found to hardcode an exact-match profile whitelist of exactly two
strings: `STAGE17-PILOT-CANDIDATE-BUNDLE-v4` and
`STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2`. Confirmed directly: this predates
tonight's work entirely and already did not recognize the
`STAGE17-PILOT-CANDIDATE-BUNDLE-v5` real candidate profile sealed under
ADR-0126, let alone the `v6` profile sealed after this evening's
production promotion.

This module is part of the already-accepted, hash-pinned `v18` closure
(`stage17_pilot_candidate_artifact_v4` appears in
`stage17-operational-evidence-admission-policy-v18.json`'s
`runtime_closure`, confirmed directly), so it cannot be edited in place.
Tracing its real callers found the gap is not confined to this one file:
`verify_pilot_candidate_artifact_v4` (the function `S17-EXT-006`
admission actually calls) internally calls `verify_extracted_bundle_v4`,
and the caller of `verify_pilot_candidate_artifact_v4` for real
`S17-EXT-006` admission is `verify_s17_ext_006` in
`tools/stage17_semantic_verifier_v14.py` -- which is *also* part of the
frozen `v18` closure, and is still the function every successor built
tonight (`v19`/`v20`/`v21`'s outer `verify_input`) delegates
non-`S17-EXT-001` inputs down to, because none of tonight's successors
overrode the `S17-EXT-006` dispatch specifically (only `S17-EXT-001`).
This means a bundle sealed under any profile newer than `v4` cannot
currently pass real `S17-EXT-006` admission even through the now-promoted
`v21` chain, until this ADR's fix is wired all the way through.

## Decision

Add `tools/stage17_pilot_candidate_artifact_v5.py` as an additive
successor to `_v4.py`, re-exporting everything unchanged except
`verify_extracted_bundle_v4`'s (renamed `_v5` in the new module, with a
`_v4` compatibility alias where the existing call convention needs it)
profile whitelist, extended to also accept `STAGE17-PILOT-CANDIDATE-
BUNDLE-v5`, `STAGE17-PILOT-CANDIDATE-BUNDLE-v6`, and
`STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3` (the dry-run successor already
sealed earlier tonight while promoting the chain). `VERIFIER_ID` and
`VERIFIER_VERSION` stay exactly `"STAGE17-PILOT-CANDIDATE-EXTERNAL-
VERIFIER"` / `"4"`, unchanged -- this identity represents a stable
protocol-level identity that `verify_s17_ext_006`-equivalent dispatch
compares against, not a literal file-version tag, matching the same
"frozen historical anchor" pattern ADR-0126 already established for the
envelope's `semantic_verifier` field.

Add a new outer semantic-verifier successor (the next version after `v21`)
that, unlike every prior successor tonight, overrides `S17-EXT-006`
dispatch specifically -- not just `S17-EXT-001` -- routing it to a new
`verify_s17_ext_006`-equivalent bound to
`stage17_pilot_candidate_artifact_v5.py` instead of the frozen `_v4.py`.
Every other input's dispatch continues delegating down the predecessor
chain unchanged. A new operational-policy successor binds the new
artifact-verifier's and outer-verifier's real hashes, following the exact
same additive pattern as `v19` through `v21`.

## Effects

A bundle sealed as `STAGE17-PILOT-CANDIDATE-BUNDLE-v5` or `v6` (or the
`v3` dry-run profile) becomes admissible for a real `S17-EXT-006`
transaction through the newest successor chain. No scientific design,
archive/sidecar integrity requirement, or authority boundary changes --
this only teaches the profile-recognition step to accept byte-identical
newer profile identities it previously rejected by string equality alone.
This does not authorize a real `S17-EXT-006` transaction; it only removes
a defect that would have blocked one.

## Verification and supersession

Acceptance requires: a regression proving the unmodified `v18`/`v14`/`v4`
chain is completely unaffected and still correctly rejects/accepts
exactly what it did before; positive tests that `v5` and `v6` (and dry-run
`v3`) profiles now pass through the new successor; a negative test that
an unrecognized profile string still correctly fails closed; confirmation
via `git diff` that no file in the accepted `v18` closure changed. Any
later new bundle profile requires another prospective successor under
the same standard applied since ADR-0108.
