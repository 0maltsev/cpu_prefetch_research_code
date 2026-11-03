# ADR-0238: Q16c sealed original schedule sources

- Status: ACCEPTED engineering work; qualification required before activation
- Date: 2026-11-03
- Scope: Formal Q16c original-source transport only
- Execution authority: None

The existing inline request embeds all prospective deadline arrays in JSON.
Their size grows with every warmup and measurement schedule and may exceed the
fixed request bound. Increasing that bound or inventing placeholder arrays does
not establish a correct source transport or resource budget.

Add an explicit source-descriptor path while preserving inline-v1. The signed
plan retains schedule identity, count, original binary format, size and SHA256.
The parent verifies original accepted-generator provenance, copies the exact
original big-endian u64 artifact into a sealed memfd and binds its read-only
descriptor in the sealed execution context. Required descriptor membership is
exact; extra, missing, reused or changed source bindings fail admission.
The generator, rate, namespace, run identity and source interval are unchanged.

The cold native loader checks regular-file identity, read-only access and all
four immutable seals, exact count times eight bytes, original SHA256, source
window and nondecreasing deadlines. An empty schedule is an explicitly bound
empty original, not a missing input. Native loading uses pread without changing
the borrowed descriptor offset. It does no path lookup, regeneration, file
write, mapping or hardware access. Every read and allocation is bounded by the
prospective extent and deadline. The owned arrays must be complete before
entering any whole plot and remain alive through capture preparation.

All sealed source bytes, all owned arrays, loader transient copies, current
mapped schedule copies, metadata and descriptor counts require explicit
prospective accounting. The initial loader's vector ceiling includes both its
loaded vector and Result's transient success copy (16 bytes per offered item);
fixed block/hash state and other retained sources are additional allocations.
The request-size bound is unchanged. No compression credit applies to memory.

Tests use exact big-endian byte/hash goldens, high-bit u64 values, duplicates
permitted by the existing nondecreasing contract, empty schedules, wrong hashes,
size mismatches, unsealed/writable descriptors, interval/order failures, memory
and deadline rejection, and unchanged borrowed offsets. Relevant sanitizers
and integrated parent/native descriptor/provenance checks remain required.
The isolated loader alone does not activate this transport or authorize Q16c.

## Deferred activation/current release

Activation of sealed schedule transport is deferred to prioritize qualification
of the current complete Q16a/Q16b/Q16c inline implementation. This engineering
enhancement is not a prerequisite for Q16a. Deferral neither declares the current
release qualified nor authorizes collection: all existing release, prerequisite,
prospective-plan and execution gates still apply.

Each future Q16c plan must fit the unchanged 128 MiB request bound in
`src/runner/stage17_fixed_action.cpp` (`kMaximumRequestBytes`) and its declared
memory budgets. Its actual accepted-generator schedules are needed to establish
that fit; no event rate or eventual family size is assumed. The existing
`formal_family_action` parses and retains every capture's owned schedule arrays
before constructing `PilotWholePlotControl`. Inline operation does not waive
accounting for the complete retained arrays, JSON representation, current native
mapping and publication allocations. No request limit or scientific parameter is
reduced or relaxed by this deferral.

Earlier Q16a/Q16b results are not promised reusable if later sealed-transport
integration changes the producer build. The immutable
[`EXPERIMENT_IMPLEMENTATION_SPEC.md`, §5.3](../../protocol/2.0.0-pre.3/EXPERIMENT_IMPLEMENTATION_SPEC.md)
requires calibration to repeat after material build or other listed changes;
[D-038's lifecycle rule](../STAGE13_CALIBRATION_DECISION_BUNDLE.md#lifecycle-and-invalidation)
invalidates dependent freezes. [ADR-0231](0231-formal-admission-custody-successor.md)
also requires preceding calibration records from the same qualified release and
stand. Concretely, `stage17_phase_controller_v25.validate_prior_calibration`
(inherited by controller v26) compares exact `source_revision`, and
`stage17_calibration_export_v1._build` (used by export v2) requires the same
revision across all three plans. There is no automatic cross-build reuse
exception. A separately versioned offline analysis change does not itself
replace the original producer identity.
