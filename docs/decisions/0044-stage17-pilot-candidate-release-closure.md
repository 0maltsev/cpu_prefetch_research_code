# ADR-0044: Stage 17 pilot-candidate release closure

- Status: `ACCEPTED`
- Date: 2026-08-22
- Decision owners: repository, build, controller, queue, timing, storage, and
  code-generation owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: the runner-profile/admission portion of ADR-0043; its CPU-pair
  and one-`PAUSE` selections remain unchanged
- Lifecycle gate: repository-local closure before stand qualification

## Context and scientific constraints

Q13 supplied strict admission and five controller-side branches but no affined
owner preparation, combined producer/consumer integration, complete generated-
code audit, qualification artifact producer, or pilot-candidate release. The
Stage 16 bundle is immutable and preflight-only. The physical retaining-
prefetch instruction remains a delegated platform decision and cannot be
invented during release integration.

Q14 authorizes repository-local implementation only. It supplies no watchdog,
capacity, distance, seed, hardware state, storage domain, authority, budget,
or execution permission.

## Options considered

1. Treat the component seams and Stage 16 bundle as the production release.
2. Add runtime package dispatch or a default platform-prefetch emitter.
3. Complete the static affined profile, require every unresolved input as
   immutable evidence, audit the combined operations, and issue a separately
   versioned fail-closed candidate bundle.
4. Postpone all local integration.

## Decision

Select option 3. The release profile is
`STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v2`. It preserves CPUs 0/1 and 0/26
and exactly one x86 `PAUSE`, prepares each private observation stream only on
its already-affined owner thread, verifies singleton affinity and actual CPU
before the start barrier, and retains static package specialization.

Admission replaces the generic `PILOT_EXECUTION_AUTHORIZATION` kind with
`PHASE_EXECUTION_AUTHORIZATION` and adds a distinct
`SOFTWARE_PREFETCH_MAPPING` kind. The latter is deliberately unresolved: R1,
R2, and L1 cannot arm until an accepted instruction/intent mapping and its
generated-code evidence exist. H0/H1 control remains the separate
`HARDWARE_PREFETCH_MAPPING` kind.

The new `STAGE17-PILOT-CANDIDATE-BUNDLE-v1` contains the runner and
qualification-only validator/tooling but explicitly sets pilot and
confirmatory authority false. Its creator rejects dirty source trees. Q14 does
not authorize creating a clean revision, transferring the bundle, or running
it on a stand.

## Evidence

- Q14 acceptance on 2026-08-22.
- The accepted D-044 through D-046 bundle.
- Stage 16 component-only audit and Q13 admission/static-dispatch evidence.
- ADR-0001, ADR-0012, ADR-0016, ADR-0028, ADR-0030 through ADR-0034, and
  ADR-0043.
- Imported owner-first-touch, static-package, retaining-prefetch, timing,
  one-attempt, polling, partial-failure, and no-timed-I/O rules.

No outcome or platform measurement selected this profile.

## Consequences and compatibility

The v1 admission and Stage 16 bundle remain readable under their identities,
but cannot be presented as the v2 pilot candidate. Runner profile, evidence
registry, combined-codegen report, binary, source, schema, and bundle hashes
are compatibility identity.

The physical software-prefetch mapping remains open rather than receiving a
host default. A candidate archive can be built only from a clean exact source
revision; an uncommitted working tree can verify the creator's refusal but
cannot produce an eligible release.

## Verification and acceptance tests

- Owner-thread preparation, affinity/readback/actual-CPU mismatch, partial
  preparation, and pre-barrier failure tests.
- Exact v2 evidence-registry, legacy-profile, missing software-prefetch, and
  phase-authorization negative tests.
- Combined producer/consumer operation audit for all five static package
  shapes using both accepted disassemblers and deliberate forbidden-work
  mutants; unresolved physical emitters remain non-eligible.
- Clean-source, manifest, internal/outer hash, forbidden-authority, and clean-
  extraction bundle checks.
- Full supported compiler, sanitizer, static, schema, and existing regression
  matrices before release.

## Rollback or supersession

Failure before the start barrier returns a pre-run failure and starts no
measurement. A material source, binary, emitter, pair, clock, queue, storage,
or policy change requires a new profile and complete affected requalification.
Existing artifacts remain immutable.

## Protocol-amendment assessment

This closes implementation seams while making the unresolved physical emitter
more explicit. It changes no protocol schedule, queue semantics, timestamp,
row, lifecycle, failure, or analysis rule. No protocol amendment is required.
