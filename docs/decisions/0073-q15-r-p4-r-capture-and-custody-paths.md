# ADR-0073: Freeze Q15-R-P4-R capture and development-custody paths

- Status: `ACCEPTED_REPOSITORY_LOCAL_TEMPLATE_FREEZE_NO_STAND_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-073
- Accepted by: Q15-R-P4-F
- Decision owners: custody, audit, repository, and platform owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; supplies literal P4-R evidence paths under ADR-0068's domain separation
- Lifecycle gate: before creating any identity, stdout, stderr, sidecar,
  transfer-receipt, or review artifact

## Context and scientific constraints

The collector emits canonical evidence to stdout and diagnostics to stderr.
Terminal-only output, inferred filenames, or rewritten bytes cannot provide
immutable custody. Capture identity is evidence identity, not a scientific
event or outcome.

## Options considered

1. reserve the exact capture ID and development-repository paths selected
   below, preserve raw bytes, and fail if any destination exists;
2. use terminal output or copied text;
3. infer temporary filenames; or
4. remain blocked.

## Decision

Freeze capture ID `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01` and custody root
`/home/omaltsev/research/cpu_prefetch_research_code/docs/evidence/stage17/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01`.
Freeze the exact identity JSON and sidecar, collector stdout JSON, raw stderr
binary, collector sidecar, transfer receipt, and independent-review paths in
the accepted decision bundle. Every destination must be absent and is
append-only/create-exclusive. Raw source bytes may not be normalized or
rewritten.

This is a repository-local literal freeze only. It creates no directory or
artifact and does not authorize capture, transfer, collection, signature, or
stand access. It also does not satisfy future Stage A two-domain durability.

## Evidence

- Decision bundle SHA-256:
  `18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604`.
- Q15-R-P4-F acceptance SHA-256:
  `ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`.
- The accepted collector contract separates canonical stdout and bounded
  diagnostic stderr and requires partial-byte preservation.

## Consequences and compatibility

Scientific effect is none. Compatibility effect is exact: capture ID,
absolute paths, basenames, raw-byte policy, detached sidecar, receipt, and
review identity are immutable inputs to later authorizations.

## Verification and acceptance tests

Repository checks reject changed capture IDs, paths, custody domains,
filenames, overwrite semantics, or fabricated artifact hashes. Filesystem
absence and actual custody access remain future external evidence.

## Rollback or supersession

Any identity, path, domain, filename, or byte-handling change requires a new
unused capture identity and prospective acceptance. Existing and partial
evidence is retained; overwrite, rename, reuse, and automatic deletion are
forbidden.

## Protocol-amendment assessment

No protocol amendment is required. This ADR preserves evidence identity and
does not alter the imported logical model or scientific semantics.
