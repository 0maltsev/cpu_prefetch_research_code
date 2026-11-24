# ADR-0126: Stage 17 no-predecessor-attestation executor binding

- **Status:** `ACCEPTED`
- **Decision ID:** D-126
- **Classification:** implementation correctness, action-time admission,
  executor/verifier call-site binding
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any `S17-EXT-001` transaction using the D-124
  no-predecessor-attestation branch may reach action-time evaluation
  through the real stand-facing executor

## Context

ADR-0125 wired the D-124 no-predecessor-attestation branch into a new
policy successor (v19) whose resolution-time admission correctly resolves
either predecessor-evidence branch of a `stage17-read-only-preflight-
supporting-contract/13` document. Policy v19's own `runtime_closure`,
however, still bound the unchanged `tools/stage17_read_only_preflight_
executor_v12.py`, which imports `stage17_read_only_preflight_semantic_
verifier_v14` as `current_semantic` and calls
`current_semantic.evaluate_s17_ext_001_action_readiness_v14(...)` at
action time, immediately before opening the real transport.

`stage17_read_only_preflight_semantic_verifier_v15.py` (ADR-0124) never
defined an `evaluate_s17_ext_001_action_readiness_v14` (or `_v15`)
function; its action-time-relevant public surface was limited to
`verify_s17_ext_001_semantics_v15`, called from the journal layer at
resolution time, not from the executor's action-time call site. Binding
executor v12 unchanged into policy v19's closure meant that even a fully
valid attestation-branch contract, once admitted, would crash the
executor's action-time check with `AttributeError` before transport --
the real defect this ADR fixes, discovered by inspection before any code
was written to paper over it. This is the same class of predecessor/
successor call-site mismatch that ADR-0121, ADR-0122, and ADR-0123 each
fixed on this exact call site (D-120's `KeyError` on a 17-property attempt
schema, D-121's marker-only stop on adopted-child reaping, D-122's
action-time `KeyError` on `record_schema_bindings`); it is treated with
the same rigor here, not as a quick two-line import swap.

A separate, initial assumption that this component required a dual-
disassembler generated-code audit (the verification method ADR-0121-0123
used for the compiled runner packages) was checked and found incorrect:
`stage17_read_only_preflight_executor_v12.py` and its successor are pure
Python, not compiled C++, and no such audit tooling exists or applies to
them. The real, load-bearing verification for this component is
regression testing plus the binding-check pattern already used by
`check_stage17_action_revalidation_binding.py` for the equivalent D-122
fix.

## Decision

Add `evaluate_s17_ext_001_action_readiness_v15` to
`stage17_read_only_preflight_semantic_verifier_v15.py`. It is a faithful
copy of predecessor `evaluate_s17_ext_001_action_readiness_v14` for every
check unrelated to which predecessor-evidence branch the bound contract
uses -- `_reverify_current_action_inputs` is reused unmodified from v14,
since it never inspects the blocker/attestation fields. Only the branch-
specific re-verification and its resulting file bindings differ, selected
by the same `classify_predecessor_evidence` helper already used at
resolution time, so action-time and resolution-time can never disagree
about which branch a contract uses. The three-blocker branch calls the
same three unmodified `_verify_pre_marker_predecessor`/
`_verify_post_marker_predecessor`/`_verify_action_revalidation_predecessor`
helpers v14 already used, in the same order, appending the same three file
bindings. The attestation branch calls the already-implemented and
already-tested `_verify_no_predecessor_attestation` helper and appends one
file binding for the attestation record.

Add `tools/stage17_read_only_preflight_executor_v13.py`, byte-identical to
v12 except: its `current_semantic` import binds
`stage17_read_only_preflight_semantic_verifier_v15` instead of `_v14`; its
`current_journal` import binds `stage17_state_journal_v17` instead of
`_v16`, so resolution-time and action-time validation are on the same
chain generation; its action-time call site invokes
`evaluate_s17_ext_001_action_readiness_v15` (the version-matched name,
following the established convention where each executor generation calls
the function named for the verifier generation it imports -- v8 to v10,
v9 to v11, v10 to v12, v11 to v13, v12 to v14, now v13 to v15); and its
`EXECUTOR_ID` constant is updated to `v13` to accurately self-identify.
No transport, timeout, deadline, subreaper, or cleanup logic changes.

A new policy successor (v20) binds executor v13's real hash into
`runtime_closure` in place of executor v12's, and its verification
explicitly rejects a closure that still contains the superseded v12 entry
point, so this defect class cannot silently reappear by a future policy
accidentally reverting to the old executor. Policy v19 and its entire
existing closure remain byte-identical and independently valid.

## Effects

The D-124/D-125 no-predecessor-attestation branch, and the unchanged
three-blocker-receipt branch, both become reachable at action time through
the real stand-facing executor. No scientific design, transport mechanics,
credential handling, or authority boundary changes. This ADR does not by
itself promote policy v20 to be the production-current policy; that
remains a separate, explicit decision, exactly as ADR-0125's promotion
step required a distinct owner confirmation from its acceptance.

## Verification and supersession

Acceptance requires: a regression proving the unmodified v12/v14/v16/v18
chain is completely unaffected and still independently passes everything
it passed before; a regression reproducing the exact `AttributeError`
this ADR fixes, as a permanent guard against silent recurrence; positive
tests for both v13-chain branches (three-blocker path still succeeds
unchanged; attestation path now succeeds); the full existing Stage 17
test suite; sanitizers where applicable. Any later change to the
executor's transport, credential, or process-lifecycle mechanics requires
another prospective successor under the same standard this repository has
applied since ADR-0108.
