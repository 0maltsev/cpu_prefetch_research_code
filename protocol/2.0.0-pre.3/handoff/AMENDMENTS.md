# Protocol Amendments and Version Lineage

Records in this file are append-only. They identify protocol semantics, not experimental outcomes.

## AMEND-2.0.0-pre.1-DATA-CONTRACT

- Prior version: `1.0.0-pre.1`
- New version: `2.0.0-pre.1`
- Effective date: 2026-08-17
- Authority role: repository protocol owner; no personal identity is present in repository evidence
- Access state: pre-implementation; no pilot, confirmatory, training, or validation outcomes exist or were accessed
- Authorization basis: explicit final pre-implementation correction task and repository amendment rule
- Version class: `MAJOR` prerelease revision

### Reason

The `1.x` schemas could not represent all normative operation timestamps, forced production rows into an inline JSON array, required successful artifacts for early failures, weakly constrained schedule/replacement/sealing records, and sized H3 validation from a post-selection family. Repair changes existing primary-data and lifecycle obligations incompatibly. The scientific objects, RQ1--RQ3, exact H1/H2 registry, complete-block design, strict-zero-loss estimand, and H3 selection criterion remain unchanged.

### Affected artifacts

- normative: `EXPERIMENT_IMPLEMENTATION_SPEC.md`, `PROTOCOL_FREEZE_CHECKLIST.md`, `AGENTS.md`;
- publication: timing, methodology, model notation, abstract/introduction/conclusion as affected;
- handoff: README, protocol version, decisions, data dictionary, access protocol, readiness report, and all seven schemas;
- research/status: open questions, claims ledger, evidence matrix, revision report/notes, README, and status.

### Affected schemas

- incompatible: `raw-observation.schema.json`, `run-manifest.schema.json`, `schedule.schema.json`, `block-plan.schema.json`, `freeze-record.schema.json`;
- version-aligned but scientifically unchanged: `failure-record.schema.json`, `platform.schema.json`.

### Estimands and contrasts

- Primary end-to-end estimand: unchanged, but its additive interval boundaries are now defined by queue linearization events rather than cross-core operation responses.
- Full/drop and effective-tail estimability semantics: unchanged.
- H1 stable IDs: unchanged, seven-member family.
- H2 stable IDs: unchanged, twenty-member family.
- H1/H2 sizing: clarified as separate family calculations with `R12=max(R_H1,R_H2)`.
- H3 selected-minus-alternative decision rule: unchanged; prospective training/validation sizing becomes selection-independent through the 270/540 complete pre-selection sets.

### Prior records and hashes

No implementation, pilot, calibration, training, validation, or confirmatory records exist in this paper repository; none is invalidated or migrated. The preserved `1.0.0-pre.1` authoritative hashes are:

- PDF: `461f7dba9ad34254dd3e82aba7cd1ca36ac712b5a9fcb6f8af13441143983983`;
- specification: `6c1f2a959736a693599193ed2433b2d143ade7cd5aacb34e3061e202bf9ebea4`;
- checklist: `8cd9488787669d3f05b00588d67d3381889ed7f227c6692550bcb7b7173d1513`;
- instructions: `8866ea62e33c7b7f4eb80d1a9f40525b355e90a4e36254abf327b61e271f0f7a`.

### Required downstream action

Future implementation repositories must create `2.0.0-pre.1` instances, pass the Draft 2020-12 conformance suite and semantic-validator rules, and freeze all still-open physical/platform values. Silent `1.x` acceptance or field inference is prohibited.

## AMEND-2.0.0-pre.2-D031-MULTI-BLOCKER

- Prior version: `2.0.0-pre.1`
- New version: `2.0.0-pre.2`
- Effective date: 2026-08-21
- Authority role: protocol owner and statistical owner
- Access state: pre-implementation; no pilot, confirmatory, training, or
  validation outcomes exist or were accessed
- Authorization basis: Q10 accepted the complete D-031 decision bundle and Q11
  assigned version `2.0.0-pre.2`, preserved `2.0.0-pre.1`, and authorized this
  amendment/import
- Version class: prerelease schema amendment at an incompatible closed-object
  boundary

### Reason

Version `2.0.0-pre.1` requires independent validity, zero-loss,
effective-tail, completeness, and access gates but exposes only one singular
confirmatory-estimability reason. Several gates can fail simultaneously, and
the protocol defines neither a priority nor a lossless collection. Allowing an
arbitrary applicable singular reason would make canonical final manifests
writer-dependent; inventing a priority would hide scientifically material
gate facts.

### Normative change

Every `2.0.0-pre.2` run manifest contains a required, exhaustive
`confirmatory_blockers` array. Members are unique and sorted by ascending UTF-8
token bytes solely for canonical serialization. An empty array accompanies
`NOT_EVALUATED`, `ESTIMABLE`, or `NOT_APPLICABLE`. Exactly one failed gate uses
the matching legacy singular summary. Two or more use `BLOCKED_MULTIPLE` while
retaining every applicable cause. Final evaluation waits for authoritative
evidence for every applicable gate.

The five causes remain `BLOCKED_ZERO_LOSS`, `BLOCKED_EFFECTIVE_TAIL`,
`BLOCKED_INVALID_RUN`, `BLOCKED_INCOMPLETE_BLOCK`, and
`BLOCKED_ACCESS_LEAKAGE`. Their independent source fields and applicability do
not change.

### Affected artifacts

- normative: `EXPERIMENT_IMPLEMENTATION_SPEC.md` and
  `PROTOCOL_FREEZE_CHECKLIST.md`;
- handoff: data dictionary, implementation decisions, readiness report,
  protocol version, amendments, README, and all seven version-aligned schemas;
