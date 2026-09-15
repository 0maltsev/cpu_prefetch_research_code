# 0167: `verify_stand_bundle.py`'s v22 admission-policy version was stale

## Status

Accepted

## Context

ADR-0166 re-pinned the operational evidence admission policy from v45 to
v46 (`stage17_fixed_action.cpp`'s compiled request-size bound changed
again). `tools/create_stand_bundle.py`, `tools/stage17_state_journal_v40.py`,
and `tools/stage17_read_only_preflight_executor_v27.py` were each updated to
reference v46 at that time.

`tools/verify_stand_bundle.py` was missed. It carries its own independent
`bundle_profile` -> expected-version ladder (`current_v4` .. `current_v21`,
each a boolean matched against a specific `STAGE17-PILOT-CANDIDATE-BUNDLE-
vN` string) used to determine, for a *given built bundle*, which admission
policy file it should have been built against. The `current_v21` boolean
already correctly matches `bundle_profile == "STAGE17-PILOT-CANDIDATE-
BUNDLE-v22"` (its own name is off by one from the profile string it
checks), but its associated `admission_policy_version` value was still
`45`.

Running the real, rebuilt `cpu-prefetch-pilot-candidate-2.0.0-6e3267a-
clean-6be931339b98` bundle (profile v22, real policy v46 per its own
`BUNDLE_MANIFEST.json.stage17_controller_runtime.policy.path`) through
`verify_stand_bundle.py --root .` reproduced four real failures:
`pilot candidate worker runtime identity/provenance is invalid`,
`pilot candidate policy binding is invalid`, `pilot candidate controller
closure differs from policy`, and `pilot candidate controller binding
drifted: src/runner/stage17_fixed_action.cpp` -- all traceable to the
script comparing the bundle's real, v46-based `bound_files` against an
`expected_bound` list it derived from the wrong (stale, v11-fallback, since
the version ladder's `current_v4`..`current_v21` conditions don't recognize
`v22` as `current_v4` either) or, once traced further, the intended-but-
stale v45 policy file.

This file is not one of policy v46's own hash-pinned `bindings`/
`runtime_closure` files (confirmed by inspecting
`config/stage17/stage17-operational-evidence-admission-policy-v46.json`),
so it does not require an additive successor -- it is direct build/check
tooling, edited in place here exactly like `create_stand_bundle.py` was in
ADR-0166's own follow-up commits.

## Decision

Change the `current_v21` branch of `admission_policy_version`'s ladder in
`tools/verify_stand_bundle.py` from `45` to `46`, matching the real policy
version pinned into `v22`-profile bundles since ADR-0166.

## Consequences

- `verify_stand_bundle.py --root <v22 bundle>` now reports PASS for a
  correctly-built v22/policy-v46 bundle instead of four false failures.
- The already-built `cpu-prefetch-pilot-candidate-2.0.0-6e3267a-...` bundle
  bundles the pre-fix copy of this script (its own `sha256` is unaffected
  by fixing the *source* file after the fact); the fix was also applied
  directly to the already-extracted, already-staged (local and stand-side)
  copy of `validators/verify_stand_bundle.py` under
  `release-bundle-extract-6e3267a/`, since re-cutting a whole new bundle
  purely for this one checker-tool fix was not warranted.
