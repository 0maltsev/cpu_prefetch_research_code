# D271: Explicit descriptive Q16c admission and original-source transport

- Status: ACCEPTED engineering implementation under owner-approved D270; activation pending verification
- Date: 2026-11-17
- Scientific authority: [D270 acceptance](../STAGE17_EXT007_Q16C_DESCRIPTIVE_V1_DECISION.md)
- Scope: cold Q16c family admission/source transport and descriptive reporting only

Use scheduled-plan/3 with exactly180 settings, one repetition,1-second
measurement,5-second warmup and initial scale0 (g=1). The family method is
MATRIX-FULL-DESCRIPTIVE-SCREEN-v1; capture collector identity remains the legacy
native format without inferential validity. Historical family/1 and/2 retain
their original methods and limits. No placeholders, projected arrays, new RNG,
rounding change, request-limit increase or measured-loop change is permitted.

Native capture/2 names SEALED_U64BE_ORIGINAL-v1 schedules with original artifact
identity/hash/count/window, without inline deadline arrays. An explicit parent
context binds every source to a unique read-only immutable descriptor. Native
loading verifies those bytes using D238 and owns every deadline before hardware
entry. The inline parser rejects sealed input without explicit context. Source
membership is exact across the complete family; extra/missing/duplicate/aliased
bindings reject admission, including aliases of worker control descriptors.

A prospective transport budget accounts separately for all sealed bytes, all
owned vectors, the largest Result transient copy plus8192-byte block, and at
least1MiB for source metadata/hash/allocator overhead. That entire bound is
added to existing native/controller/codec/broker memory; compression supplies
no memory credit. Descriptor count is exactly360, with actual FD-limit admission
required separately. Count products, totals and time horizons are checked.
Hardware and memory availability, accepted-generator provenance, original-source
hashes, clean release qualification, compatibility and signed owner admission
remain separate prerequisites. A software declaration grants no execution.

Keep the approved D233 storage and D270 single absolute24-hour window. Software
preparation does not start it. No actual source generation, qualification or
collection is authorized by this implementation record alone; before launch,
verify the finite envelope, give the measured ETA and satisfy every operational
gate. Completed Q16a/Q16b remain bound to their actual source identities and are
never automatically repeated. Preserve FULL as valid with a separate gate.

## Independent analysis

The separately versioned scheduled-source capture validator reconstructs the
original big-endian artifact hash from retained little-endian publication and
keeps compact packed values for the unchanged scheduled-arrival/owner join.
It validates the actual capture/2 input first. The packed values are decoded raw
observations, never synthetic inline substitutes, and their sum must fit the
existing native source ceiling. Existing file identity/hash and reconciliation
checks still run. The original validator remains strict for its old wire format.

A separate descriptive family composition requires all180 independently VALID
bound reports for DESCRIPTIVE_COMPLETE. All counts and original run/report
identities are retained; FULL leaves validity intact and fails the separate
observed zero-loss gate. Missing/invalid data remains incomplete. Report no
confidence claim, final scale selection or final matrix feasibility. Source
authentication and calibration compatibility remain external admission gates.
