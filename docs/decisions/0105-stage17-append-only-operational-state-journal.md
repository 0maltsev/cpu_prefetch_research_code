# ADR-0105: Append-only Stage 17 operational state journal

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-26
- Decision ID: `STAGE17-STATE-JOURNAL-v1` (directly instructed defect
  correction; not a D-109/D-110 decision-only bundle)
- Classification: operational state persistence, evidence identity, release
  custody, and lifecycle admission
- Decision owners: repository, pilot, platform, release, custody, and audit
  owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: ADR-0104 only where its v1 successor/checklist representation
  embedded mutable current state and input status; its finite graph, pilot role
  collapse, no-retry rule, and strict Stage 18 boundary remain accepted
- Lifecycle gate: before `S17-EXT-001` or any operational transition

## Context and scientific constraints

The immutable ADR-0104 successor schema admits only `current_state=PREPARED`,
so it cannot persist its first valid transition. Its checklist also combines
requirement definitions with mutable resolution status, and the successor
binds that whole checklist hash. The old checker accepted a string artifact ID
and syntactically valid SHA-256 without reading evidence bytes. Historical
D-099 through D-108 evidence, ADR-0104, successor v1, and checklist v1 must not
be rewritten to correct those implementation defects.

The imported Stage 18 sealing/access chronology remains scientific authority.
No pilot record may weaken, skip, or authorize that chronology.

## Options considered

1. Rewrite the historical successor/checklist after every state/input change.
2. Keep mutable status in one file and weaken hash checking.
3. Preserve definitions, derive state from a hash-chained append-only journal,
   and resolve immutable catalog entries with separately hashed evidence
   records whose real bytes are verified.

## Decision

Select option 3. `STAGE17-OPERATIONAL-GRAPH-v1` is the immutable finite graph,
and `STAGE17-EXTERNAL-INPUT-CATALOG-v1` is the immutable ten-item requirement
catalog. The repository begins with one genesis journal snapshot in
`PREPARED`. Each successor snapshot adds exactly one resolution or transition
reference, binds its predecessor snapshot, and retains an exact prefix of all
prior references. Current state is computed only by replaying the three
adjacent transition records from the canonical genesis hash.

Repository evidence is a repository-relative regular nonsymlink file whose
actual size and SHA-256 are recomputed. External evidence requires a real
absolute regular nonsymlink artifact, a real repository receipt, size/hash,
custody locator, verifier identity/version, verification result, and a real
hash-bound contract. `S17-EXT-006` additionally requires caller-supplied exact
archive and sidecar bytes under its fixed contract; metadata-only legacy
release evidence cannot resolve it.

The initial journal has no resolutions and no transitions. Therefore all ten
inputs, including `S17-EXT-006`, are `EXTERNAL_REQUIRED`; state is `PREPARED`
and pilot readiness is false. No timestamp, owner approval, target locator,
signature, stand result, or execution authority is fabricated.

## Evidence

- Direct owner instruction identifying the four confirmed persistence and
  evidence-validation defects.
- Disk-backed full-chain fixtures that close and reload 10 resolution records
  and three transitions from an isolated directory.
- Negative fixtures for missing/extra inputs, skip/backward transitions,
  predecessor replacement, fork, duplicate/replay, unknown/expired authority,
  graph change, Stage 18 chronology weakening, missing external bytes, and
  `artifact_id=DOES-NOT-EXIST` plus SHA-256 `"a" * 64`.
- Immutable SHA-256 checks for ADR-0104, successor v1, checklist v1, and the
  D-099..D-108 preservation manifest.

## Consequences and compatibility

Scientific effect: none. No treatment, queue operation, schedule, timing
boundary, calibration value, outcome, estimand, or access order changes.

Compatibility effect: graph, catalog, schema-version hashes, canonical genesis
hash, resolution record bytes, transition record bytes, and every journal
snapshot hash are identity. A resolution never mutates the catalog. A later
snapshot that changes a prefix, forks a predecessor, skips a state, or weakens
the Stage 18 boundary is invalid.

## Verification and acceptance tests

- Validate every schema with Draft 2020-12 and every repository evidence path
  through component-by-component `lstat` plus byte/hash checks.
- Reconstruct state from genesis and a sequential predecessor/hash chain only.
- Reject missing, duplicate, replayed, forked, expired, changed-definition, and
  Stage-18-widening records.
- Keep the actual checked-in genesis at `PREPARED`, with 0 resolutions, 0
  transitions, 10 missing inputs, and `pilot_ready=false`.
- Validate actual pilot-candidate archive/sidecar bytes only through the
  explicitly invoked integration checker.

## Rollback or supersession

Never rewrite the graph, catalog, genesis, or a completed record/snapshot.
Stop and retain partial evidence. A prospective versioned graph/catalog/schema
may supersede this ADR only while preserving the full predecessor lineage.
Any scientific or Stage 18 chronology change also requires protocol review and
an amendment where applicable.

## Protocol-amendment assessment

No protocol amendment is required. This corrects implementation-owned pilot
state persistence and evidence verification while preserving every imported
scientific and confirmatory rule.
