# Authoritative Repository Instructions

## Mission and paper identity

This repository contains the research, publication, and implementation-handoff artifacts for:

> **Prefetching and Tail Latency in Lock-Free Inter-Core Queues: Effects of Access Pattern, Placement, and Offered Load**

The repository's current deliverable is an English-language pre-experiment protocol and an authoritative handoff to a separate implementation repository. It is implementation-ready only when the structural semantics below and the normative handoff artifacts agree. It is not execution-ready until every applicable platform-, pilot-, budget-, engineering-, and author-dependent item is frozen.

`EXPERIMENT_IMPLEMENTATION_SPEC.md` and `PROTOCOL_FREEZE_CHECKLIST.md` are normative. The paper is the publication-level description. Files under `handoff/` define versioning, data, schema, access, provenance, and readiness contracts. If a conflict is found, stop execution planning, record it, and resolve it through a protocol amendment before implementation or data access.

## Scientific scope

The study has three stages:

- **Stage A (mandatory confirmatory core):** a bounded SPSC ring and a bounded linked 1P1C FIFO including its regular SPSC node recycler. Five queue/software packages are crossed with two verified hardware-prefetch states: `R0` ring/off, `R1` ring/one-line lookahead, `R2` ring/latency-matched lookahead, `L0` linked/off, and `L1` linked/one-hop successor hint.
- **Stage B (optional exploratory extension):** tagged-pointer NBLFQ instantiated as MPSC, only if its representation and platform assumptions pass. It cannot replace a Stage A cell.
- **Stage C (optional robustness extensions):** mutable event preparation/ownership, burstiness, interference, alternative page/data placement, memory-order sensitivity, SMT, and overload. It cannot replace a Stage A cell.

The three research questions are:

- **RQ1:** How do verified hardware-prefetch configurations and feasible family-specific software-prefetch policies modify run-level p99.9 end-to-end latency across the two complete Stage A queue packages at common logical capacity and matched working-set residency class?
- **RQ2:** How do producer--consumer placement, working-set residency, and offered load modify prefetch effects and useful ring lookahead?
- **RQ3:** Can deterministic, precision-gated training and sealed held-out validation support a platform-conditioned selection rule for the six declared middle-load contexts?

Do not reintroduce a three-object mandatory core or RQ1--RQ6. Stage B contention and Stage C robustness remain explicitly exploratory.

## Repository boundary

Allowed repository artifacts are limited to:

- LaTeX and BibTeX publication sources and verified LaTeX build products;
- Markdown research, protocol, handoff, provenance, freeze, amendment, and status records;
- non-executable JSON schemas and data dictionaries;
- corpus PDFs and their provenance/checksum records.

Do not create or modify benchmark, analysis, plotting, hardware-control, build, CI, deployment, or executable configuration code. Prohibited formats include C, C++, Rust, Go, Python, shell, assembly, CMake, Make, Meson, Bazel, Docker, and equivalent executable or implementation-oriented source. Do not create implementation directories such as `src/`, `include/`, `benchmarks/`, or `scripts/`.

Do not run the experiment, generate synthetic measurements, fabricate results, choose platform-dependent values without evidence, write empirical Results or Discussion, or make a performance recommendation. A methodological Conclusion may describe the protocol and its blockers only.

## Normative Stage A invariants

