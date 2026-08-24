# ADR-0054: Preserve the Q15 buffer across Q15-R and Q15-W

- Status: `ACCEPTED_AND_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-054
- Classification: qualification orchestration and treatment-state verification
- Decision owners: protocol, platform, security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no accepted scientific decision; resolves the implementation gap
  between ADR-0051 and ADR-0052
- Lifecycle gate: before dynamic probe implementation and Q15-R

## Context

ADR-0052 requires the H0/H1 pair to retain the same binary, CPU, buffer,
layout, order, and counter configuration. ADR-0051 requires Q15-R evidence to
be sealed before Q15-W can be created. The split authorization schema places
H0 probes in Q15-R and H1 probes in Q15-W. Independent one-shot processes
cannot retain the same private anonymous mapping.

## Options considered

1. Treat deterministic byte equality as buffer equality.
2. Persist or remap a file/shared-memory buffer.
3. Keep one non-mutating session and its private anonymous mapping alive across
   the two authorizations.
4. Supersede the D-052 same-buffer requirement.

## Decision

Select option 3 exactly as frozen in the
[Q15-S3 bundle](../Q15_DYNAMIC_IMPLEMENTATION_DECISION_BUNDLE.md). The session
is a fail-closed state machine. It binds every identity and immutable input,
retains one private anonymous mapping through H0, Q15-R sealing, H1, and
restoration readback, verifies peer credentials and evidence hashes at every
handoff, and retains partial failures. It has no duration default and cannot
continue after expiry, disconnect, illegal transition, integrity change, or
evidence mismatch.

The session never reads or writes an MSR, validates or issues authority, opens
a network listener, accesses a scientific schedule/outcome, or modifies a
sealed Q15-R artifact.

## Evidence and effects

Evidence is the joint D-051/D-052 contract audit plus explicit owner acceptance
of Q15-S3 on 2026-08-24. Scientific effect is preservation of the literal
same-buffer qualification constraint. Session protocol, state sequence,
mapping identity, process/peer identities, artifact hashes, authorization
hashes, and restoration handoff are compatibility identity.

## Verification

Repository-local fake-backend tests pass every legal transition and the
registered illegal, peer/hash/value/expiry/disconnect, unchanged-buffer,
partial-evidence, and no-authority cases. No dynamic operation was executed.

## Supersession

A different phase boundary, buffer lifetime, or control protocol requires a
new ADR and full requalification. Replacing same-buffer with same-bytes needs
explicit scientific review and a superseding D-052 contract.
