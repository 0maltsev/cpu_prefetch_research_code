# Access and Sealing Protocol

Protocol version: **`2.0.0-pre.2`**.

## Roles

- **Freeze authority:** approves protocol-dependent freeze records without treatment access.
- **Custodian:** stores namespaces and enforces access state; does not choose candidates.
- **Training analyst:** may access only unsealed `H3_TRAIN` artifacts during selection.
- **Validation authority:** verifies the immutable selection record and authorizes validation unsealing.
- **Confirmatory analyst:** evaluates validation and later H1/H2 only in the permitted sequence.
- **Replacement authority:** may authorize a new complete role-compatible block within `R_replacement_max`.

Names and identities remain blocked until the implementation repository assigns them. One person may hold multiple roles only if the freeze record explicitly permits it and the storage controls still enforce chronology.

## State machine

1. **PLANNED:** every Stage A block has a unique ID and immutable role; schedules and role-specific seed references exist; validation artifacts do not yet exist or are inaccessible.
2. **COLLECTED_SEALED:** raw artifacts are checksummed and stored. `H3_VALIDATION` content is sealed from all analysts. Metadata may reveal existence and integrity but not outcomes.
3. **TRAINING_OPEN:** the freeze authority confirms candidates, six stable contexts, tie break, `delta_star`, `B_boot`, bootstrap seed, separate `R_H1`/`R_H2`, all 270 prospective training-pair standard errors, the complete 540-comparison prospective validation family, `Rtrain`, `Rval`, schemas, and input hashes. Only `H3_TRAIN` is exposed; validation outcomes were not used for sizing.
4. **SELECTION_FROZEN:** an object keyed by exactly `NEAR_L2_L050`, `NEAR_LLC_L050`, `NEAR_BEYOND_LLC_L050`, `FAR_L2_L050`, `FAR_LLC_L050`, and `FAR_BEYOND_LLC_L050` stores one candidate per context. Training artifact IDs/hashes, rule version, timestamp, freeze authority, and selection checksum/signature are immutable. Any missing, invalid, zero-loss-failed, or effective-tail-inestimable required cell makes H3 unresolved and prevents substitution.
5. **VALIDATION_UNSEALED:** the validation custodian matches the selection-record ID/hash and records validation namespace/artifact ID/hash, a nonempty validation-block list, authorization, prior `SELECTION_FROZEN`, new `VALIDATION_UNSEALED`, and `outcome_access_prohibited=false`. Only then may validation outcomes be read.
6. **H3_EVALUATED:** the confirmatory analyst records the 54 selected-minus-alternative comparisons, one-sided simultaneous limits, and all source hashes, transitioning from `VALIDATION_UNSEALED` to `H3_EVALUATED`. No candidate removal, retraining, or validation resizing is allowed.
7. **H1H2_RELEASED:** the validation custodian links the sealed H3 evaluation/access records and authorizes the transition from `H3_EVALUATED`. Only then may all complete `H3_TRAIN`, `H3_VALIDATION`, and `H1H2_SUPPLEMENTAL` blocks enter H1/H2. Earlier H1/H2 outcome access is a leakage failure.
8. **ARCHIVED:** access, selection, validation, failure, replacement, and derived records are append-only and cross-hashed.

## Leakage prevention

- Namespace paths are not treated as identity; schema fields and hashes determine role.
- Validation raw contents, summaries, logs containing outcomes, and treatment-dependent diagnostics remain sealed together.
- A selection record must be reproducible from exactly the named training hashes.
- H1/H2 fitting, summary generation, or exploratory access to validation before `H1H2_RELEASED` invalidates confirmatory H3 and blocks H1/H2 until an independent audit determines whether recovery is possible.
- An amendment after `TRAINING_OPEN` cannot change candidates, contexts, tie break, exclusion, effective-tail, or validation rules using observed outcomes.

## Unsealing record

The unsealing record uses `freeze-record.schema.json` with `record_kind=VALIDATION_UNSEAL` and includes protocol version, record ID, validation-custodian authority, UTC timestamp, selection-record ID/hash, validation namespace ID, validation artifact ID/hash, nonempty affected-block list, authorization state, prior/new access state, and SHA-256 of the record's canonical serialization. A signature may supplement SHA-256; its algorithm and key provenance must be frozen before confirmation. The later `H3_EVALUATED` record additionally references the unseal record by ID and hash, so the required predecessor cannot be inferred only from a state label.

## Schema and semantic enforcement

Draft 2020-12 conditionals enforce the six selection keys, record-kind evidence, nonempty affected-block lists, authority roles, authorization status, and required transitions for selection, unsealing, H3 evaluation, H1/H2 release, replacement, and amendments. The implementation-side semantic validator must additionally resolve referenced records and hashes, prove chronological predecessor state, verify affected block roles and namespace membership, enforce authority assignments/segregation, confirm replacement-budget availability, and reject overwritten or branched lineage.
