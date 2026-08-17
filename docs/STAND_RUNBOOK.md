# Stage A Stand Runbook

Status: **planning document only**. This runbook does not authorize calibration, pilot, or confirmatory execution and intentionally contains no machine commands or platform values. It becomes usable only after the corresponding `PLAN.md` gates and accepted records are complete.

## 1. Roles and separation

Before stand access, record named identities and approved combinations for:

- freeze authority;
- platform operator with least privilege for hardware controls;
- controller operator;
- data custodian;
- training analyst;
- validation authority/custodian;
- confirmatory analyst;
- replacement authority;
- independent access/audit reviewer.

The access design must keep validation outcomes technically inaccessible through training selection and prevent H1/H2 access until `H1H2_RELEASED`. A role label without an enforcement boundary is insufficient.

## 2. Authorization gates

### Before any pilot

Require all of the following as immutable, source-hashed evidence:

- accepted queue provenance/licenses/modes, atomic mapping, refinement/progress arguments;
- supported platform inventory with eligible near/far topology;
- clean-room build and exact build/dependency provenance;
- schema and semantic conformance suites;
- unit/property/queue/stress/sanitizer acceptance;
- atomic lock-freedom and generated-code acceptance for every package;
- fixed RNG, derivation, permutation, consumer mixing, checksum, schedule, physical row, compression/copy, and serialization records;
- proven raw-buffer and durable-storage capacity for the proposed pilot horizon;
- authorized affinity/NUMA and hardware-state control/readback procedures;
- clock, processor-relax, timestamp, and boundary acceptance procedures;
- synthetic end-to-end dry run that is explicitly not a performance experiment;
- pilot durations, repetitions, namespaces, treatment-blind acceptance plan, and stand-hours.

Any missing item stops pilot preparation.

### Before confirmatory Stage A

Additionally require frozen application/pilot/calibration outputs: `delta_star`; capacities/residency maps; service calibration and `mu_ref`; rates; matrix zero-loss estimator, inputs, `pi_matrix`, and global rule; `d2`; warm-up/horizon/recovery/effective-tail parameters; environmental limits; `B_boot`; all repetition counts; master/derived seeds; exact block roles/plans; stand budget; replacement cap/authority; technical sealing; and access/signature records.

Verify `Rtotal = max(max(R_H1,R_H2), Rtrain + Rval)` and `Nruns = 180*Rtotal` without inventing any operand. A blocked operand stops confirmation.

## 3. Stand admission

For each authorized session:

1. Verify protocol/import, implementation revision, build artifact, dependencies, and accepted ADR/freeze hashes.
2. Verify the machine identity matches the platform record, including CPU, stepping, microcode, topology, cache line, memory, kernel/OS, firmware/power, and SMT state.
3. Verify authorized storage locations, free capacity, custody/access controls, append-only behavior, clock source, and rollback/recovery readiness.
4. Verify role-specific namespaces and block plans have not been used, mutated, unsealed, or branched.
5. Record the session admission decision. On mismatch, create a pre-run/platform/protocol failure record and do not launch workers.

## 4. Whole-plot procedure

Follow the frozen counterbalanced hardware-state order in the block plan.

At each whole-plot boundary:

1. Platform operator applies only the authorized requested state.
2. Independently record requested state and configuration readback.
3. Run the frozen regular-access and pointer-behavior probes.
4. Record verified state as default, changed, failed, or unknown; never infer “all prefetch off.”
5. Apply the frozen cooldown/recovery and environmental acceptance checks.
6. If verification or environment fails, record failure and stop the affected launch; do not substitute another state or tune from outcomes.

Run the 90 cells within the whole plot only in the pre-generated order. Never reorder because a prior cell was slow, full, low-`N_eff`, inconvenient, or surprising.

## 5. Per-run preparation

Resolve the explicit run identity from protocol, platform, build, block/role, factor cell, and within-cell ordinal. Do not parse identity from paths.

Before worker launch:

- validate manifest/config/schedules structurally and semantically;
- verify arrival/event/node seed references and paired-treatment sharing;
- verify schedule count/order/horizon/checksum and disjoint namespace;
- allocate or confirm persistent arenas, then verify line alignment, footprints, mappings, producer-home shared data, and worker-local private buffers;
- verify linked address-pattern gates and paired checksums where applicable;
- verify pre-horizon record-content checksum and immutable event order;
- verify actual CPU affinity, cache relationship, NUMA residency, build, clock, requested/verified hardware state, and raw-buffer capacity;
- create a `PLANNED` lifecycle manifest without claiming artifacts that do not yet exist.

Any failure remains a pre-run failure with its evidence. Do not fabricate producer, consumer, join, or integrity artifacts.

## 6. Warm-up, reset, and start

