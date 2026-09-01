# ADR-0124: Stage 17 no-predecessor attestation

- **Status:** `ACCEPTED_IMPLEMENTED_LOCAL_NOT_WIRED_NO_AUTHORITY`
- **Decision ID:** D-124
- **Classification:** implementation correctness, action admission, and an
  alternative evidentiary path for the `S17-EXT-001` predecessor-evidence
  input
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any `S17-EXT-001` transaction whose supporting contract
  cannot bind real D-120/D-121/D-123 blocker-receipt evidence

## Context

ADR-0121, ADR-0122, and ADR-0123 preserve the D-120 pre-marker cardinality
stop, the D-121 marker-only post-marker stop, and the D-123 action-
revalidation stop as terminal, append-only local engineering transactions.
The `stage17-read-only-preflight-supporting-contract` schema, versions 2
through 12, requires every `S17-EXT-001` transaction to bind exactly three
real predecessor blocker-receipt files -- `pre_marker_predecessor`,
`post_marker_predecessor`, and `action_revalidation_predecessor` -- authored
from those transactions' real evidence.

An exhaustive read-only search of this development environment (the full
repository git history including `--diff-filter=A` across every commit; the
rest of the home directory, `/tmp`, `/var/tmp`, `/opt`, `/srv`, `/root`; and
every locally present `cpu_prefetch`/`cpu-prefetch` checkout, build artifact,
and CI/hermetic-rehearsal output) found no real, owner-authorized D-120,
D-121, or D-123 blocker-receipt instance anywhere on this machine. Only (a)
empty schema and authoring-tool definitions with no populated instance, (b)
bundle-source verification checkouts with no evidence content, and (c)
output explicitly labeled `synthetic_test_only` by `run_stage17_hermetic_
handoff.py` exist. The existing three-blocker-receipt path therefore has no
real bytes to bind in this environment, and the current contract schema
provides no alternative: a first-ever `S17-EXT-001` transaction where no
real predecessor incident evidence is recoverable cannot currently be
expressed.

## Decision

Add a fourth, mutually exclusive evidentiary path to the
`stage17-read-only-preflight-supporting-contract` schema, effective at
schema version 13: a `no_predecessor_attestation` binding the owner may
supply instead of the three `*_predecessor` bindings, when and only when no
real predecessor blocker-receipt evidence exists to bind.

A `no_predecessor_attestation` record
(`cpu-prefetch-stage17-preflight-no-predecessor-attestation/1`) is created
exclusively by the owner and must bind:

- `schema_version`: the fixed constant
  `cpu-prefetch-stage17-preflight-no-predecessor-attestation/1`;
- `attestation_id`: a literal owner-chosen identifier;
- `actor`: the owner's real named identity, never a repository default or a
  synthetic value;
- `recorded_at_utc`: the real observed UTC instant of authoring, read from
  the system clock at authoring time, never caller-supplied;
- `search_evidence`: an `external_binding` (locator, size_bytes, sha256,
  schema_identity) to a real, byte-exact file recording the actual search
  performed for D-120/D-121/D-123 evidence -- its scope, the locations
  searched, and its result -- never a value invented independent of that
  file's real bytes;
- `search_scope`: the fixed constant array
  `["REPOSITORY_GIT_HISTORY", "LOCAL_FILESYSTEM_OUTSIDE_WORKING_TREE",
  "LOCAL_BUILD_AND_CI_ARTIFACT_STORAGE"]`, naming what a qualifying search
  must have covered;
- `declaration`: the fixed constant `NO_REAL_PREDECESSOR_EVIDENCE_FOUND`,
  asserting only that a real search was performed and found no admissible
  predecessor evidence -- it never asserts that no predecessor incident ever
  occurred, only that none is recoverable in this environment;
- `covers_incident_ids`: the fixed constant array
  `["D-120", "D-121", "D-123"]`;
- `retry_allowed`: `false`;
- `replacement_transaction_required`: `false` (there is no predecessor
  transaction to replace);
- `stage18_authority`: `false`.

The updated supporting-contract schema (v13) accepts, through an exclusive
`oneOf` (or equivalent exclusive construct), either all three
`*_predecessor` bindings or exactly one `no_predecessor_attestation`
binding -- never both, never neither. `author_ext001` gains a
`--no-predecessor-attestation` argument, mutually exclusive with the three
blocker-receipt flags at the argument-parsing level, before any file I/O.
Semantic verifiers that consume the supporting contract are updated so a v13
contract using either exclusive branch resolves the `S17-EXT-001`
predecessor-evidence input; a contract with both branches present, or
neither, is rejected before any other check runs.

This decision does not weaken any other input. It resolves only the
predecessor-evidence component of `S17-EXT-001`. The three-blocker-receipt
path, its schema, and its required-ness are unchanged for any environment
where real predecessor evidence exists. No stand access, transport,
credential use, calibration, pilot, measurement, or Stage 18 authority is
created, granted, or implied by this ADR or by its implementation.

## Effects

A first-ever `S17-EXT-001` transaction becomes expressible in an
environment with a real, searched, and negative predecessor-evidence result,
without inventing D-120/D-121/D-123 bytes that do not exist. The scientific
design, the fixed six-observation read-only action plan, and every later
gate (`S17-EXT-002` through `S17-EXT-010`, Q15-R, Q15-W, Q16a/b/c, and
Phase 18 access) are unchanged and remain independently authorized.

## Verification and supersession

Acceptance requires: a positive test that a valid attestation resolves the
predecessor-evidence input; negative tests that a missing, empty, or
content-mismatched `search_evidence` binding fails; a negative test that
supplying both an attestation and any blocker receipt fails; a negative test
that supplying neither fails; and a negative test, using an explicitly
`synthetic_test_only`-labeled fixture, that an attestation is rejected when
real blocker-receipt evidence is actually present for the fixture's
namespace. All prior Stage 17 suites, sanitizers, and a clean verified
candidate bundle must continue to pass unchanged.

This ADR remains `PROPOSED` until the owner reviews and separately accepts
it. Acceptance alone grants no authority -- a real `no_predecessor_
attestation` record, authored by the owner from a real search-evidence
file, is still required before `author-ext001` can run for the first time
in any environment lacking real D-120/D-121/D-123 evidence.
