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
