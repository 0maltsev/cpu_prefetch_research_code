# D-116 Stage 17 pilot warm-up protocol-amendment decision bundle

Status: **`ACCEPTED; IMPLEMENTED IN 2.0.0-pre.3`**

Current protocol: **`2.0.0-pre.3`**

Immutable predecessors: **`2.0.0-pre.1`** and **`2.0.0-pre.2`**

Execution authority: **`NONE`**

Repository state while unresolved: **`PREPARED`**, zero resolutions, zero
transitions, `action_ready=false`, `pilot_ready=false`,
`stand=NOT_ACCESSED`

## Resolved contradiction

The current protocol cannot determine the warm-up duration for the first
calibration or pilot measurement without using evidence that does not exist
until after that pilot:

- Specification section 5.4 requires every applicable warm-up to last at
  least `max(5 seconds, 10 * h_max / rho_min)`.
- In the same sentence, `h_max` and `rho_min` are defined from valid **pilot**
  observations.
- The freeze checklist marks the duration as a blocked output and says that
  the pilot must supply both inputs.
- Pilot schedules nevertheless need a finite warm-up horizon before any pilot
  run can start.

Using five seconds, a synthetic `tau_corr`, a guessed pilot rate, a prior-host
value, or the 180-second action limit as the first pilot warm-up would silently
change warm-up semantics. The amendment rule explicitly classifies a change
to warm-up/reset/start semantics as a versioned protocol change.

Fresh repository evidence at baseline
`12aa7c102daff53441e11d3bfdb5b291cedaf900` is:

- `EXPERIMENT_IMPLEMENTATION_SPEC.md` SHA-256
  `8488f9d3870b620b0b4f15cb1f47c2eb7ab3ecb8b15fc09603047dc379a5912c`;
- `PROTOCOL_FREEZE_CHECKLIST.md` SHA-256
  `ea78396d55b5bbfd1d4653d6e6516b4b645997fb53a46f848e2608249fdf524a`;
- `PAPER_AGENTS.md` SHA-256
  `94c2d0c4ef8cd2566b51b515ca505d372528c4b804c10984242c718704ccfccf`;
- `tools/check_protocol.py` passes for both immutable snapshots when run with
  the recorded offline Python dependency prefix.

No pilot, calibration, or confirmatory observation was accessed to identify
this contradiction.

## Decision record

| Field | Value |
|---|---|
| ID | `D-116` |
| Classification | Scientific protocol amendment: pre-pilot warm-up/bootstrap and correlation-freeze boundary |
| Options considered | A: a prospective pilot-bootstrap exception using the already registered five-second floor; B: an independently justified prospective upper-bound record supplied before pilot; C: remain blocked |
| Selected option | **Option A accepted.** The owner accepted the bundle as protocol and statistical owner; ADR-0116 and the complete hash-verified `2.0.0-pre.3` snapshot record the result. |
| Evidence | Protocol 2.0.0-pre.2 sections 5.4 and 10.4; freeze-checklist warm-up rows; immutable hashes above |
| Scientific effect | Option A changes only how non-confirmatory pre-freeze observations bootstrap the existing formula. It does not change queue behavior, factors, estimands, contrasts, FULL/low-tail rules, replacement, or Phase 18 access chronology. |
| Compatibility effect | Requires `2.0.0-pre.3`; pre.1 and pre.2 remain immutable and readable. Pre.2 pilot/calibration records, if any existed, could not be silently relabeled. The repository currently contains none. |
| Owner | Protocol owner and statistical owner; repository owner implements only after both roles accept |
| Deadline/gate | Before completing Stage 17B.2 production-pilot admission and before Q16 calibration or pilot authority |
| Supersession rule | A later amendment must retain every prior snapshot and evidence record, state how prior pilot records are treated, recompute hashes, and cannot use confirmatory outcomes |

## Options

### Option A — recommended: explicit pre-freeze bootstrap exception

Add the following prospective rules to `2.0.0-pre.3`:

