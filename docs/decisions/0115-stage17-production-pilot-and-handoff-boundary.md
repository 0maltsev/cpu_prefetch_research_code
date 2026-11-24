# ADR-0115: Close the Stage 17 production pilot and handoff boundary

- Status: Accepted for repository implementation; no stand or execution authority
- Decision ID: D-115
- Classification: implementation, release-integrity, platform-control, and governance boundary
- Date: 2026-08-28
- Owner: repository and Stage 17 implementation owner
- Gate: real Stage 17 stand handoff
- Supersedes: policy-v10 production-completeness claims only; it preserves ADR-0114 and all scientific predecessors

## Context

Policy v10 established independent controller trust and a compiled six-action
surface, but its local closure was not an executable stand workflow.  Its
synthetic integration could select internally consistent worker hashes, Q15-W
did not retain the Q15-R process/mapping transaction, calibration and pilot
requests did not prove their complete registered matrices, and Stage 17 exit
could be assembled from structurally valid but unrelated records.  The v10
policy therefore remains readable but is
`REJECTED_INCOMPLETE_PRODUCTION_BOUNDARY`.

## Options considered

1. Treat schema-valid manifests and successful process exit as sufficient.
2. Add more owner-provided booleans to the existing records.
3. Bind one clean release end to end, execute only the compiled fixed-action
   surface, validate action-specific bytes and lineage, make Q15 mutation a
   supervised read/apply/probe/restore transaction, and provide one canonical
   author/admit/journal handoff.

Option 3 is selected.  The first two options are self-attesting and cannot
establish either execution semantics or custody.

## Decision

Policy v11 is the current Stage 17 semantic-admission policy.  It binds the
complete loaded Python/C++/schema closure, the v3 action registry, and the full
bundle verifier.  `S17-EXT-002` derives runtime identity from a fully verified
clean bundle: `SHA256SUMS`, SBOM, inventory, manifest, source revision, worker
bytes, and the worker's closed runtime-identity response must agree.  The
caller cannot select production versus synthetic classification.  EXT003
accepts those exact bytes.  EXT006 later re-verifies the archive and sidecar
and requires byte equality with that accepted runtime.

Q15-R and Q15-W are one phase-spanning supervised transaction.  The worker
retains its private probe mapping; Q15-W binds the exact Q15-R attempt/result,
re-reads the complete live MSR prestate immediately before mutation, executes
both registered probes, restores and reads back.  The controller independently
restores after any post-marker failure.  A durable controller quarantine gate
is created only if that real restore/readback fails.  A claim or request
boolean cannot establish probe, restoration, quiescence, or quarantine.

Q16a/Q16b/Q16c and the pilot accept only complete frozen matrices.  Hardware
states are whole plots with live apply/readback and final restoration.  The
pilot is exactly the registered 5 x 2 x 2 x 3 x 3 product (180 cells), with the
prospectively frozen repetition count, run IDs, schedules, seeds, placements,
capacities, and packages driving execution.  Every run emits independently
owned producer/consumer raw streams, joined observations, envelopes, join
audit, phase integrity, checksums, and page/residency provenance.  Verification
streams raw bytes under a bound derived limit; it has no fixed 16 MiB evidence
cap.

The controller pins worker, request, schemas, and evidence-root inode identity
before its durable marker.  It applies the Stage 17A.7 subreaper/process-group
barrier and validates the closed action-to-role-to-schema registry only after
quiescence.  A zero exit without the exact typed result and output family is a
failure.  Cleanup and restoration evidence precede terminal completion.

One production CLI canonically authors unsigned requests/authorizations from
explicit owner facts, verifies externally supplied detached signatures, and
create-exclusively appends admitted resolutions and graph transitions.  It
does not sign, invent facts, or edit validated JSON.  Immutable repository
definitions and an external operational evidence root remain separate.

Stage 17 completion is derived only from admitted EXT010 plus the exact pilot
attempt/result/completion and sealed artifact manifest.  Phase 18 requires an
independent trust key whose admission is separately approved through the
already admitted owner trust, a new signed Phase 18 authorization, and the
registered chronology.  No Stage 17 record grants Phase 18 authority.

## Scientific effect

None.  No duration, repetition count, capacity, rate, distance, schedule,
seed, platform value, calibration result, or acceptance threshold is selected
here.  Those values enter only through their admitted frozen records.  The
synthetic dry run proves software mechanics and cannot support an empirical
claim.

## Compatibility and risks

The fixed production path requires Linux procfs, memfd sealing, directory FDs,
pid-namespace mapping, OpenSSH SSHSIG tools, the accepted Intel 06_55H MSR
mapping, and the repository dependency prefix.  Missing capability fails
closed.  Policy-v10 records do not satisfy v11.  Every predecessor remains
byte-readable and every prior marker blocks replay.

## Supersession rule

A successor must preserve protocol snapshots and prior evidence, narrow or
retain authority, bind all consumed bytes and runtime modules, preserve the
six-action surface and complete matrices, and demonstrate the same unmocked
compiled-dispatch dry run.  A scientific change requires a versioned protocol
amendment rather than an implementation ADR.