- The primary estimand compares complete ring and linked-plus-recycler packages; pointer dependence is not isolated as the sole cause.
- Queue families share logical capacity and working-set residency class, not necessarily byte footprint.
- Logical arrivals are pre-generated open-loop deadlines. A queue-full return is a retained drop outcome, never an automatic run replacement; strict zero loss is a separate confirmatory-estimability gate.
- Stage A event records are one cache line, initialized before warm-up, immutable throughout warm-up and measurement, and contain an immutable index, one aligned 64-bit payload word, and inert padding.
- The consumer reads the index and payload and updates a consumer-private rolling checksum with one frozen deterministic fixed-structure integer-mixing operation. Mutable event lifecycle work belongs to Stage C.
- Primary Stage A data are ordered per-event producer and consumer observations joined after the run by run identity plus accepted ordinal. Every logical row stores `run_id`; producer and consumer rows retain the invocation, linearization, response, and action boundaries fixed by protocol `2.0.0-pre.1`. Histograms and quantiles are derived artifacts only.
- Logical row fields are normative and independent of physical storage. Production envelopes reference external immutable raw artifacts; inline JSON rows are validation/example only. Physical encoding, deterministic primitives, row sizes, and compression remain pre-pilot freeze decisions.
- Run lifecycle and join status permit partial failures without fabricated artifacts. A valid completed Stage A latency run requires both raw streams, a passed join audit, joined-derived rows, complete counts, provenance, and phase/integrity evidence.
- Warm-up uses a dedicated namespace. It is followed by drain, a deterministic logical reset that preserves mappings and cache history, a two-worker start barrier, and measurement `t0` from the frozen clock protocol.
- The primary run quantile is the non-interpolated inverse empirical CDF `X_(ceil(pN))`; events are never pooled across runs.
- Genuine full outcomes and genuine low effective-tail counts remain retained. They block dependent confirmation but are not measurement failures and do not authorize selective repetition.
- Correctness or measurement failure makes the original 180-cell block incomplete. Only a new complete role-compatible block may replace it, within the pre-frozen replacement budget.
- One common pool of complete confirmatory Stage A blocks is assigned immutable roles `H3_TRAIN`, `H3_VALIDATION`, or `H1H2_SUPPLEMENTAL`. H3 validation stays sealed through training selection; H1/H2 access all complete blocks only after selection is frozen, validation is unsealed and H3 is evaluated, and the H3 access record is sealed.
- H1 and H2 prospective precision are sized as separate seven- and twenty-contrast max-T families. H3 training sizing covers all 270 context/pair differences and validation sizing the complete 540-member ordered pre-selection family; sizing never uses selected identities or validation outcomes.
- Strict zero loss remains the confirmatory estimability rule. Before confirmation, a treatment-blind whole-matrix feasibility bound accounts for all planned runs and offered events; any load change is global and predeclared.

## Amendment rule

Any change to a queue algorithm, language memory-order mapping, record immutability, consumer action, waiting/polling or termination behavior, warm-up/reset/start semantics, arrival workload, timestamp boundary, factor, estimand, quantile, H1/H2 contrast, H3 selection/access chronology, exclusion or replacement rule, raw-data/join contract, or primary block structure requires a versioned protocol amendment.

Every amendment must:

1. identify the prior and new protocol versions;
2. state the reason and exact affected documents, schemas, estimands, contrast rows, and prior pilot records;
3. be approved before affected outcomes are opened;
4. recompute relevant hashes and precision/budget records;
5. preserve the prior record rather than overwrite it.

No blocked value may be resolved using confirmatory treatment outcomes. Validation outcomes may not be accessed before the sealing protocol permits it. Outcome-dependent deletion, reseeding, narrowing, extension, or repeat-until-success is prohibited.

## Evidence and publication integrity

- Inspect a source before citing it and keep claims within the inspected evidence.
- Do not invent citations, metadata, quotations, hardware behavior, implementation provenance, licenses, platform values, or results.
- Maintain `research/EVIDENCE_MATRIX.md`, `research/CLAIMS_LEDGER.md`, `research/OPEN_QUESTIONS.md`, and corpus provenance when claims or sources change.
- Preserve the 26 resolved bibliography entries unless evidence requires a documented correction.
- Keep authorship empty until repository evidence or an explicit submission decision supplies it.

## Required verification before handoff

- Build `paper/main.tex` with pdfLaTeX, BibTeX, pdfLaTeX, pdfLaTeX.
- Resolve errors, undefined citations/references, duplicate labels, harmful overfull boxes, broken metadata, and unreadable layout.
- Render and inspect every PDF page.
- Validate every JSON schema syntactically and verify corpus/artifact checksums.
- Search sources and extracted PDF text for stale protocol language.
- Confirm that all 26 bibliography entries resolve and that no experiment code, empirical result, or recommendation was created.
- Update `STATUS.md`, `REVISION_NOTES.md`, and `handoff/HANDOFF_READINESS_REPORT.md` with evidence-backed readiness and blockers.

The valid terminal state for this repository is `READY_FOR_IMPLEMENTATION` while remaining explicitly not ready for pilot or confirmatory execution wherever the freeze records say so.
