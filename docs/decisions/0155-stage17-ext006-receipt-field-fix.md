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

Add `verify_s17_ext_006` to `tools/stage17_semantic_verifier_v41.py`
**in place**, rather than as a new `v42` successor (an earlier version of
this ADR did exactly that, then reverted it -- see the correction below).
It is a faithful copy of the predecessor `v40`'s own version, changed
only to read `receipt.get("artifact_locator", "")` instead of the stale
`contract_path`. Every other check -- verifier identity, the `S17-
EXT-003` release cross-check, the `synthetic_test_only` classification
check -- is byte-identical to the predecessor.

Purely a Python fix to the admission-time verifier -- no C++ or schema
changed, so it is patched directly onto `standv2-18`'s live
admission-root the same way ADR-0154's own CLI fix was, without
requiring a rebuild or reseal, preserving the journal's already-admitted
`S17-EXT-001` through `S17-EXT-005` (the first honest `S17-EXT-004`/
`S17-EXT-005` pairing this engagement has ever achieved) and its
real, already-completed live Q15-R/Q15-W measurements.

**Correction, found by testing against a disposable copy of the real,
in-flight journal before touching the live stand (the same discipline
that caught this fix's own subject bug):** the first version of this
change created `tools/stage17_semantic_verifier_v42.py` as a new,
additive successor and moved `stage17_state_journal_v35.py`'s own
`semantic` import to it -- the same pattern ADR-0153 and ADR-0154 both
used successfully. For an already-in-flight journal this is unsafe:
`S17-EXT-001`'s own already-admitted envelope pins `state_journal_
v35.py`'s exact bytes (transitively, via the read-only-preflight
policy's `IMPLEMENTATION_PATHS`), and editing that file's import line --
to point at *any* new module -- changes those bytes and breaks that
binding, confirmed for real: `stage17-operational: FAIL: S17-EXT-001
policy binding mismatch`. Reverted the `state_journal_v35.py` edit and
the `v42` file, and instead edited `stage17_semantic_verifier_v41.py`'s
own body in place. This works because `S17-EXT-001`'s binding never
references `v41.py`'s bytes directly, only `state_journal_v35.py`'s
import line -- and `v41.py` was authored and deployed entirely within
this same session, for this same journal's own use, so nothing else
depends on its bytes staying frozen. This is a deliberate, narrow
exception to the codebase's usual "never edit an already-accepted file
in place" convention, not a general precedent: `v22`/`v34`/`v39`/`v40`
and every other file genuinely shared across journals or bundles still
require a fresh additive successor for any real change.

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
- A third real, previously-uncaught lesson from this same investigation:
  "purely a Python fix, no rebuild needed" does not by itself mean a fix
  is safe to patch onto an in-flight journal. Whether it moves an
  orchestration-layer import binding (state_journal's own `semantic`
  import, the CLI's own `pilot_artifact`/`semantics_v6` imports) matters
  independently, because only those files' bytes are what `S17-EXT-001`'s
  own admitted binding actually pins.