1. Calibration and pilot runs performed before a valid warm-up freeze use
   exactly the already registered five-second floor. They retain the dedicated
   warm-up seed namespace, identical treatment, drain, logical reset, mapping
   preservation, and start-barrier rules. These observations are explicitly
   `PRE_FREEZE_BOOTSTRAP`; they are not confirmatory observations.
2. A correlation horizon is computed independently for every valid pilot run
   using the existing section 10.4 indicator and threshold rule. Runs are
   never concatenated. `h_max` is the maximum valid run-level horizon across
   the complete required pilot matrix and repetitions.
3. For each same eligible run, the accepted-event rate is the exact rational
   `accepted_count / measurement_horizon_duration`; drain duration is not in
   the denominator. `rho_min` is the minimum of those run-level rates. A valid
   reconciled `FULL` remains valid and participates with its actual accepted
   count; it separately fails zero loss and is never retried.
4. Missing or invalid required pilot evidence, no valid correlation horizon,
   zero accepted count, or an incomplete pilot matrix prevents the warm-up
   freeze. There is no imputation, favorable filtering, cell-specific
   duration, implicit retry, or extension.
5. The frozen later warm-up is
   `ceil_tick(max(5 seconds, 10 * h_max / rho_min))`, where `ceil_tick` rounds
   upward to the already accepted schedule integer time unit. The same frozen
   duration applies prospectively wherever the protocol requires it; it is
   never revised from confirmatory behavior.
6. The freeze record names every source run, raw/join/integrity artifact hash,
   correlation-estimator/version, exact rate numerator/denominator, selected
   extrema, rounding unit, resulting duration, validity decisions, protocol
   version, and implementation release.

This is the smallest amendment that breaks the cycle while retaining the
existing five-second floor and existing post-pilot formula. Its cost is an
explicitly acknowledged bootstrap assumption for non-confirmatory collection.

### Option B — prospective external conservative bounds

Require, before any calibration or pilot run, an independently justified and
hash-bound upper bound for `h_max` plus a lower bound for `rho_min`. The first
warm-up uses those bounds. The record must identify the external population,
method, contexts, uncertainty, applicability, and invalidation rules. No such
evidence currently exists, so choosing this option leaves Stage 17B.2 blocked
until it is supplied and accepted.

### Option C — remain blocked

Do not define a bootstrap rule. Production admission must continue to reject
all calibration and pilot plans because a required warm-up duration cannot be
derived prospectively.

## Completed amendment work

Acceptance of Option A authorized only repository-local amendment and
implementation work. It did not authorize stand access or execution.

The implementation owner completed these repository-local steps:

1. preserve `protocol/2.0.0-pre.1/` and `protocol/2.0.0-pre.2/` byte-for-byte;
2. create/import a complete `protocol/2.0.0-pre.3/` snapshot with version,
   amendment, specification, checklist, handoff documents, schemas, manifest,
   sizes, and SHA-256 values;
3. record an accepted ADR that binds D-116 and the new snapshot;
4. add typed bootstrap-source and warm-up-freeze records plus schema and
   semantic validation;
5. reject mixed versions and pre.2 records presented as pre.3;
6. add exact-arithmetic, rounding, missing/invalid/incomplete/FULL/zero-rate,
   namespace, provenance, and no-confirmatory-access tests;
7. only then continue the Stage 17B.2 durable pilot-session and public handoff
   implementation.

## Exact approval statement

The smallest sufficient owner response is:

> **Q17B2-PROT — accept D-116 Option A as protocol and statistical owner;
> authorize protocol version 2.0.0-pre.3, preserving pre.1 and pre.2
> unchanged; authorize repository-local snapshot creation/import,
> hash-verification, accepted ADR, typed-record/schema/validator work, and
> continuation of Stage 17B.2 only. This grants no stand, credential,
> authority, custody, calibration, pilot, measurement, confirmatory, network,
> MSR, or push permission.**

Any different response must explicitly select Option B or C and, for Option
B, supply the exact prospective evidence contract and real evidence identity.
