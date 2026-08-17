# Repository Status

Protocol snapshot: **`2.0.0-pre.1`**

Repository state: **`STAGE_2_DOCUMENTED_AWAITING_ACCEPTANCE`**

Readiness verdict: **`BLOCKED_BEFORE_IMPLEMENTATION`**

## Readiness by area

| Area | State | Evidence or blocker |
|---|---|---|
| Stage 1 import/traceability | `COMPLETE_REVERIFIED` | On 2026-08-17 all 18 artifacts again matched manifest size/SHA-256, the inventory had no missing/extra files, all four declared current hashes matched, and the manifest/seven schemas parsed as JSON. A fresh Draft 2020-12 meta-schema validator is still unavailable. |
| Stage 2 architecture boundaries | `ACCEPTED` | ADR-0001 through ADR-0006 freeze plane separation, logical/physical separation, semantics-preserving adapters, artifact compatibility, append-only partial failures, and two-pass validation. |
| Stage 2 implementation choices | `BLOCKED_PENDING_OWNER_ACCEPTANCE` | Q1-Q3 in `docs/DECISIONS_REQUIRED.md`: software foundation; queue/process/atomic/integrity/correctness plus project license; platform/custody boundary and owners. |
| Queue implementation | `NOT_STARTED_BLOCKED` | No queue source exists. Independent paper/protocol implementation is recommended, but implementation mode, repository license, memory mapping, and claim boundary are not accepted. Third-party queue code must not be downloaded or reused. |
| Measurement system | `NOT_STARTED_BLOCKED` | Toolchain/process/identity choices are not accepted; clock, raw format, deterministic suite, exact platform APIs, and target stand remain open. |
| Pre-pilot validation | `NOT_STARTED` | Requires implementation plus schema/semantic, queue/refinement, sanitizer, generated-code, storage, platform/timing, custody, and clean-room evidence. |
| Pilot | `PROHIBITED` | Stage 16 readiness and explicit pilot authority are absent; local one-NUMA-node development host is ineligible for near/far evidence. |
| Confirmatory execution | `PROHIBITED` | Pilot outputs and all later protocol-defined freeze records, budgets, authorities, and sealing proof are absent. |

## Stage 1 verification facts

- Immutable snapshot path and version remain `protocol/2.0.0-pre.1/` and `2.0.0-pre.1`.
- All four source-declared authoritative hashes match.
- Every one of the 18 imported artifacts matches `IMPORT_MANIFEST.json` by byte size and SHA-256; the exact inventory matches.
- `IMPORT_MANIFEST.json` and all seven imported schemas parse as JSON.
- No imported protocol byte was changed during Stage 2.
- The imported source tree had no Git metadata, so the import correctly records no invented source commit.

## Stage 2 accepted decisions

- ADR-0001: three planes and strict timed-path boundary.
- ADR-0002: stable logical model with replaceable physical codec/store.
- ADR-0003: static queue adapters that preserve package semantics.
- ADR-0004: explicit artifact/algorithm versioning and fail-closed compatibility.
- ADR-0005: append-only partial-failure and lineage model.
- ADR-0006: separate structural and semantic validation.

These decisions implement explicit protocol/user constraints and do not change treatments, data meaning, estimands, gates, or access chronology.

## Environment evidence, not study evidence

The 2026-08-17 development environment exposes Linux `7.0.11`, x86-64, GCC `16.1.1`, Clang `22.1.6`, CMake `4.3.3`, and Ninja `1.13.2`. The observed AMD Ryzen 5 5500U has one NUMA node. These facts support capability planning only; they do not approve versions, qualify a target stand, or support an empirical performance claim.

## Immediate gate

The exact next safe activity is **Stage/Phase 2 decision review and explicit acceptance of Q1-Q3**. Stage 3 build/CI and all production source remain blocked. Pre-pilot choices in the second table of `docs/DECISIONS_REQUIRED.md` may stay open until their listed gates; no pilot or confirmatory experiment is authorized.
