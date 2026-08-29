# Data Dictionary

Protocol version: **`2.0.0-pre.3`**. This logical data model is incompatible with `1.x`. JSON instances use explicit fields and never infer identity from directory names. Strings are UTF-8; integers are exact base-10 values; record timestamps are nonnegative integer ticks relative to the run schedule origin; administrative timestamps are RFC 3339 UTC; artifact hashes are lowercase hexadecimal SHA-256.

## Stable enums

| Domain | Values |
|---|---|
| Stage | `CALIBRATION`, `PILOT`, `STAGE_A`, `STAGE_B`, `STAGE_C`, `DIAGNOSTIC` |
| Run mode | `LATENCY`, `SERVICE_RATE_CALIBRATION`, `D2_CALIBRATION`, `COUNTER_DIAGNOSTIC`, `EXPLORATORY` |
| Lifecycle | `PLANNED`, `PRE_RUN_FAILURE`, `WARMUP_FAILURE`, `RESET_FAILURE`, `MEASUREMENT_STARTED`, `MEASUREMENT_FAILURE`, `DRAIN_FAILURE`, `COMPLETED` |
| Join status | `NOT_ATTEMPTED`, `FAILED`, `PASSED` |
| Block role | `H3_TRAIN`, `H3_VALIDATION`, `H1H2_SUPPLEMENTAL`, `NOT_APPLICABLE` |
| Package | `R0`, `R1`, `R2`, `L0`, `L1`, `NBLFQ_MPSC`, `NOT_APPLICABLE` |
| Requested hardware state | `H0`, `H1`, `NOT_APPLICABLE` |
| Verified hardware state | `VERIFIED_DEFAULT`, `VERIFIED_CHANGED`, `VERIFICATION_FAILED`, `UNKNOWN`, `NOT_APPLICABLE` |
| Placement | `NEAR`, `FAR`, `STAGE_C_OTHER`, `NOT_APPLICABLE` |
| Working-set class | `L2_RESIDENT`, `LLC_RESIDENT`, `BEYOND_LLC`, `NOT_APPLICABLE` |
| Load level | `L025`, `L050`, `L075`, `CALIBRATION_READY`, `STAGE_C_OTHER`, `NOT_APPLICABLE` |
| Run validity | `NOT_EVALUATED`, `VALID`, `INVALID` |
| Count reconciliation | `NOT_EVALUATED`, `PASS`, `FAIL` |
| Zero-loss status | `NOT_EVALUATED`, `PASS`, `FAIL`, `NOT_APPLICABLE` |
| Effective-tail status | `NOT_EVALUATED`, `PASS`, `FAIL`, `NOT_APPLICABLE` |
| Estimability | `NOT_EVALUATED`, `ESTIMABLE`, `BLOCKED_ZERO_LOSS`, `BLOCKED_EFFECTIVE_TAIL`, `BLOCKED_INVALID_RUN`, `BLOCKED_INCOMPLETE_BLOCK`, `BLOCKED_ACCESS_LEAKAGE`, `BLOCKED_MULTIPLE`, `NOT_APPLICABLE` |
| Block completeness | `NOT_EVALUATED`, `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE` |
| Access state | `PLANNED`, `COLLECTED_SEALED`, `TRAINING_OPEN`, `SELECTION_FROZEN`, `VALIDATION_UNSEALED`, `H3_EVALUATED`, `H1H2_RELEASED`, `ARCHIVED` |
| Warm-up regime | `PRE_FREEZE_BOOTSTRAP`, `FROZEN_LATER_WARMUP` |

## Identity

- `platform_id`, `build_id`, `block_id`, `run_id`, `queue_provenance_id`, schedule IDs, raw artifact IDs, and freeze/access IDs are stored fields.
- `block_id` canonically includes protocol version, platform, stage, immutable role, and block ordinal. A replacement has a new ID and ordinal and links the original.
- `run_id` canonically includes protocol version, platform, build, block, factor cell, and within-cell ordinal.
- **Every producer, consumer, and joined logical row stores `run_id`.** The stream envelope also stores it; disagreement is a semantic validation failure.

## Exact logical timestamp model

| Field | Symbol | Meaning |
|---|---:|---|
| `scheduled_arrival` | `a_i` | pre-generated logical deadline |
| `producer_handle_begin` | `b_i` | first timestamp after deadline waiting, before handling the due arrival |
| `record_lookup_completion` | `c_i` | deterministic record-index/pointer lookup complete |
| `enqueue_invocation` | `u_i` | invocation of the one `try_enqueue` attempt |
| `enqueue_linearization` | `p_i` | successful queue publication/linearization; accepted rows only |
| `enqueue_attempt_completion` | `r_i^e` | response/completion of the one attempt for `ACCEPTED` or `FULL` |
| `dequeue_invocation` | `v_i` | invocation of a successful `try_dequeue` |
| `dequeue_linearization` | `q_i` | successful removal/linearization boundary |
| `dequeue_completion` | `r_i^d` | response/completion of that dequeue call |
| `consumer_action_completion` | `f_i` | index/payload loads and private checksum update complete |

For an accepted event the semantic validator enforces:

- producer lateness `b_i-a_i`;
- pointer-lookup interval `c_i-b_i`;
- enqueue service `r_i^e-u_i`;
- admission delay `p_i-a_i`;
- queue residence `q_i-p_i`;
- dequeue service `r_i^d-v_i`;
- post-dequeue delivery interval `f_i-q_i`;
- consumer action interval `f_i-r_i^d`;
- end-to-end latency `f_i-a_i = (p_i-a_i)+(q_i-p_i)+(f_i-q_i)`.

