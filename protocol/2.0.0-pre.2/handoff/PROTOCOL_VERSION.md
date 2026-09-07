# Protocol Version and Artifact Identity

## Current version

- Version: **`2.0.0-pre.2`**
- Status: D-031 simultaneous-blocker representation amendment
- Date: 2026-08-21
- Repository readiness target: `READY_FOR_IMPLEMENTATION`
- Execution status: not pilot-ready and not confirmatory-execution-ready
- Compatibility: new sealed artifact graphs consistently use
  `2.0.0-pre.2`. The closed `2.0.0-pre.1` run-manifest object cannot represent
  exhaustive simultaneous blockers; old instances remain immutable and
  readable only under their original version or through an explicit
  provenance-bearing derived conversion.

## Versioning rule

Versions follow semantic form `MAJOR.MINOR.PATCH-pre.N` until confirmatory execution is authorized.

- `MAJOR`: an estimand, queue algorithm, factor family, workload, timestamp boundary, H1/H2 registry, H3 decision rule, or primary data model changes incompatibly.
- `MINOR`: an additive protocol capability or schema field changes implementation obligations without redefining existing data.
- `PATCH`: clarification that does not alter observable semantics or frozen analysis.
- `pre.N`: pre-execution handoff revision.

## Version decision

The move from `1.0.0-pre.1` to `2.0.0-pre.1` is a **major prerelease
revision**. It adds mandatory producer/consumer invocation, linearization,
response, and derived-interval fields; changes the raw-stream envelope from
mandatory inline rows to logical schemas plus external immutable storage; and
changes lifecycle, join, schedule, block, and freeze obligations. Existing
`1.x` primary records cannot satisfy the new contracts without reconstruction,
so a patch or minor version would contradict the rule above. The registered
H1/H2 contrast definitions, scientific estimands, Stage A objects, factors,
and quantile remain unchanged.

The move from `2.0.0-pre.1` to `2.0.0-pre.2` is a prerelease schema
amendment at an incompatible closed run-manifest boundary. It adds an
exhaustive `confirmatory_blockers` array and `BLOCKED_MULTIPLE` summary so
simultaneous independent gate failures have deterministic, lossless
representation. It does not change any observation, gate applicability,
estimand, outcome handling, or replacement rule. All other schemas are
version-aligned so a sealed graph cannot mix protocol versions.

## Version lineage

| Version | Date | Disposition | Lineage record |
|---|---|---|---|
| `1.0.0-pre.1` | 2026-08-17 | superseded for future implementation; historical hashes preserved | initial structural implementation handoff |
| `2.0.0-pre.1` | 2026-08-17 | superseded for new final dispositions; immutable and readable under its original contract | `handoff/AMENDMENTS.md`, amendment `AMEND-2.0.0-pre.1-DATA-CONTRACT` |
| `2.0.0-pre.2` | 2026-08-21 | current | `handoff/AMENDMENTS.md`, amendment `AMEND-2.0.0-pre.2-D031-MULTI-BLOCKER` |

## Preserved `1.0.0-pre.1` authoritative hashes

| Artifact | SHA-256 |
|---|---|
| `paper/main.pdf` | `461f7dba9ad34254dd3e82aba7cd1ca36ac712b5a9fcb6f8af13441143983983` |
| `EXPERIMENT_IMPLEMENTATION_SPEC.md` | `6c1f2a959736a693599193ed2433b2d143ade7cd5aacb34e3061e202bf9ebea4` |
| `PROTOCOL_FREEZE_CHECKLIST.md` | `8cd9488787669d3f05b00588d67d3381889ed7f227c6692550bcb7b7173d1513` |
| `AGENTS.md` | `8866ea62e33c7b7f4eb80d1a9f40525b355e90a4e36254abf327b61e271f0f7a` |

## Preserved `2.0.0-pre.1` authoritative hashes

| Artifact | SHA-256 |
|---|---|
| `paper/main.pdf` | `f7dccf3db2a4809c8d703d294f1407f91322cbc918cb2083b689c1c755b8d60e` |
| `EXPERIMENT_IMPLEMENTATION_SPEC.md` | `3795f53cfd0b06d94c2fdafa90e71372fc4f0eccd09d084382668f74f2b715ca` |
| `PROTOCOL_FREEZE_CHECKLIST.md` | `6eaa7eda33771ffa721439ee0b3273cf7cb2dabe3c5d4f46da8dec283e672867` |
| `AGENTS.md` | `6e6aac3ead33a604d515d583c018d7a6e74e5b68892ff221d0d48abce86efb8b` |

## Current authoritative hashes

The final `2.0.0-pre.2` hashes are inserted only after document
synchronization and schema conformance. The unchanged paper PDF intentionally
retains its earlier content hash because this amendment changes only the
machine-readable disposition representation.

| Artifact | SHA-256 |
|---|---|
| `paper/main.pdf` | `f7dccf3db2a4809c8d703d294f1407f91322cbc918cb2083b689c1c755b8d60e` |
| `EXPERIMENT_IMPLEMENTATION_SPEC.md` | `8488f9d3870b620b0b4f15cb1f47c2eb7ab3ecb8b15fc09603047dc379a5912c` |
| `PROTOCOL_FREEZE_CHECKLIST.md` | `ea78396d55b5bbfd1d4653d6e6516b4b645997fb53a46f848e2608249fdf524a` |
| `AGENTS.md` | `94c2d0c4ef8cd2566b51b515ca505d372528c4b804c10984242c718704ccfccf` |

A changed current authoritative hash requires a documented same-version
reproducibility record with unchanged semantics or a new append-only
amendment/version.
