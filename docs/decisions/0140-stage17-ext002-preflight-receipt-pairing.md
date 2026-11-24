# 0140. Stage 17 S17-EXT-002 preflight receipt-to-artifact pairing

Status: ACCEPTED

## Context

With ADR-0138 and ADR-0139 clearing the schema-pinning and executor/
journal reachability gaps blocking real `S17-EXT-002` admission, the
fourteenth real admission (`stage17-operational-evidence-14`, built from
the real fourteenth `S17-EXT-001` preflight execution) reached, for the
first time ever, the semantic verifier's own preflight receipt/artifact
cross-check inside `_validate_preflight`
(`tools/stage17_operational_semantics_v4.py`, unchanged through `v5`/
`v6`) -- and failed there for real:

```
stage17-operational: FAIL: preflight receipt does not bind exact stdout/stderr bytes
```

`_validate_preflight` pairs each observation receipt to its
`PREFLIGHT_STDOUT`/`PREFLIGHT_STDERR` artifact by searching the *entire*
stdout (or stderr) artifact pool for the one entry whose hash and size
match the receipt's declared value, then requires that search to return
*exactly one* match. Direct inspection of the real evidence confirmed
why this fails unconditionally for any genuinely clean run: all six real
`stderr.bin` files from the fourteenth admission are 0 bytes (every one
of the six read-only preflight observations completed without error),
so all six are byte-identical, and the "exactly one match" search for
any given receipt returns all six matches, not one. The predecessor's
uniqueness assumption is false whenever two or more observations
legitimately produce identical output -- guaranteed for empty stderr on
any fully successful run. This was never caught before because no real
`S17-EXT-002` admission attempt had ever reached this specific check
until now; it is not related to, and not fixed by, ADR-0136, ADR-0138,
or ADR-0139.

The receipt schema itself (`stage17-read-only-preflight-observation-
receipt-v7.schema.json`) carries no artifact-id or ordinal field on the
raw `PREFLIGHT_STDOUT`/`PREFLIGHT_STDERR` manifest entries to
disambiguate them; the only correlation signal available is whatever
`artifact_id` the manifest's author chose freely per artifact.

## Decision

Add `tools/stage17_operational_semantics_v7.py`, an additive successor
to `v6` that changes only how `_validate_preflight` pairs receipts to
their stdout/stderr artifacts. `_validate_preflight_v7` requires each
`PREFLIGHT_STDOUT`/`PREFLIGHT_STDERR` artifact's own `artifact_id` to
equal `f"{observation_id}-STDOUT"` / `f"{observation_id}-STDERR"` -- a
real naming convention `author-manifest` callers must follow going
forward -- then verifies the found artifact's actual bytes still match
the receipt's declared hash/size, preserving the original integrity
check while removing the false global-uniqueness assumption.
`verify_manifest_v7` is a fresh copy of `verify_manifest_v6`'s complete
body (function aliases resolve free variables against their defining
module, so a fresh copy is required to call the new pairing function);
every other branch (`S17-EXT-003` through `S17-EXT-010`) is byte-
identical to `v6`'s own, since none of them touch preflight receipt
pairing. `_read_artifacts_v6`/`ROLE_SCHEMA_v6` are reused unmodified via
re-export.

`stage17_semantic_verifier_v34.py` re-intercepts `S17-EXT-002`
(delegating to `stage17_operational_semantics_v7.verify_manifest_v7`)
while `S17-EXT-001` and every other input's dispatch is unchanged,
delegated to `predecessor.verify_input` (`v33`, ADR-0139's own fix,
untouched by this follow-up). `stage17_state_journal_v30.py` moves the
semantic import to `v34`; `cli_v11.py`'s `journal_runtime` moves to
`v30` in the same lockstep pattern already established. This is purely
semantics-side: it does not touch the executor, collector, or
preflight-plan policy, and requires no bundle reseal -- `S17-EXT-001`'s
own admission chain is completely unaffected.

## Consequences

- The `S17-EXT-002` manifest for the fourteenth admission must be
  re-authored with the new `artifact_id` convention
  (`<observation_id>-STDOUT`/`-STDERR`) for its `PREFLIGHT_STDOUT`/
  `PREFLIGHT_STDERR` entries before `admit-resolution` can be retried.
- Any future real `S17-EXT-002` manifest authoring must follow this same
  convention; it is not yet enforced by the manifest schema itself (only
  by this semantic check), so a mismatched `artifact_id` will surface as
  the same "does not bind exact stdout/stderr bytes" error rather than a
  schema-validation error.