- schema semantic change: `run-manifest.schema.json` only;
- version alignment only: raw-observation, schedule, block-plan, failure,
  freeze, and platform schemas.

The paper PDF and Stage A observation model are unchanged.

### Estimands, outcomes, and replacement

All estimands, raw rows, timestamps, queues, factor levels, full/drop handling,
effective-tail threshold, access chronology, and complete-block replacement
rules are unchanged. A correctly reconciled `FULL` and genuine low `N_eff`
remain valid retained outcomes and never authorize repetition or replacement.
The blocker set is descriptive only.

### Compatibility

The `2.0.0-pre.1` snapshot and every artifact created under it remain immutable
and readable under their original version. Its closed run-manifest object
cannot represent the new final disposition. New sealed graphs use
`2.0.0-pre.2` consistently; mixed protocol versions fail closed. Any migration
emits a new derived disposition artifact naming immutable source IDs/hashes and
converter version, and never overwrites or reinterprets its source.

The protocol-version metadata change does not revise the accepted Stage 6 RNG,
permutation, or Stage 7 schedule algorithms. Their versioned derivation-domain
labels remain byte-for-byte frozen; implementations must distinguish those
suite labels from the containing document's `2.0.0-pre.2` metadata.

### Prior authoritative hashes

- PDF: `f7dccf3db2a4809c8d703d294f1407f91322cbc918cb2083b689c1c755b8d60e`;
- specification: `3795f53cfd0b06d94c2fdafa90e71372fc4f0eccd09d084382668f74f2b715ca`;
- checklist: `6eaa7eda33771ffa721439ee0b3273cf7cb2dabe3c5d4f46da8dec283e672867`;
- instructions: `6e6aac3ead33a604d515d583c018d7a6e74e5b68892ff221d0d48abce86efb8b`;
- data dictionary: `c0c29e44ebfa5d3a8628180e748a11ea6095c1167ef5301c6bedd9518b9fd9da`;
- run-manifest schema: `ef460636ac56bdf32aa2bcde1bbdca3f64c5dc80d7258707ec7e1e8e51a078f2`.

### Required downstream action

Implementation repositories must verify both immutable snapshots, treat
`2.0.0-pre.2` as current, support the new typed blocker set, reject mixed
graphs, implement exact reconciliation before derived intervals, and retain
all still-open platform/pilot/confirmatory gates.

## AMEND-2.0.0-pre.3-D116-PILOT-WARMUP-BOOTSTRAP

- Prior version: `2.0.0-pre.2`
- New version: `2.0.0-pre.3`
- Effective date: 2026-08-28
- Authority roles: protocol owner and statistical owner
- Access state: pre-pilot; no calibration, pilot, confirmatory, training, or
  validation outcome was accessed
- Authorization basis: explicit `Q17B2-PROT` acceptance of the complete D-116
  Option A decision bundle
- Version class: prerelease scientific protocol amendment

### Reason

Version `2.0.0-pre.2` requires warm-up
`max(5 seconds, 10*h_max/rho_min)` but defines `h_max` and `rho_min` only from
valid pilot observations. It supplies no prospective duration for the first
calibration or pilot run. Any implementation-selected default would silently
change warm-up semantics.

### Normative change

Before a valid warm-up freeze exists, calibration and pilot runs are marked
`PRE_FREEZE_BOOTSTRAP` and use exactly the already registered five-second
floor. They remain non-confirmatory and preserve all ordinary namespace,
treatment, drain, reset, mapping, and start-barrier rules.

The freeze computes the Section 10.4 correlation horizon independently for
each valid required pilot run, without concatenating runs. `h_max` is their
maximum. Each same run's accepted-event rate is the exact accepted count over
measurement-horizon duration, excluding drain; `rho_min` is their minimum. A
valid `FULL` participates with its actual accepted count and separately fails
zero loss. Missing/invalid required evidence, an incomplete matrix, no valid
horizon, or zero accepted count blocks the freeze. The later duration is
rounded upward to the accepted schedule integer tick and cannot be revised
from confirmatory outcomes.

### Affected artifacts and schemas

- normative: `EXPERIMENT_IMPLEMENTATION_SPEC.md`,
  `PROTOCOL_FREEZE_CHECKLIST.md`, and `PAPER_AGENTS.md`;
- handoff: protocol version, amendments, README, data dictionary,
  implementation decisions, readiness report, and import manifest;
- semantic schema changes: `run-manifest.schema.json` adds explicit warm-up
  regime/duration/freeze identity; `freeze-record.schema.json` adds the typed
  `WARMUP_FREEZE` record;
- version alignment only: raw observation, schedule, block plan, failure, and
  platform schemas.

The unchanged PDF remains paired with this append-only machine-readable
amendment; the amendment governs the corrected pre-execution handoff.

### Estimands, contrasts, outcomes, and prior records

Queue algorithms, factors, workloads, timestamps, raw rows, estimands,
quantiles, H1/H2/H3 contrast families, FULL and low-effective-tail handling,
replacement rules, and access chronology do not change. The repository has no
prior calibration, pilot, or confirmatory records. If external pre.2 pilot
records are later discovered, they remain pre.2 and cannot satisfy a pre.3
freeze without an explicit provenance-bearing compatibility decision.

### Compatibility

The `2.0.0-pre.1` and `2.0.0-pre.2` snapshots remain immutable and readable
under their original versions. New graphs use `2.0.0-pre.3` consistently;
mixed graphs fail closed. A pre.2 run cannot acquire the new warm-up fields by
in-place editing.

### Required downstream action

Implementations must verify all three immutable snapshots, enforce the exact
five-second bootstrap only for marked calibration/pilot runs, validate the
complete source lineage and exact extrema/arithmetic of every warm-up freeze,
and block calibration, pilot, and confirmatory action when the applicable
regime or freeze evidence is missing.
