# ADR-0229: Independent Q16b/Q16c retained capture validation

- Status: ACCEPTED — engineering implementation within D035/D036/D210/D211/D219/D226
- Date: 2026-11-03
- Scope: one authenticated retained calibration capture; no family or release seal
- Execution authority: none

## Contract

`tools/stage17_formal_service_capture_validation_v1.py` exposes
`validate_capture(root, control, final, capture, resources, monitoring, hardware_control)`.
Its caller authenticates the original control, returned native result, prospective
inputs, qualified hardware prestate and source provenance. The original capture
schema selects Q16b or Q16c. Success returns
`cpu-prefetch-stage17-formal-service-capture-validation/1` with explicit action,
method, source component versions, both phase summaries and raw artifact hashes.
Invalid or unsupported evidence raises `ValidationError`; no partial successful
report is generated and retained files are never changed.

Reuse D220's exact common observation projection, arena replay and final file
identity checks. The projection contains actual phase origins and owner final
clock observations, after original pre-publication/final session equality is
checked. It does not manufacture preparation, reset, stop or cleanup evidence.
All mandatory mapping, first-touch, placement, page, TLS, thread identity,
MSR bytes, environmental observations, counter limits and final cleanup checks
remain applicable. Missing evidence is invalid, including for a zero count.

The single-capture declarations use D228's existing package/schedule checks and
the exact native input schemas. Source schedule hash syntax is not source
admission: schedule generation, seed derivation, release qualification and the
original authenticated provenance remain outer responsibilities. The validator
recomputes neither prospective native object layout nor family coverage.

## Primary reconciliation

Open original primary streams with the existing no-symlink descriptor walker,
regular-file/size checks and streaming SHA-256 reader. Decode their existing
LP-run-ID, zero padding and unsigned little-endian records one row at a time.
Join accepted producer ordinals to consumer ordinals and record identity;
repeating arena indices are validation fields, never global event identities.
Replay the measurement-seeded persistent arena, validate record order/content,
and recompute the consumer checksum across all accepted events through drain.
Check every source clock pair, local and cross-row order, publication-before-
observation, phase origin and finite drain bounds, including excluded rows.
FULL retains its producer record and has no invented consumer or accepted ordinal.

Both phase snapshots must be complete, unoverflowed and within prospective
capacities. Raw counts must match native prefix counts and actual lifecycle
counts. Current producer observations must match the last raw row; the terminal
consumer result must be the existing complete EMPTY result without invented
item data. Its `last_append` is null: the native consumer resets that optional
before each poll, and the terminal EMPTY poll appends no primary row. It is not
the status of the last retained item. The legacy empty capture has no retained
clock sample; this validator
does not fabricate one or claim independent per-empty timestamp reconstruction.
Its drain checks combine the actual successful lifecycle, final clock/checkpoint,
terminal EMPTY status, count equations and complete independent P/C join.

Linked packages additionally stream-check the full node-order artifact against
the registered deterministic permutation of `capacity + 1` nodes. Ring packages
retain the declared empty node-order artifact. All roles/phases must use distinct
paths and physical files. Original file identity stamps are rechecked after
validation; no joined-derived file is fabricated or required by this calibration
contract. The immutable completed-valid-Stage-A artifact requirements are unchanged.

## Distinct Q16b and Q16c rules

Q16b requires the actual fixed-duration producer stop and normal terminal drain.
Recompute D211's numerator using every consumer action completion `f_i` and the
actual phase origin `t0`, exact prospective duration `T`, and integer clock domain:
`t0 <= f_i < t0 + T`. Retain full consumed count and outside-interval count
separately. Check the native cold counter against independently derived values.
A valid zero numerator is retained; it is not missing data or a retry trigger.
Warmup has no service-rate estimate. No dequeue/start-time substitution occurs.

Q16c validates both actual mapped source vectors against the authenticated
prospective vectors, their source metadata, byte counts and hashes. Check the
published schedule offsets/counts for alignment, non-overlap and
containment after the arena/order storage within the admitted records region.
These extent checks do not substitute for native object-layout verification.
Preserve source coordinates and prove each producer row's due time is
`actual_phase_origin + source_deadline - source_origin`. Every offered arrival
has exactly one producer attempt, including FULL and late handling. Measurement
exposure must be positive. The terminal offered/attempted and completion evidence
must agree. No D211 completion filtering is applied to this scheduled run.

The five-second warmup is the frozen schedule horizon, not an invented active
wall-time requirement. A completed scheduled producer can stop before its horizon;
`deadline_reached` is checked literally against its actual completion sample.
Mandatory during observations and ordinary drain/reset checks remain required.
No horizon hold, warmup minimum, favorable extension or gate waiver is introduced.

## Result and bounds

Two phase summaries distinguish raw reconciliation and execution-evidence
validation from descriptive zero-loss predicates. `measurement_zero_loss` and
`zero_loss_all_phases` remain separate. No run-level FULL is relabeled as a
correctness failure. `family_validity_established`, `execution_authority` and
`phase18_authority` are false. D035 lower bounds, D036 feasibility inference and
any global scale selection belong to later family evaluation.

Raw I/O holds a constant number of rows and file identities. Arena replay uses
the existing finite packed arrays; linked replay adds one packed uint64 array
bounded by half the arena replay limit plus one word. There is no Python-int
list of raw events, no joined-event JSON array and no second raw copy. Prospective
schedule arrays and bounded original metadata are already caller inputs.

Twelve targeted synthetic tests cover both modes and all five package declarations,
linked order corruption, independently reconciled FULL, exact-end exclusion,
zero interval throughput with drain rows, scheduled late handling and early
completion, wrong source/due mappings, missing arrivals, malformed original bytes,
excluded-drain corruption, incomplete prefixes, missing mandatory controls,
checksum/count/reset/cleanup failures, bounded reads and separate warmup versus
measurement zero-loss predicates. These are software tests, not stand evidence.

The existing C++ ring fixture additionally accepts `--mode service|scheduled`.
It invokes the real typed R0 and L1 capture backends and original publishers,
using caller-owned event/order/schedule backing, scripted clocks and explicitly
synthetic platform observations. It does not execute the native worker lifecycle
or qualify hardware. Six bridge tests pass its original unmodified control and
returned result through this validator, covering all four mode/package pairs,
both phase primary streams, linked node order and actual mapped source vectors.
They reject changed duration/due bindings, mapped extents, cleanup evidence,
terminal append state and corrupt excluded-drain bytes even with a revised hash.
The original six ring bridge tests remain passing. The bridge exposed and
corrected the consumer terminal-EMPTY append-status expectation without changing
native capture semantics or serialized publisher output.
