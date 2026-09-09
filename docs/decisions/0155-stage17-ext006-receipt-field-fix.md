# 0155. Stage 17 EXT-006 receipt field fix

Status: ACCEPTED

## Context

Preparing the real `S17-EXT-006` admission on journal `standv2-18` --
the first time this input has ever been attempted for real in this
engagement's history, now that `S17-EXT-004`/`S17-EXT-005` are honestly
admitted -- reading `verify_s17_ext_006`'s own body carefully (rather
than trusting that a "faithful copy... byte-identical" chain going back
to `v14` meant it had ever actually been exercised) found a real,
structural mismatch: it reads `receipt.get("contract_path", "")` to
locate the wrapped `S17-EXT-006` pilot-candidate contract document.

That field name matches the *old* `stage17-external-custody-receipt-v1`
schema, confirmed directly against that schema's own `required` list
(`contract_path`/`contract_sha256`, flat string fields). The real,
currently-active receipt schema is `v2` --
`tools/stage17_operational_cli_v11.py`'s own `author_custody_receipt`
function emits `"schema_version": "cpu-prefetch-stage17-external-
custody-receipt/2"`, confirmed against every real receipt this
engagement's admissions have actually produced (`S17-EXT-002`/`004`/
`005`). `v2`'s own schema, with `additionalProperties: false`,
restructured those two flat fields into a nested `contract: {locator,
sha256, scope}` object -- used throughout every other real admission
this engagement has made to scope the receipt to the operational
evidence root's own journal genesis file, not to locate the artifact a
receipt wraps. `receipt.get("contract_path", "")` therefore always
resolves to the empty string against any real `v2` receipt;
`verify_pilot_candidate_artifact_v7` would then fail to even open the
resulting nonsense path as a contract file.

This was never caught before because no real `S17-EXT-006` admission has
ever been attempted in this engagement's history -- `tools/stage17_
semantic_verifier_v22.py`'s own docstring already documents that even
the `v21`-profile-fixed dispatch chain "could not admit a real
`S17-EXT-006` transaction for any bundle newer than `v4`, until now" (a
different gap, ADR-0153's own subject), and every generation since,
including this session's own `v40` copy, faithfully carried the same
unexercised field read forward.

The real, wrapped `S17-EXT-006` contract document's own path is already
present on the receipt at `artifact_locator` -- the field every other
real receipt this session has used to locate what a receipt actually
wraps, and the field `author_custody_receipt` already populates from
whatever `--artifact` path is passed to `author-custody-receipt
--input-id S17-EXT-006`.

## Decision

Add `tools/stage17_semantic_verifier_v42.py`: an additive successor to
this session's own `v41` that intercepts `S17-EXT-006` specifically
(mirroring the exact scope `v22` originally established for it), with
`verify_s17_ext_006` a faithful copy of `v40`'s own version, changed
only to read `receipt.get("artifact_locator", "")` instead of the stale
`contract_path`. Every other check -- verifier identity, the `S17-
EXT-003` release cross-check, the `synthetic_test_only` classification
check -- is byte-identical to the predecessor. Add the matching
`config/schemas/stage17-operational-evidence-admission-policy-v42.
schema.json`.

Purely a Python fix to the admission-time verifier -- no C++ or schema
changed, so it is patched directly onto `standv2-18`'s live
admission-root the same way ADR-0154's own CLI fix was, without
requiring a rebuild or reseal, preserving the journal's already-admitted
`S17-EXT-001` through `S17-EXT-005` (the first honest `S17-EXT-004`/
`S17-EXT-005` pairing this engagement has ever achieved) and its
real, already-completed live Q15-R/Q15-W measurements.

## Consequences

- This is the second real, never-before-exercised bug this engagement
  found only by attempting the real thing for the first time, not by
  code review alone -- the same pattern ADR-0154's own `EXT-004`
  investigation already established. `S17-EXT-007` through `S17-EXT-010`
  remain unattempted and unverified for the same class of gap.
- The real `S17-EXT-006` receipt's `--artifact` must be the `S17-EXT-006`
  contract document itself (`author-ext006-contract`'s own output), not
  the pilot archive or sidecar directly -- `author-custody-receipt`'s
  existing `input_id == "S17-EXT-006"` special case for `verifier_id`/
  `verifier_version` already assumed this convention; this fix completes
  it.
