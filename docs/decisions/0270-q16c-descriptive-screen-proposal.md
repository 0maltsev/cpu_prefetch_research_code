# D270 proposal: one complete descriptive Q16c matrix screen

- Status: PROPOSED; owner scientific decision required before implementation activation or collection
- Date: 2026-11-17
- Amendment: AMEND-2.0.0-pre.3-Q16C-DESCRIPTIVE-MATRIX-SCREEN-v1
- Scope: initial Stage17 Q16c descriptive evidence only; no confirmatory relaxation

## Why another scientific decision is required

D254's approved descriptive reduction is explicitly Q16b-only. Q16c still uses
D036's weighted run-cluster Hoeffding/Bonferroni probability method. The exact
accepted implementation gives p_U=1 for one, two or four all-zero equal-exposure
runs per cell. Even59 all-zero equal-exposure runs give p_U about0.288. With at
least one future offered event per each of180 cells, the resulting matrix lower
bound is0 in these best-case examples. Unequal weights only increase the margin.
These are synthetic method checks, not observed Q16c results. A short screen
cannot honestly be labelled a95%-confidence matrix-feasibility certification.

The actual Rtotal, Nruns and final N_sched are also not frozen. They must remain
explicitly NOT_EVALUATED, without invented exposure values. This proposal
separates useful initial observed data from that unresolved final probability
claim. It changes no completed Q16a/Q16b result or earlier source history.

## Proposed scientific design

1. Retain the full180 settings: five packages, H0/H1, NEAR/FAR, three working-set
   classes and all three offered-load levels. Collect exactly one independent
   capture per setting:180 total, with5-second scheduled warmup and1-second
   measurement. Keep accepted producer/consumer independence, one attempt per
   due arrival, all original observations, drains, monitoring and validity rules.
2. Use only initial global scale g=1, with exact rational base rates from the
   completed descriptive Q16b:1670571/4,1670571/2 and5011713/4 EVENTS_PER_SECOND.
   Use accepted D029 Poisson/Philox/Decimal80 schedules, fresh prospective
   identities and the original geometry/R2 distance. No rate, schedule or sample
   is chosen from new Q16c outcomes.
3. Name the family analysis method MATRIX-FULL-DESCRIPTIVE-SCREEN-v1. Retain all
   actual offered/accepted/FULL/drained counts and original run identities. Its
   outcome is descriptive matrix coverage and observed zero-loss gates only;
   genuine FULL or zero stays valid retained data. Missing/invalid required
   capture leaves coverage incomplete. No event-independence claim, D036
   confidence claim, future matrix-success guarantee or final scale selection
   is made. Preserve the individual native collector-format identity separately
   from this new family method, as D254 already does for Q16b.
4. Do not automatically collect a lower scale, top up, replace a cell, extend
   measurement, retry or recollect any completed Q16a/Q16b. If observed FULL
   occurs, report its separate failed zero-loss gate. Keep final D036 matrix
   feasibility NOT_EVALUATED until its own required design/exposures are frozen.
5. Permit a separately versioned Stage17-scoped descriptive handoff/freeze
   representation; do not relabel this as the legacy statistical method or
   legacy final feasibility freeze. Completed Stage17 data does not by itself
   grant Stage18 or confirmatory authority. Existing primary hypothesis and
   precision requirements and strict confirmatory zero loss remain unchanged.

## Necessary engineering and reuse

The current qualified worker embeds every schedule array in a128MiB JSON request.
At these rates, an example180-capture family with these horizons has about
902108340 expected deadline values. This expectation is a planning model, not
an actual generated count or verified request size. It implies about7.22GB of
uncompressed U64 source values and likely JSON well above the current bound.
Actual accepted-generator sources and exact accounting are required before arm.
Never raise the request bound or shrink the scientific horizon to force fit.

Where required, activate D238's already accepted sealed original-source transport,
with exact signed provenance and prospective FD/memory accounting. Complete
correctness/codegen/sanitizer checks before packaging a clean native release;
qualify that actual new executable once, near/far clocks and Q15-R/W, with the
same CPU isolation and unchanged hardware/clock acceptance limits. Stop on the
first qualification failure. No repeated qualification of the unchanged old
release is requested.

Extend the explicit cross-source compatibility exception only if independently
verified measured-code/library, native geometry, physical-platform and source
closure proofs pass for the reviewed cold source-transport changes. Keep the
old Q16a and two-source Q16b bound to their actual producers and qualifications;
never relabel them as collected by the new executable. If compatibility fails,
stop; this proposal authorizes no automatic recalibration or replacement.

Source generation and independent original-generator verification may be
parallelized or their previously authenticated exact results reused, but every
original generated byte, algorithm/rounding/identity rule and provenance gate
must remain identical. No arbitrary cached success flag is acceptable.

## Prospective time/storage boundary

Planning estimate: approximately20–24hours for one complete operational family
once source preparation is verified, including schedule generation/provenance,
required actual qualification, collection/archive, independent validation and
restoration. This is not a launch-ready measured prediction. The software-only
stand timing sampled4096 accepted-generator operations in0.651seconds and
observed16 physical CPUs; ideal parallel scaling is not guaranteed. Existing
Q16b collection took6.50hours/103captures and validation2.24hours/103captures;
those are context for budgeting, not measurements of Q16c.

Before any experimental launch, provide the owner an updated estimate based on
actual generated sources, measured preparation/archive/validation costs and
an exact finite envelope. Require that entire envelope to fit one new absolute
24-hour Q16c window, anchored to the first stand schedule-preparation or actual
qualification action, whichever is earlier. If it cannot fit, do not launch or
silently reduce the180 captures. Native software development/build correctness
work precedes that operational window. D260's completed window is never reset.

Keep D233's shared6TB archive quota,512GiB workspace,256GiB aggregate analysis
scratch and16GiB reserve; verify available capacity and actual extents before
launch. Raw evidence remains authoritative on the stand, with only final
reports/manifests on the PC. Retain failed stand evidence; remove verified PC
transfer duplicates. Stop on the first new Q15/Q16, validity, custody, time or
resource failure, reap owned workers and restore hardware/isolation. No automatic
retry or new window follows failure.

## Current boundary

This proposal is not approved and starts no experiment or qualification.
The [planning calculations and software timing](../evidence/stage17/Q16C-D270-PROPOSAL-20261117-01/planning.json)
contain no Q16c observations or execution authority. Until the owner decides,
continue only independent metadata handoff and necessary software preparation;
no dependent schedule collection, native qualification or Q16c launch.
