# ADR-0129: Stage 17 EXT-002 release-receipt profile recognition

- **Status:** `PROPOSED`
- **Decision ID:** D-129
- **Classification:** implementation correctness, latent gap in already-
  accepted production code, `S17-EXT-002` admission
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-002` transaction can admit evidence
  captured from a `STAGE17-PILOT-CANDIDATE-BUNDLE-v5` or later archive

## Context

ADR-0128 fixed `S17-EXT-006` archive/sidecar admission's rejection of
bundle profiles newer than `v4`, by minting `stage17_pilot_candidate_
artifact_v5.py` and a new outer semantic-verifier successor (`v22`)
overriding the `S17-EXT-006` dispatch. Continuing the hermetic rehearsal
past that fix, `ext002()` failed at the same root cause through a
*different* call site that ADR-0128 did not touch: real `S17-EXT-002`
admission (`stage17_operational_semantics_v4.py`'s `verify_manifest_v4`,
`S17-EXT-002` branch) calls `_verify_extracted_release`, which calls
`release_verifier.verify_extracted_release_receipt_v4` --
`stage17_pilot_candidate_artifact_v4.py`'s own `verify_extracted_release_
receipt_v4`, confirmed to internally call the same frozen
`verify_extracted_bundle_v4` whitelist ADR-0128 already found (exactly
two accepted strings: `STAGE17-PILOT-CANDIDATE-BUNDLE-v4` and
`STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2`).

Both `stage17_operational_semantics_v4.py` and
`stage17_pilot_candidate_artifact_v4.py` are part of the frozen, accepted
`v18` closure and cannot be edited in place. Traced directly (not
assumed): within `verify_manifest_v4`'s ~240-line body, exactly one call
site touches the release verifier -- the `S17-EXT-002` branch's call to
`_verify_extracted_release` -- confirmed by searching the full function
body for `release_verifier`/`verify_extracted` references. Every other
branch (`S17-EXT-003`, `004`, `005`, `007` through `010`) is unaffected by
this specific gap; `S17-EXT-004`/`005`/`007`'s shared `_phase_family`
helper does not reference the release verifier at all.

`stage17_pilot_candidate_artifact_v5.py` (ADR-0128, accepted) already
exists and is itself now an accepted, immutable file -- it added
`verify_extracted_bundle_v5` with the broadened whitelist but did not add
`build_extracted_release_receipt_v5`/`verify_extracted_release_receipt_v5`
equivalents, since ADR-0128's scope was `S17-EXT-006` only. This ADR
extends the artifact module one step further (`v6`) rather than editing
the accepted `v5` file.

## Decision

Add `tools/stage17_pilot_candidate_artifact_v6.py`: additive successor to
`_v5.py`, re-exporting everything unchanged, adding
`build_extracted_release_receipt_v6`/`verify_extracted_release_receipt_v6`
-- faithful copies of `_v4.py`'s same-named functions, calling
`verify_extracted_bundle_v5` (the already-broadened predecessor function)
instead of `_v4`'s narrower `verify_extracted_bundle_v4`.

Add `tools/stage17_operational_semantics_v5.py`: additive successor to
`_v4.py`, re-exporting everything unchanged, adding
`_verify_extracted_release_v5` (a faithful copy of `_verify_extracted_
release`, calling the new `stage17_pilot_candidate_artifact_v6.verify_
extracted_release_receipt_v6` in place of `_v4`'s) and `verify_manifest_v5`
(a faithful copy of the full `verify_manifest_v4` body, with only the
`S17-EXT-002` branch's call retargeted to `_verify_extracted_release_v5`
-- every other branch byte-identical).

Add a new outer semantic-verifier successor (the next version after
`v22`) that, in addition to `v22`'s existing `S17-EXT-006` override, adds
an `S17-EXT-002` override routing to a new `verify_operational_manifest_v5`
(a faithful copy of `stage17_semantic_verifier_v14.py`'s
`verify_operational_manifest`, retargeted to call `stage17_operational_
semantics_v5.verify_manifest_v5` instead of the frozen `_v4.verify_
manifest_v4`). Every other input still delegates down the predecessor
chain unchanged. A new operational-policy successor binds the new
modules' real hashes, following the same additive pattern as every prior
successor.

## Effects

Evidence captured from a `v5`/`v6`/`v7` (or later) sealed bundle becomes
admissible for a real `S17-EXT-002` transaction through the newest
successor chain. No scientific design, integrity requirement, or
authority boundary changes -- this only teaches the release-receipt
profile-recognition step to accept byte-identical newer profile
identities it previously rejected by string equality alone, mirroring
exactly what ADR-0128 already did for the separate `S17-EXT-006` call
site. This does not authorize a real `S17-EXT-002` transaction; it only
removes a defect that would have blocked one.

## Verification and supersession

Acceptance requires: a regression proving the unmodified `v18`/`v14`/`v4`
chain is completely unaffected; a hermetic-rehearsal test proving
`ext002()` now succeeds against a real sealed `v7` bundle through the new
successor chain; confirmation via `git diff` that no file in the accepted
`v18` closure changed. Any later new bundle profile, or any other
`verify_manifest_v4` branch found to share this defect class, requires
another prospective successor under the same standard applied since
ADR-0108.
