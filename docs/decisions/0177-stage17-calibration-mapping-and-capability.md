# ADR-0177: Stage A calibration mapping and capability integration

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-177
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: engineering prerequisites for EXT007, authorized by the continuation request
- Lifecycle gate: local implementation only; prospective release and exact action authority required

## Context

Q16a/b/c are the ring-distance, service-rate, and zero-loss calibrations for
the Stage A design. ADR-0173's implementation notes incorrectly call their
whole-plot controller Stage B/C. This correction grants no deferred Stage B/C
scope. ADR-0172/0173 already accept the two CPU mappings; ADR-0175 already
accepts the distinct T0-only software-prefetch form.

ADR-0176 exposed a remaining integration gap: the whole-plot controller used
the old CPU whitelist and manufactured 06_55H identity; output admission
hardcoded the old apply CPU set; action admission hardcoded the old mapping;
and worker preparation still required PRFCHW even for the accepted T0-only
form. Those independent checks must agree before live calibration.

## Decision

Extract whole-plot control behind the existing MSR backend seam and test it
with fake I/O. Bind its plan and both Linux adapters to the registered mapping
selected by the signed hardware-control record. Read actual CPUID before
each whole-plot entry and reject identity drift before MSR I/O. Preserve full
64-bit prestate, independent readback, and reverse restoration. Track even
ambiguous failed writes for restoration; failed restoration is sticky and
prevents re-entry. This adds no retry or arbitrary CPU/MSR/mask interface.

Worker preparation checks the requirements of the explicitly selected
software-prefetch mapping. Preserve the raw absent-PRFCHW observation for the
T0-only form. Keep the original form's PRFCHW requirement and reject unknown
mapping IDs. Select the mapping from actual CPU identity outside measurement.

Calibration hardware evidence uses the existing additive v2 schema and the
actual mapping ID. A v6 fixed-action plan and registry v8 bind those exact
outputs. Admission derives mapping/prestate from the verified Q15-R output
and checks Q15-W lineage; it does not infer silicon from the requested CPU
set. Readback must match the exact requested OR-mask and original prestate.
Operational semantics v12, controller v21, CLI v14, journal v48, and policy
v54 are prospective successors. All predecessor bytes remain untouched.

## Scientific boundary and release

The current Q16a draft supplies a sample-count ceiling but lacks D-037's
prospective run duration and minimum observations per series. Its warm-up
record is not implemented by the capture loop. Its memory-residency and
working-set preparation need verification. These are execution blockers;
this decision does not choose values, silently reinterpret sample-count
termination as fixed duration, or declare EXT007 resolved.

Changed worker/preparation/platform sources require fresh source bindings,
a clean verified release, and dependent qualification evidence under the
invalidation rules. Do not mutate an admitted root, reuse an old binary's
qualification, retry a stopped transaction, or run under a blocked state.
The new policy is not promoted by this engineering decision.

## Verification

Tests cover both mappings' exact CPUs, H0 with no writes, H1 reserved-bit
preservation, reverse restoration, destructor fallback, CPU drift and crossed
CPU sets before I/O, ambiguous writes, sticky restoration failure, and
T0-only preparation without invented PRFCHW capability. Production Python
output-admission tests must bind real fixture bytes and reject wrong mappings,
apply/restore corruption, CPU-order drift, and wrong Q15 lineage.
