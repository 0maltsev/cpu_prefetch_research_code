# ADR-0176: Bind calibration prestate validation to its named mapping

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-176
- Protocol: `2.0.0-pre.3`, unchanged
- Scope: engineering correction under the existing ADR-0172/0173 mappings
- Lifecycle gate: `IMPLEMENTED_LOCAL_NOT_RELEASED`; no execution authority

## Evidence

The real server's retained v5-12 journal validates with six resolutions and
two transitions. EXT007 through EXT010 remain missing. The read-only audit is
recorded in `docs/evidence/stage17/STAND-AUDIT-CPU-PREFETCH-V5-20261030-01/`.

A production-dispatch regression reproduced both sides of a validation defect:
Q16a rejected mapping `INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1` with its accepted
CPU set `{0,1,8}`, while accepting that mapping with the predecessor's
`{0,1,26}` set through the prestate gate. The latter is an identity mismatch,
even though later hardware gates can still stop execution.

## Decision

Resolve the prestate CPU order from the existing registered mapping ID for
Q16a/Q16b/Q16c and both pilot-plan readers. Reject unknown mappings and
unassigned CPU sets. Preserve the exact existing three-value parser and all
other admission gates. This selects no new CPU, mask, estimator, capacity,
duration, seed, scientific outcome, or protocol amendment.

The regression exercises the production Q16a/Q16b/Q16c dispatchers with
deliberately incomplete capture/run bodies. Both registered mappings must
advance to the body-validation gate only with their own CPU set. Crossed
sets and unknown IDs must fail at the plan gate. No hardware read/write or
artifact publication is needed to distinguish these outcomes.

## Limits and remaining work

This is a bounded validation correction, not closure of Stage 17. The
whole-plot controller still hardcodes the predecessor MSR access whitelist
and CPUID identity; calibration and pilot hardware evidence still emits
predecessor schema/mapping identities. Q16a also retains an unconditional
PRFCHW capability check despite ADR-0175's T0-only mapping. Those paths need
their own integrated correction, tests, schema/controller binding review,
and a fresh release before live calibration.

Changing this worker source invalidates the current release policy's source
binding. Historical policies, admission roots, artifacts, and one-shot
transactions are preserved. This work does not promote a policy, release a
candidate, issue an authorization, or execute an experiment.
