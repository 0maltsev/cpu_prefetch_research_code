# 0138. Stage 17 S17-EXT-002 manifest schema-binding completion

Status: ACCEPTED

## Context

ADR-0136 corrected `stage17_operational_semantics_v6.py`'s `ROLE_SCHEMA_v6`
so that `S17-EXT-002` manifest authoring (`author-manifest`) validates
`PREFLIGHT_ATTEMPT`/`PREFLIGHT_OBSERVATION_RECEIPT`/`PREFLIGHT_COMPLETION`
artifacts against the real executor's current record schemas
(`stage17-read-only-preflight-attempt-v10.schema.json`,
`-observation-receipt-v7.schema.json`, `-completion-v7.schema.json`)
instead of the frozen `-v7`/`-v5`/`-v5` schemas ADR-0126 had pinned. That
fix made `author-manifest` succeed for the first time.

It did not, however, update `author_stage17_policy_v30.py`'s
`SUCCESSOR_BINDINGS`, which separately pins the exact schema *file bytes*
`stage17_operational_semantics_v6.verify_manifest_v6` requires each
manifest artifact's schema to be drawn from (the `pinned` dict
`stage17_semantic_verifier_v30.verify_operational_manifest_v6` builds
from `policy["bindings"]`/`policy["runtime_closure"]`, checked against
via `pinned_binding_bytes`). Policy v30 (and its untouched-by-ADR-0137
successor v31) still only pins the old `-v7`/`-v5`/`-v5` schema files;
`author-manifest`'s own `ROLE_SCHEMA_v6` check moved on, but the
admission-time policy binding it depends on for `admit-resolution`
never did.

This was never previously exercised: this session's first real
`author-manifest` attempt (which surfaced ADR-0136) never got past
manifest *authoring* to real resolution *admission*. It was only the
first real `admit-resolution --input-id S17-EXT-002` attempt against a
correctly-authored manifest -- performed locally, with no stand contact
of any kind, since S17-EXT-002 admission is pure evidence recording --
that reproduced the real failure:

```
stage17-operational: FAIL: schema is not policy-pinned: config/schemas/stage17-read-only-preflight-attempt-v10.schema.json
```

Confirmed by direct inspection: `stage17-operational-evidence-admission-policy-v30.json`'s
`bindings` contains `stage17-read-only-preflight-attempt-v7.schema.json`,
`-observation-receipt-v5.schema.json`, `-completion-v5.schema.json` --
the exact schemas ADR-0136 moved `ROLE_SCHEMA_v6` away from -- and no
entry at all for the `-v10`/`-v7`/`-v7` schemas the real executor
actually produces. This is the same lockstep-move class of gap ADR-0130
and ADR-0137 already found and fixed elsewhere in this chain: fixing the
code path that *selects* a schema is necessary but not sufficient when a
separate policy-side allowlist must also be told the new schema exists.

## Decision

Add a new, additive-successor outer policy generation, `v32`, whose only
change from `v31` is pinning the three real record schemas
`ROLE_SCHEMA_v6` already requires
(`stage17-read-only-preflight-attempt-v10.schema.json`,
`-observation-receipt-v7.schema.json`, `-completion-v7.schema.json`) into
its `bindings`. No Python logic changes: `stage17_semantic_verifier_v32.py`
is a pure rebind of `v31` (`POLICY_PATH`/`POLICY_SCHEMA`/
`VERIFIER_VERSION` only, `verify_input` delegated unchanged), with one
added self-test assertion that the three schemas are present in
`policy["bindings"]`. `stage17_state_journal_v28.py` moves the semantic
import to `v32` to keep it reachable from real `admit-resolution` calls,
and `stage17_operational_cli_v11.py`'s `journal_runtime` moves to `v28`
in lockstep, exactly as ADR-0130/ADR-0137 already established for this
class of fix.

`S17-EXT-001`'s own admission chain (executor v20, collector v3,
preflight-plan policy v22) is completely unaffected; `S17-EXT-002`'s own
manifest-authoring logic (`ROLE_SCHEMA_v6`, `verify_manifest_v6`) is
completely unaffected -- this closes a policy-pinning gap only.

## Consequences

- A fourth real `admit-resolution --input-id S17-EXT-002` attempt against
  the thirteenth admission root, now targeting policy v32, is expected to
  reach real schema/hash verification of the already-authored manifest
  instead of failing on an unpinned schema.
- The recurring lockstep-completeness lesson holds: whenever a semantic
  verifier's role-to-schema (or module-to-import) table moves, every
  separate policy-side allowlist that also names the old target must be
  audited and moved in the same change, not left to be found by the next
  real admission attempt that happens to reach it.
