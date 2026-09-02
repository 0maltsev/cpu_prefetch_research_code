# ADR-0136: Stage 17 S17-EXT-002 preflight role schema versions

- **Status:** `ACCEPTED`
- **Decision ID:** D-136
- **Classification:** implementation correctness, latent defect predating
  this session, admission-side role-to-schema table never updated as the
  read-only preflight record schemas moved forward
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-002` admission can accept a manifest
  built from any real `S17-EXT-001` execution newer than the frozen `v7`/
  `v5` attempt/receipt/completion record generation

## Context

With `S17-EXT-001` finally resolved for real (the eleventh real admission,
ADR-0135's fix), this session attempted the first-ever real `S17-EXT-002`
admission, built entirely from real evidence: the real completed
preflight's own attempt/completion/receipt/stdout/stderr records, a real
`RUNTIME_IDENTITY`/`RUNTIME_RELEASE_PROVENANCE` pair built and
independently verified against the real, sealed `v13` bundle via
`stage17_pilot_candidate_artifact_v6.verify_extracted_release_receipt_v6`,
the real worker binary, and a real `TRUST_ANCHOR`/`TRUST_ALLOWED_SIGNERS`
pair built from the owner's own real SSH public key.

The real `author-manifest` command failed immediately, on the very first
artifact:

```
stage17-operational: FAIL: config/schemas/stage17-read-only-preflight-
attempt-v7.schema.json rejection: 'cpu-prefetch-stage17-read-only-
preflight-attempt/7' was expected
```

Reading `tools/stage17_operational_semantics_v4.py`'s `ROLE_SCHEMA` table
(inherited unchanged by `stage17_operational_semantics_v5.py`'s own
`ROLE_SCHEMA_v5`, confirmed via `ROLE_SCHEMA_v5 = {**predecessor.
ROLE_SCHEMA, "RUNTIME_RELEASE_PROVENANCE": ...}` -- only that one entry
overridden) shows three stale entries:

```python
"PREFLIGHT_ATTEMPT": "config/schemas/stage17-read-only-preflight-attempt-v7.schema.json",
"PREFLIGHT_OBSERVATION_RECEIPT": "config/schemas/stage17-read-only-preflight-observation-receipt-v5.schema.json",
"PREFLIGHT_COMPLETION": "config/schemas/stage17-read-only-preflight-completion-v5.schema.json",
```

Confirmed directly against the real evidence this session's real
executor produced (`stage17_read_only_preflight_executor_v19.py`'s own
`attempt_marker_name`/`failure_name`/`completion_name`/record-schema
bindings, all unchanged in identity since ADR-0130): the real attempt
record is `cpu-prefetch-stage17-read-only-preflight-attempt/10`, the real
observation receipts are `.../observation-receipt/7`, and the real
completion record is `.../completion/7`. All three current schema files
(`-v10.schema.json`, `-v7.schema.json` for both receipt and completion)
already exist in the repository -- they were simply never wired into
`ROLE_SCHEMA`. This is not a stand-side or executor-side defect; it is
purely on the `S17-EXT-002` admission side, and it has never been caught
before because no real `S17-EXT-001` output ever existed to admit until
this session's eleventh admission succeeded.

This same stale `ROLE_SCHEMA` is read by two call sites that must both
move together: `tools/stage17_operational_cli_v11.py`'s
`author_operational_manifest` (via `semantics_v5.ROLE_SCHEMA_v5`, at
manifest-authoring time -- where the real failure above was reproduced)
and `tools/stage17_operational_semantics_v5.py`'s own `_read_artifacts_v5`
(via its module-global `ROLE_SCHEMA_v5`, at resolution-admission time).
Both must resolve the corrected table, or authoring would succeed while
admission still fails, reproducing the identical defect one step later.

## Decision

Add `tools/stage17_operational_semantics_v6.py` as an additive successor
to `stage17_operational_semantics_v5.py`, re-exporting every `v5` name
unchanged and adding `ROLE_SCHEMA_v6 = {**predecessor.ROLE_SCHEMA_v5,
"PREFLIGHT_ATTEMPT": ".../stage17-read-only-preflight-attempt-v10.schema.json",
"PREFLIGHT_OBSERVATION_RECEIPT": ".../stage17-read-only-preflight-observation-receipt-v7.schema.json",
"PREFLIGHT_COMPLETION": ".../stage17-read-only-preflight-completion-v7.schema.json"}`.
`_read_artifacts_v6` is a fresh copy of `_read_artifacts_v5` (confirmed
by exact extraction, not manual retyping), broadened only to resolve
roles through `ROLE_SCHEMA_v6` instead of `v5`'s frozen table -- the same
free-variable-resolves-via-defining-module reason `v5`'s own `_read_
artifacts_v5` needed a fresh copy rather than an alias. `verify_manifest_
v6` is a fresh copy of the complete `verify_manifest_v5` body (confirmed
by exact extraction), changed only to call `_read_artifacts_v6` instead
of `_read_artifacts_v5`; every branch for `S17-EXT-002` through
`S17-EXT-010` is otherwise byte-identical, since only artifact reading
itself depends on the stale table. `_verify_extracted_release_v5` is
reused unmodified via re-export (an alias, not a fresh copy: ADR-0134/
0135's own established rule applies -- its body reads no free variable
that varies between `v5` and `v6`, since the `RUNTIME_RELEASE_PROVENANCE`
schema binding it depends on is untouched by this fix).

`tools/stage17_operational_cli_v11.py`'s `author_operational_manifest` is
edited in place (per this repository's established precedent: no sealed
manifest or resolution pins `cli_v11.py`'s own bytes, only the preflight-
plan/operational policies' `implementations` entries do) to import
`stage17_operational_semantics_v6 as semantics_v5_current` and read
`semantics_v5_current.ROLE_SCHEMA_v6` instead of `semantics_v5.
ROLE_SCHEMA_v5` at its one call site.

`tools/stage17_semantic_verifier_v30.py` is an additive successor to
`stage17_semantic_verifier_v29.py`, redefining `verify_input` for the
first time since `v23.py` first introduced the generic `S17-EXT-002`
through `S17-EXT-010` manifest dispatch: identical to `v23`'s own
`verify_input` except importing `stage17_operational_semantics_v6 as
operational` and calling `operational.verify_manifest_v6` instead of
`operational.verify_manifest_v5`. `S17-EXT-001`'s own dispatch (delegated
to `predecessor.verify_input`, itself falling through to `v29`'s
`_verify_ext001`) is completely untouched.

`config/stage17/stage17-operational-evidence-admission-policy-v30.json`
(authored from `v30.py`'s own `runtime_import_roots`/bindings, mirroring
`v29`) binds the new files' real hashes; `cli_v11.py`'s own edit above
is picked up transitively, the same way every prior promotion has picked
up its own wiring edits. This ADR does not touch the preflight-plan
policy (`stage17-read-only-preflight-evidence-admission-policy-vNN.json`)
at all -- `S17-EXT-001`'s own admission chain, its executor, collector,
and semantic verifier are completely unaffected; only the outer registry
and the generic operational-manifest admission path move.

## Effects

Fixes the real, reproduced schema-rejection failure that stops any real
`S17-EXT-002` manifest from ever being authored from real `S17-EXT-001`
output, on any real host, at the very first artifact. Narrowly scoped:
only three `ROLE_SCHEMA` entries change, and only for the two call sites
that read them; every other role, every other external input's manifest
handling, and the entire `S17-EXT-001` admission chain (executor,
collector, semantic verifier, preflight-plan/operational policies
through `v21`/`v29`) are completely untouched. Does not by itself
guarantee the rest of a real `S17-EXT-002` admission succeeds -- the
deeper field-level checks in `_validate_preflight` (record field names,
not just schema identity) have never been exercised against real `v10`/
`v7` records either, and may themselves need a further successor if they
also drifted; this ADR fixes only the confirmed, reproduced schema-
identity rejection, not any later failure a retried real admission might
still surface.

## Verification and supersession

Acceptance requires: a positive regression proving `author_operational_
manifest`, run against the real, admitted `S17-EXT-001` attempt/
completion/receipt records this session's eleventh admission actually
produced, accepts `PREFLIGHT_ATTEMPT`/`PREFLIGHT_OBSERVATION_RECEIPT`/
`PREFLIGHT_COMPLETION` artifacts without a schema rejection; a regression
proving `v5`'s own chain (and every `check_stage17_*` regression already
established for `S17-EXT-001`) remain completely unaffected and
importable/usable exactly as before; confirmation via `git diff` that no
file in any previously accepted or accepted-adjacent closure changed,
and specifically that the preflight-plan policy chain (`v21`/`v29`) is
untouched. Any later change to the operational-manifest role-schema table
requires another prospective successor under the same standard applied
since ADR-0108.
