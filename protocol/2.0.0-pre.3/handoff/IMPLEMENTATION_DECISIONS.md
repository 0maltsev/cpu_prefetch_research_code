# Implementation Decisions

Protocol version: **`2.0.0-pre.3`**. A decision remains open unless repository evidence fixes it. Confirmatory treatment outcomes may not be used to settle any open item. Version `2.0.0-pre.3` adds an explicit five-second non-confirmatory pre-freeze bootstrap and typed warm-up freeze, while retaining the pre.2 exhaustive confirmatory-blocker representation. It does not change primary observations or freeze a physical raw format.

## Fixed protocol decisions

- Stage A contains two mandatory queue objects and packages `R0`, `R1`, `R2`, `L0`, `L1`.
- Complete queue packages, not pointer dependence alone, are the primary estimand.
- Records are immutable one-cache-line objects with an index, aligned 64-bit payload, and inert padding.
- The consumer reads index and payload, updates a private rolling checksum, then records completion.
- Open-loop one-attempt arrivals retain full/drop outcomes; strict zero loss separately gates confirmation.
- Ordered producer and consumer observations are primary; histograms are derived only.
- Every logical row stores `run_id`; the join key is run ID plus accepted ordinal; record index is a validation field.
- Producer rows retain handling, lookup, invocation, linearization when accepted, and attempt-completion boundaries; consumer rows retain invocation, linearization, response, and action completion. Only admission, residence, and post-dequeue delivery form the additive end-to-end partition.
- Logical row fields are normative; production envelopes reference external immutable artifacts. Inline JSON rows are test/example only.
- Run lifecycle and join state allow early/partial failures without fabricated raw artifacts; a valid completed Stage A run requires raw streams, passed join audit, joined data, provenance, counts, and integrity evidence.
- Pre-freeze calibration/pilot warm-up is exactly five seconds and explicitly
  marked; complete valid pilot evidence then freezes later warm-up through the
  exact run-level horizon/rate extrema and upward-tick rule. Warm-up is
  followed by drain, deterministic logical reset, start barrier, and
  controlled warm-start measurement.
- Producer and consumer waiting and termination follow the normative non-sleeping state machine.
- Genuine low effective count is retained and blocks dependent confirmation without repeat or extension.
- Simultaneous confirmatory blockers are retained exhaustively without a
  scientific priority. The singular summary is `BLOCKED_MULTIPLE` when two or
  more independent gates fail.
- Confirmatory blocks have immutable roles `H3_TRAIN`, `H3_VALIDATION`, or `H1H2_SUPPLEMENTAL` in one common Stage A namespace.
- Validation remains sealed through selection; H1/H2 access all complete blocks only after H3 unsealing/evaluation.
- Correctness/measurement failure permits only new complete-block replacement within a frozen budget.
- Original block plans use explicit null replacement fields; replacement plans require both IDs and lineage, while factorial completeness is a semantic validation obligation.
- Quantile, exact H1/H2 contrasts, separate H1/H2 max-T sizing, H3 candidate order, 270-pair training sizing, 540-comparison validation sizing, and selection rule are fixed by the normative documents.
- Strict zero loss remains the estimability rule; a prospective whole-matrix probability bound and treatment-blind global load rule must pass before confirmation.

## Required before implementation architecture is finalized

- For each queue: official-artifact status, source license, reuse/adapt/independent-implementation choice, and semantic adaptations.
- Intended language standard and feasible atomic width/alignment model.
- Artifact and data-storage architecture capable of append-only ordered observations, external immutable stream envelopes, phase/integrity evidence, and schema plus semantic validation.
- Identity/checksum library choices that support SHA-256 and the still-to-be-frozen data checksums.
- Sealing authority model and storage boundary that can make validation technically inaccessible.

## Required before pilot

- Target platform/topology and privileged-control authority.
- Compiler, library, full flags, link mode, language memory-order mappings, and lock-free atomic evidence.
- Exact consumer integer-mixing operation and generated-code acceptance signature.
- Processor-relax mapping; clock and linearization-boundary protocol; schedule time unit/encoding; physical raw format/version, row sizes, endianness, compression, copy policy, and storage budget.
- RNG/permutation algorithms and versions plus all pilot/calibration/warm-up/diagnostic namespaces.
- Queue provenance/license record, refinement argument, unit/property/stress/sanitizer acceptance.
- Hardware-prefetch requested/verified-state procedure and page-residency mechanism.
- Calibration estimators, durations, repetition counts, and pilot environment thresholds.

## Required before confirmatory execution

- `delta_star` and actionability record.
- Final capacities, loads, `mu_ref`, matrix-level zero-loss estimator/confidence/acceptance bound/global reduction rule, and context-specific `d2`.
- Measurement horizon, `tau_corr` inputs, recovery interval, moving-block diagnostic, and effective-tail evidence.
- `B_boot`, bootstrap RNG seed, `R_H1`, `R_H2`, `R12=max(R_H1,R_H2)`, 270-pair `Rtrain`, 540-family `Rval`, `Rtotal`, and role assignment.
- Validation sealing/unsealing and replacement authorities, selection-record signature method, `R_replacement_max`.
- Environmental acceptance limits, stand budget, final randomized block plan, and performance-counter availability.

## Submission-only decisions

- Author identities, affiliations, and anonymous-review status.
- Venue/template, page limit, bibliography style, accessibility, archival packaging, and final metadata.
