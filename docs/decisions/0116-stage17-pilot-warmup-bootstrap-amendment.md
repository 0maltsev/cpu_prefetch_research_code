# ADR-0116: Resolve the first-pilot warm-up bootstrap cycle

- Status: `ACCEPTED`
- Date: 2026-08-28
- Decision owners: protocol owner and statistical owner
- Protocol version: `2.0.0-pre.3`
- Decision ID: D-116
- Supersedes: the incomplete first-pilot warm-up boundary in
  `2.0.0-pre.2`; the snapshot itself remains immutable
- Lifecycle gate: before Q16 calibration and Stage 17 pilot admission

## Context and scientific constraints

Protocol `2.0.0-pre.2` required warm-up
`max(5 seconds, 10*h_max/rho_min)` while deriving both nonconstant inputs only
from valid pilot observations. It supplied no prospective duration for the
first calibration or pilot run. An implementation default would silently
alter warm-up/reset/start semantics, which the protocol amendment rule
reserves to a new version.

No calibration, pilot, confirmatory, training, or validation outcome was
accessed. D-116 recorded the contradiction and exact snapshot hashes before
the owner accepted Option A as both protocol and statistical owner through
`Q17B2-PROT`.

## Options considered

1. Use the existing five-second floor only for explicitly marked
   non-confirmatory pre-freeze calibration and pilot runs, then derive and
   freeze the later duration from complete valid pilot evidence.
2. Require externally justified prospective conservative bounds for the first
   run; no such evidence exists.
3. Remain blocked.

## Decision

Option 1 is accepted exactly as recorded in the D-116 bundle and imported
amendment `AMEND-2.0.0-pre.3-D116-PILOT-WARMUP-BOOTSTRAP`.

- Pre-freeze calibration/pilot runs use exactly five seconds and are marked
  `PRE_FREEZE_BOOTSTRAP`.
- Correlation horizons are computed per valid required pilot run without
  concatenation; `h_max` is their maximum.
- Each same run's rate is exact accepted count divided by measurement-horizon
  duration, excluding drain; `rho_min` is their minimum.
- Valid `FULL` participates with its accepted count and fails zero loss
  separately.
- Missing/invalid evidence, an incomplete matrix, no valid horizon, or zero
  accepted count blocks the freeze without imputation, retry, extension, or
  favorable filtering.
- The later duration is rounded upward to the accepted integer schedule tick
  and cannot be revised from confirmatory behavior.

The complete `2.0.0-pre.3` snapshot is imported under an 18-artifact
size/SHA-256 manifest. Versions pre.1 and pre.2 remain byte-identical.

## Evidence

- D-116 decision bundle and `Q17B2-PROT` acceptance;
- pre.2 specification sections 5.4 and 10.4 plus its freeze checklist;
- pre.3 specification, checklist, amendment, data dictionary, run-manifest and
  freeze-record schemas;
- import-manifest inventory/hash verification and Draft 2020-12 checks.

## Consequences and compatibility

This changes only the pre-freeze bootstrap boundary. Queue behavior, factors,
workload, timestamps, primary rows, estimands, quantiles, contrasts, FULL and
low-tail semantics, replacement, and Phase 18 chronology remain unchanged.

New graphs use pre.3 consistently. A pre.2 record cannot be relabeled or
edited into pre.3. Any discovered pre.2 pilot evidence remains under its
original contract until a separately accepted provenance-bearing conversion
or compatibility decision exists.

## Verification and acceptance tests

The implementation must test exact five-second tick conversion, regime/stage
compatibility, source completeness, independent run-level extrema, exact
rational rate arithmetic, upward rounding, valid FULL, zero accepted count,
invalid/missing/incomplete sources, mixed versions, immutable source hashes,
and prohibition on confirmatory-source access.

## Rollback or supersession

Do not roll back or rewrite any snapshot. A successor must preserve every
version and evidence record, identify affected prior pilot records, recompute
hashes, and remain prospective with respect to confirmatory outcomes.

## Protocol-amendment assessment

This ADR implements an already accepted scientific amendment; it is not an
engineering reinterpretation. Stand access, credentials, authority, custody,
calibration, pilot, measurement, confirmatory execution, network, MSR access,
push, and Phase 18 authority remain absent.
