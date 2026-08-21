# ADR-0034: D-031 amendment import and exact Stage 12 reconciliation

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Protocol compatibility / reconciliation / run disposition
- Decision owners: Protocol owner; statistical owner; repository owner; data-integrity owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: The final-disposition limitation recorded by D-031 under `2.0.0-pre.1`; no earlier scientific rule
- Lifecycle gate: Required and accepted before Stage 12 implementation

## Context and scientific constraints

Protocol `2.0.0-pre.1` defines independent run-validity, zero-loss,
effective-tail, block-completeness, and access gates, but its closed run
manifest has only singular `BLOCKED_*` estimability summaries. It cannot encode
two simultaneous causes without losing evidence or inventing a priority. The
accepted D-031 bundle selected an exhaustive multi-cause representation and
explicitly prohibited changing validity, retry, extension, selective removal,
or complete-block replacement rules.

Stage 12 must also implement the existing exact join: accepted producer events
in logical order join to consumer observations by run identity and accepted
ordinal; the k-th accepted event must equal the k-th consumer observation;
record index is a validation field, not event identity; derived timestamps are
created only after the complete join succeeds.

## Options considered

1. Give the five singular blockers a fixed priority.
2. Permit any one applicable singular blocker.
3. Add a versioned exhaustive blocker array and a non-priority multiple summary.
4. Keep the legacy manifest and add an implementation-only sidecar.

For reconciliation, the implementation alternatives were record-index joins,
unordered key joins, best-effort partial derivation, or the protocol's exact
ordered accepted-ordinal refinement.

## Decision

Select D-031 option 3 and the protocol-fixed exact ordered reconciliation:

- preserve `protocol/2.0.0-pre.1/` byte-for-byte and import the independently
  versioned `protocol/2.0.0-pre.2/` snapshot;
- require `confirmatory_blockers` in every `2.0.0-pre.2` run manifest;
- permit exactly the five existing cause tokens, unique and sorted by
  ascending UTF-8 token bytes;
- use an empty array with `NOT_EVALUATED`, `ESTIMABLE`, or `NOT_APPLICABLE`,
  the matching singular summary for one cause, and `BLOCKED_MULTIPLE` for two
  or more causes;
- keep summary and blocker array `NOT_EVALUATED`/empty until every applicable
  gate has authoritative evidence;
- read historical `2.0.0-pre.1` records under their historical contract, emit
  new documents as `2.0.0-pre.2`, reject mixed-version record graphs, and never
  silently migrate an immutable artifact;
- retain the ADR-0025 and ADR-0029 literal `2.0.0-pre.1` derivation-domain
  labels in their frozen HMAC and decoded-deadline preimages. They are suite
  identity, not current document version; changing them would change accepted
  deterministic bytes and is not authorized by D-031;
- reconcile raw streams only by run identity plus contiguous accepted ordinal
  in producer logical order, validate record index against the immutable Stage
  6 mapping and against the k-th consumer row, and emit no joined rows when any
  mismatch exists;
- compute timing equations with the accepted Stage 8 implementation only after
  exact reconciliation passes;
- evaluate lifecycle completion, validity, join, count reconciliation,
  zero-loss, effective-tail, and estimability as separate machine-readable
  states. `FULL` and genuine low `N_eff` remain valid retained outcomes;
- require an invalidating failure record for every `INVALID` result;
- inject, but do not invent, authoritative block-completeness and access-gate
  evidence. Their computation and chronology remain Stage 14 work.

## Evidence

- Q10 accepted the D-031 bundle as protocol and statistical owner.
- Q11 authorized protocol `2.0.0-pre.2`, preservation of `2.0.0-pre.1`, the
  import/hash verification, this implementation ADR, and Stage 12 only.
- Imported specification Sections 8.1, 8.3, 8.4, 10.5, 10.7, 10.8, 11.1,
  and 11.2; data dictionary; failure taxonomy; lifecycle and access records.
- `2.0.0-pre.1` manifest SHA-256
  `1326e1132e76dfe6f5a9a98088fa4b9b02b66514eca4d04b80a73b76ad9733ff`.
- `2.0.0-pre.2` manifest SHA-256
  `e06ac6bdc4f4d6b47a6f3c0d548f2b3b0f1088684a77cae08cbf7167800a1d76`;
  amended run-manifest schema SHA-256
  `4a8e0261e69b9b2bbf12ca070f9f07cd6afe3a6419ae9c5b8d52ef1dc52556ca`.
- Dual-snapshot inventory, authoritative-hash, Draft 2020-12, and positive/
  negative fixture checks pass with the accepted pinned validator.

## Consequences and compatibility

Scientific effect: the amendment preserves every independent gate and makes
simultaneous causes lossless. Exact reconciliation enforces already-fixed
semantics and cannot select, remove, repeat, extend, or replace observations.

Compatibility effect: the added required property and `BLOCKED_MULTIPLE` token
make final `2.0.0-pre.2` run manifests incompatible with the closed
`2.0.0-pre.1` schema. Old records remain readable only as old records. A
conversion must create a new derived artifact with explicit source lineage.
Physical raw format v1 remains usable because its byte grammar is unchanged,
but its envelope/logical schema version must match the graph being validated.

## Verification and acceptance tests

Require dual-snapshot hash/schema fixtures; legacy-read/new-write/mixed-version
tests; all mismatch classes; repeating record-index cases; exact joined-row
comparison; timestamp corruption; schedule/count/source/hash/integrity/failure
relationships; partial-failure absence; valid `FULL`; low `N_eff`; all five
simultaneous blockers; sanitizer runs; and synthetic inputs only.

Stage 12 does not claim block-level completeness, access chronology, custody,
or experiment eligibility. Those remain Stage 14/16 gates.

## Rollback or supersession

Any blocker-set, ordering, summary, gate, join identity, interval, validity,
retry, or replacement change requires a later versioned protocol amendment and
superseding ADR. Existing snapshots and artifacts remain immutable. A pure
implementation refactor requires equivalent golden, fault, semantic, and
sanitizer evidence before replacement.
