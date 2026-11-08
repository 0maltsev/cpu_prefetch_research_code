# ADR-0240: One Q16a complete-context continuation after the E23 infrastructure stop

- Status: `ACCEPTED` — explicit owner continuation instruction, 2026-11-08
- Amendment: `AMEND-2.0.0-pre.3-Q16A-CONTINUATION-v1`
- Policy: `Q16A-COMPLETE-CONTEXT-CONTINUATION-v1`
- Scope: original plan `a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7` and failure receipt `a6704159e3dd2adab1598e2959202cfa5a6a0b5c9164a01fab967deeb251c7e4` only
- Scoped supersession: D037/D038 no-top-up/one-plan lineage, solely for the complete-context reuse and one 531-capture family specified below
- Immutable protocol: `protocol/2.0.0-pre.3/` and historical decisions remain unchanged

## Decision

Adopt the [versioned continuation decision](../STAGE17_EXT007_Q16A_CONTINUATION_V1_DECISION.md) and [recorded owner acceptance](../STAGE17_EXT007_Q16A_CONTINUATION_V1_ACCEPTANCE.md). The owner instructed “continue from the broken one” after explanation that a versioned continuation/reuse decision was required. This is not a new generic retry permission.

Preserve the original failed family and failed ordinal 177. Reuse contexts 0–2 only after all 177 original captures independently pass. Require proof that the infrastructure stop at ordinal 177 preceded both phase releases and produced zero raw observations. Enumerate only contexts 3–11, 59 captures each, in a new `/3` plan: local ordinal 0–530 maps to original slot 177–707. Fresh identities preserve original numeric seeds, including the explicitly authorized failed-slot seed exception. Keep scientific controls, all finite numeric bounds and D233 shared-program accounting unchanged. Only qualified release/profile references and declared cpuset path relocation may change.

A bound compatibility proof must establish unchanged measurement dependencies across the qualified workers. Old captures remain bound to their original source. Prefix validation, failure/restoration proof, compatibility, namespace history, resources and exact signed admission remain required. The next Q15/Q16 failure stops dependent work with evidence retention and restoration; no further repair/retry or top-up is authorized.

## Implementation boundary

`tools/stage17_formal_ring_continuation_v1.py` and `stage17-formal-ring-plan-v3.schema.json` validate the true 531-capture declaration. The existing ring validator gains only a private explicit continuation branch; historical `/1` and `/2` callers retain their original strict coverage. `validate_parent(plan, original_plan_bytes)` authenticates the original bytes and checks preserved prospective numeric seeds, identities, science, geometry, limits and scoped path changes. It grants no authority and does not turn referenced proofs into established evidence.

Native admission, prefix proof and composite result integration use separate versioned boundaries. No manufactured 708-capture execution plan/result and no in-place reassignment of original report identities are allowed. The mathematical D212/D230 estimator is unchanged; the new policy identifies the changed collection lineage explicitly.

## Required verification

Test exact 531 coverage and context/repetition mapping, old-version rejection, pinned incident bindings, missing prefix/compatibility references, invalid parent bytes, changed numeric seeds, original-identity collisions, changed science/geometry/bounds, path substitutions outside the five cpuset files, finite arithmetic, and no declaration-derived execution authority. Native integration must test the same order and boundaries; prefix/composite integration must reject any missing/invalid original capture, observed failed phase, incompatible source or reused report. Tests establish software behavior only. Qualification and independent original-raw validation remain operational prerequisites.
