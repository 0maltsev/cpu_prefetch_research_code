# ADR-0118: external operational journal preflight runtime

- **Status:** accepted and implemented prospectively
- **Decision ID:** D-118 / STAGE17-EXTERNAL-JOURNAL-PREFLIGHT-RUNTIME-v1
- **Classification:** engineering, authority and persistence boundary
- **Owner:** repository, pilot, platform, custody, and audit owner
- **Gate:** before any new `S17-EXT-001` read-only preflight attempt
- **Deadline:** Stage 17 stand handoff
- **Supersedes:** the production-use claim of the policy-v9 executor/journal pairing only

## Context

The public Stage 17 operational CLI correctly separates immutable repository
definitions from an append-only external evidence root.  Its documented
handoff creates journal, resolution, and transition records below that
external root.  The policy-v9 preflight executor nevertheless delegated
lineage validation to the legacy repository-root loader.  A real admitted
`S17-EXT-001` transaction therefore stopped before its marker with
`journal path is outside repository root`.  No SSH transport was opened.

Moving operational records into the release tree would weaken the accepted
immutable-repository/external-evidence split.  Treating the external journal
as an unchecked path would be fail-open.  Modifying an already bound runtime
would invalidate predecessor policies and authorizations.

## Options considered

1. Copy the journal into the immutable bundle before execution.
2. Relax the legacy repository-relative loader in place.
3. Add a versioned successor that validates repository definitions under the
   verified release root and journal lineage under the owner-mode external
   evidence root through component-wise no-follow descriptor traversal.

## Decision

Select option 3.  The successor keeps the graph, catalog, resolution,
transition, journal, action-plan, observation, clock, transport, one-shot,
cleanup, and evidence schemas unchanged except where a new binding identity
is necessary.  It introduces a new preflight policy/envelope and binds the
actual successor executor, current external-root journal runtime, semantic
verifier, schemas, and this ADR by exact size and SHA-256.

The journal root is derived from the explicitly supplied journal directory;
the latest journal must be inside that root.  Every lineage, resolution, and
transition reference remains a safe relative path below the external root.
Repository definitions and repository evidence remain safe relative paths
below the independently verified release/admission root.  Symlinks,
`..`, absolute record references, forks, hash drift, runtime drift, and
cross-root substitution fail before the one-shot marker and transport.

The failed predecessor transaction remains immutable and is not retried.
A successor release requires a fresh authorization, resolution, transition,
and empty create-exclusive preflight evidence root.

## Scientific and compatibility effects

Scientific effect: none.  No schedule, queue, timestamp, record, placement,
load, package, calibration, pilot, or analysis semantics change.

Compatibility effect: policy-v9 records remain readable but cannot authorize
the successor executor.  The external operational journal contracts stay v1;
only their runtime root interpretation is corrected prospectively.  Stage 18
authority remains false.

## Evidence and supersession rule

Acceptance is based on the real pre-marker reproduction, an external-root
positive test that reloads the append-only records from disk, repository-root
and cross-root negative tests, predecessor preservation, clean-bundle
verification, and the existing Stage 17 runtime suites.

Any future change to journal-root selection, locator traversal, executor
identity, action readiness, retry behavior, or authority scope requires a new
versioned ADR and policy/runtime successor.  Scientific changes require a
separate protocol amendment.
