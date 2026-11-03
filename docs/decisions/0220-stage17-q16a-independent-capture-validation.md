# ADR-0220: Independent formal Q16a per-capture validation

- Status: `ACCEPTED` — engineering implementation of D210–D212, D214 and D217
- Date: 2026-11-03
- Scope: one retained formal R0 capture; historical validators/codecs unchanged
- Execution authority: none

The formal publisher retains four primary and four acquire-demand streams, plus
actual session and environmental observations. A stream classifier alone cannot
establish that its demand advances correspond to the independently recorded
primary events or that the required warmup, reset and cleanup completed.

Introduce `tools/stage17_q16a_capture_validation_v1.py`. Its `validate_capture`
entry point receives an output root, the original formal control, the returned
final native result, the frozen capture/resources/monitoring records and the
qualified hardware-control prestate. Its caller must authenticate those input
objects and their original artifact bindings. This component supplies no signed
authority, family coverage, release qualification, prospective layout proof,
duration selection, or repetition policy.

Before inference, require the original formal control identity/method and the
actual successful native/service session. Bind both phase origins and exact
prospective horizons, five-second warmup, private and queue reset, observed
clock checkpoints, preparation, six control groups, TLS/thread identity,
placement/page observations, original environmental bytes and final cleanup.
Missing evidence fails closed. A failure does not alter retained files or
manufacture a partial successful report.

Reuse the existing independent common control/arena/environment checks through
a temporary observation view. The formal and discovery publishers use exactly
the same `observation_document` encoders. The view projects actual formal phase
origin samples and actual owner final ticks into the common helper's field
names. Original pre-publication/final session equality is checked before this
projection. The existing environmental decoder requires its discovery-control
version label; only this temporary, observation-only view uses that label,
after verifying the original formal version. The original document is not
modified or relabeled, and no discovery-study validator is called. No missing
stop, success, preparation or reset flag is invented by the projection.

All eight raw streams are checked using the existing LP-run-ID codecs and
descriptor-based finite reads, original sizes, hashes and file identities.
Producer attempts, including FULL, join to producer demand attempts; accepted
producer ordinals join to consumed ordinals and record identities; advancing
consumer demand rows join to those consumed rows. EMPTY polls remain retained
and never acquire an invented primary row. Check all clock pairs, ordering,
acquire-bracket nesting, stream capacities/counts and the last retained current
events. Replay the exact measurement-seeded persistent arena with the existing
packed replay helper, checking order/content hashes and the full drain checksum.
No joined artifact is fabricated or required by this eight-stream format.

Only after both phases' primary joins, demand associations and all eight hashes
pass, invoke the existing D212 decoder for phase-specific classification and
exact inverse-ECDF ranks. Warmup is raw validation only. Invalid or insufficient
measurement series return no quantile report. Excluded drain rows retain all
clock-validity requirements; zero length outside the eligible measurement
series alone does not invalidate them. FULL is valid reconciled data with a
separate per-phase `zero_loss=false` result, not a fabricated validity failure
or retry. The summary names `zero_loss_all_phases` and `measurement_zero_loss`
explicitly; warmup FULL does not silently redefine the measurement gate. These
are descriptive count predicates, not a new scientific exclusion rule.
Recheck original file identity stamps around classification as well as each
decoder's existing byte/hash checks.

Memory is bounded by a constant number of rows and eight file identities,
the existing finite packed arena replay, the caller's bounded control document,
and existing exact-tail heaps. There is no array of all raw observations or
per-event output JSON. The result has two phase summaries, exact counts/ranks
and explicit absence of family/execution/Stage-18 authority.

Verification uses small independent raw byte fixtures, existing synthetic
observation fixtures, missing-evidence and malformed clock/identity/join/hash
mutants, FULL reconciliation, excluded zero-length brackets and bounded read
checks. These are software checks, not native hardware or scientific results.

The separate `stage17_formal_ring_fixture_main.cpp` test tool adds a cross-language
serialization check. It drives the real R0 event backend, raw streams, immutable
arena and quiescent reconciliation/reset with a bounded scripted clock. It
constructs typed synthetic mapping, thread, TLS, MSR and page observations;
synthetic smaps bytes pass through the real finite file-snapshot implementation.
The actual formal publisher and final-result encoder emit eight raw artifacts
and their control/result documents. The Python bridge passes those documents
unchanged to the complete per-capture validator, without replacing missing
fields or mocking common checks. Failure mutants remove common observations,
corrupt final cleanup, or change a phase-window binding.

The test tool is not a production or qualification worker. Its scope sidecar
explicitly declares synthetic platform evidence, no hardware claim and no
execution authority. Its scripted single-thread driver does not execute or
qualify the native owner-thread lifecycle; the existing lifecycle tests retain
that responsibility. Input is capped at 64 KiB, arena capacity at 1,024 records,
each raw stream at 16 rows, and synthetic environmental storage at six 16-KiB
buffers with finite read ledgers. No experiment or live qualification is run.