Only admission, residence, and post-dequeue delivery are additive. Lateness, lookup, enqueue service, dequeue service, and consumer action are nested/overlapping diagnostics and are not added again. An accepted producer row requires `accepted_ordinal` and `enqueue_linearization`. A `FULL` row forbids both, retains the other producer timestamps, and has no consumer or joined row.

## Logical streams and physical storage

The logical producer, consumer, and joined row definitions are normative. Physical encoding is not. A raw envelope records logical schema version, physical-format record ID, encoding, integer time unit, endianness, compression, row count, byte count, immutable ordering, storage location, integrity-artifact reference, and artifact SHA-256. Production uses `EXTERNAL_IMMUTABLE_ARTIFACT`; `INLINE_TEST_ONLY` exists solely for fixtures/examples. Compression is lossless and post-measurement.

For external storage, the implementation-side semantic validator decodes exactly `row_count` records with the frozen physical-format record, validates every decoded record against the applicable producer, consumer, or joined logical-row definition in `raw-observation.schema.json`, and proves that every row `run_id` equals the envelope `run_id`. Physical decoding success alone is not logical-row conformance.

A joined envelope names producer and consumer source artifact IDs and hashes. Each joined row names source row ordinals and carries every required timestamp and derived interval. A join audit is distinct from the successful joined stream.

## Phase and integrity evidence

The run manifest links one `PHASE_INTEGRITY_REPORT`. Machine-readable evidence records algorithm ID, algorithm version, and value for:

- final consumer rolling checksum;
- event-record content checksum before the horizon;
- event-record content checksum after the horizon;
- ordered-index checksum;
- address-delta checksum.

The pre/post content algorithms must match, and the values must be equal for an immutable valid run. Checksum algorithms, canonical serialization, and byte order remain pre-pilot freeze items; no default is implied.

## Schedule contract

Schedules record kind, arrival family, namespace/parent namespace, seed derivation, integer time unit, absolute/delta encoding, origin, horizon, half-open `[origin,origin+horizon)` inclusion, exact rational nominal rate, offered count, overflow rule, decoded checksum, immutable order, and storage artifact. Semantic validation proves nondecreasing decoded deadlines, exact count, horizon membership, completion independence, warm-up/confirmatory namespace separation, and intended matched-treatment schedule sharing.

## Lifecycle and artifact invariants

- Before a valid warm-up freeze exists, calibration and pilot manifests use
  `PRE_FREEZE_BOOTSTRAP` and exactly five seconds in the schedule integer time
  unit. After freeze, applicable later manifests use
  `FROZEN_LATER_WARMUP` and reference the immutable freeze record.
- A warm-up freeze consumes every prospectively required pilot run. It
  computes a correlation horizon per valid run without concatenation, uses the
  maximum horizon, computes exact accepted-count/measurement-horizon rates,
  uses their minimum, and rounds the resulting duration upward to the schedule
  tick. A valid `FULL` run participates with its accepted count and separately
  fails zero loss. Missing/invalid evidence, zero accepted count, or an
  incomplete matrix blocks the freeze.

- An early invalid run requires a failure record but no fabricated raw artifacts.
- A failed join requires a failed join audit and forbids a successful joined dataset.
- A valid completed Stage A latency run requires complete counts, producer raw, consumer raw, passed join audit, joined data, phase/integrity evidence, and provenance.
- Pilot and calibration manifests require their applicable schedule, seed, provenance, and integrity references.
- `VALID` is independent of zero-loss and effective-tail status. Correctly reconciled `full>0` implies zero-loss `FAIL`, not invalidity. Genuine `N_eff<200000` implies effective-tail `FAIL`, not invalidity. Neither condition authorizes replacement.
- Every run manifest has a required `confirmatory_blockers` array. Its members
  are the five existing `BLOCKED_*` cause tokens, are unique, and appear in
  ascending UTF-8 token-byte order solely for canonical serialization. An
  empty array accompanies `NOT_EVALUATED`, `ESTIMABLE`, or `NOT_APPLICABLE`.
  One blocker uses its matching legacy singular summary; two or more use
  `BLOCKED_MULTIPLE` and retain every applicable failed-gate token. Final
  evaluation is forbidden until every applicable gate has authoritative
  evidence. The blocker set is descriptive and never authorizes retry,
  extension, selective removal, or replacement.

## Block and access invariants

- Original block plans use explicit null replacement fields. Replacement plans use nonempty original/authentication IDs and lineage.
- JSON Schema fixes 180 array entries and basic uniqueness. The semantic validator proves the exact Cartesian product, complete unique ordinals, one `H0` and one `H1`, role-compatible seeds, new replacement identity/ordinal/subspace, and unchanged role.
- H3 selection uses exactly the six stable context keys in `freeze-record.schema.json`. Validation unsealing names the validation namespace plus the selection and validation artifact hashes; H3 evaluation additionally names the unseal-record hash. Cross-record chronology, referenced hashes, block roles, namespace membership, authority segregation, and budget availability remain semantic-validator obligations.

Every derived artifact names immutable source IDs and SHA-256 hashes. Raw producer/consumer streams are never superseded in place; corrected joins and derived records are append-only.