1. Use the dedicated warm-up namespace and the same package, software/hardware policy, placement, persistent mappings, and consumer action as the measured run.
2. Execute the frozen warm-up duration; warm-up data never enter inference.
3. Stop new warm-up arrivals and drain all accepted warm-up events.
4. Stop both workers at the phase barrier.
5. Preserve every allocation, first-touch result, and mapping.
6. Restore ring empty slots/cursors or linked sentinel/recycler order exactly; reset event-order position, counters, sample indices, and occupancy; prove no warm-up event remains.
7. Do not remap, regenerate schedules/permutations, broadly retouch payloads, or clear cache/hardware-prefetch history.
8. Synchronize both workers at the start barrier and derive `t0` through the frozen clock protocol.
9. Seal a reset/start phase result. A failure becomes `WARMUP_FAILURE` or `RESET_FAILURE` and stops the run.

## 7. Measurement and drain

During the measured horizon, no operator or controller action may add allocation, blocking I/O, console output, dynamic parsing, compression, aggregation, analysis, state changes, or hot-line observation.

The producer handles the pre-generated half-open deadline stream in order and makes one enqueue attempt per logical arrival. The consumer polls with the fixed behavior, performs the immutable record action, and writes only its private observations. The producer and consumer never share a writable raw buffer.

After the final attempt, the producer release-publishes `arrivals_finished`. The consumer acquire-observes it and drains until empty. Accepted events scheduled within the horizon stay included when action completes in drain. A process interruption, buffer overflow, clock/platform mismatch, or corrupt output is a measurement failure; do not shorten, extend, or improvise recovery within the run.

## 8. Immediate post-run handling

1. Stop data-plane workers and seal every artifact actually produced.
2. Recheck actual CPUs, NUMA residency/migration, hardware state, clock, environment, address identities, final occupancy, node ownership, and record contents.
3. Record final rolling, pre/post content, ordered-index, and address-delta checksums with algorithm/version identities.
4. Reconcile counts and seal producer and consumer envelopes.
5. Attempt the accepted-ordinal join and always seal its audit.
6. Produce joined-derived rows only if the audit passes.
7. Complete lifecycle, join, validity, zero-loss, effective-tail, estimability, block completeness, failure, provenance, and artifact fields independently.
8. Recompute artifact SHA-256 and make the append-only custody transition.

Do not calculate a performance recommendation at the stand.

## 9. Outcome classification

Use these non-interchangeable dispositions:

| Observation | Run validity | Gate consequence | Collection consequence |
|---|---|---|---|
| Correctly reconciled `FULL` | May remain valid | Zero-loss fails; dependent confirmation blocks | Retain; no repeat/replacement |
| Genuine `N_eff < 200000` | Remains valid if otherwise valid | p99.9/effective-tail and dependent confirmation block | Retain; no extension/repeat/replacement |
| Extreme valid latency | Remains valid | Analyze under frozen protocol | Retain; no repeat |
| Correctness/count/clock/placement/sample/integrity failure | Invalid | Original block incomplete | Retain evidence; complete-block replacement only if separately authorized |
| Failed join | Invalid | No joined latency | Retain raw artifacts and failed audit; original block incomplete |

No unfavorable or inconvenient outcome authorizes deletion, reseeding, rate/capacity change, selective repeat, or cell substitution.

## 10. Complete-block replacement

When one required run is genuinely invalid:

1. Retain the original block plan, all its runs, and failure records.
2. Mark the original block incomplete; do not fill the failed cell.
3. Replacement authority verifies failure category, remaining `R_replacement_max`, role, stand-hours, and access state without using treatment favorability.
4. If authorized, create a new complete 180-cell block with new ID/ordinal, same immutable role, new role-compatible seed subspace, and new whole-plot/cell randomization.
5. Cross-link authorization, original, failure, replacement, and budget records.
6. If the cap is reached or authority denies replacement, stop collection and leave the affected study unresolved.

## 11. H3 and H1/H2 access

After collection, custody must enforce the imported access state machine. Training analysts receive only `H3_TRAIN` artifacts. Selection freezes exactly six context choices and source hashes. Validation unsealing requires the authorized predecessor record. The confirmatory analyst evaluates the fixed paired validation family, seals H3 evaluation/access records, and only then may the custodian authorize `H1H2_RELEASED` for all complete common-pool blocks.

Any premature access, summary, log exposure, or analysis is an `ACCESS_LEAKAGE` failure. Stop further release and invoke an independent audit; do not attempt an informal cleanup.

## 12. Session closeout and emergency stop

At each session end, verify append-only storage, hashes, access logs, unused namespace custody, environmental record, failure inventory, and next authorized block identity. Record planned versus completed runs without interpreting effects.

Immediately stop on protocol contradiction, version/hash mismatch, unauthorized access/privilege, platform/build mismatch, failed hardware/clock/NUMA verification, unexplained corruption, storage exhaustion, replacement-cap exhaustion, or loss of custody. Preserve existing evidence and create the appropriate failure record. Resumption requires the responsible authority and all affected gates to be satisfied; it never occurs merely because the stand becomes available again.
