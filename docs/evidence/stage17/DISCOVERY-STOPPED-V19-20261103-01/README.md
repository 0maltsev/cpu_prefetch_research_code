# First v19 discovery attempt — stopped, 2026-11-03

The finite D178 authority was consumed once. The supervisor launched at
09:35:04 UTC and recorded exit 1 at 09:35:33 UTC. Capture 0 stopped during
warmup; no measurement phase completed, no study completion record exists,
and no diagnostic duration or formal-calibration result can be selected.
This record grants no further execution authority.

The original failure identifies `WORKER_NONZERO`. The retained control
reports consumer warmup trace-capacity exhaustion at 5,000,000 attempts;
the producer stopped on its peer's signal. The required during-warmup
observation was not completed before the workers stopped. The study fails
mandatory validity regardless of whether its retained raw prefix reconciles.

MSR restoration matched all three recorded CPU prestates. The process group
was gone and the leader reaped. The CPU partition was removed, with original
root cpuset/controller values verified at 09:35:33 UTC. No quarantine was
required. `originals/` preserves original failure, attempt, hardware,
supervisor, launch, restoration and log bytes. `stand-inventory.json` retains
the original stand-side inventory and original small-file encodings.

## Original-byte custody

`stopped-copy-verification.json` records matching original sizes and SHA-256
for all 12 output files, totaling **1,142,655,488 bytes**. These include the
27,519,778-byte control document, three warmup binary streams, three empty
measurement streams, and attempt/failure/log/hardware records.

- Stand: `/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19/discovery-output-1`
- PC: `/home/omaltsev/research/cpu_prefetch_research_code/build/stage17-discovery-v19-copy1/discovery-output-1`

Raw streams and the large control document remain at those locations; they
are not duplicated into Git. Neither copy is compressed. Independent raw
validation began only after the complete second-copy verification passed.
The local orchestration scripts are retained for reproducibility and call
the existing validator; they change no production source or validity gate.

## Independent validation of the failed prefix

`stopped-prefix-validation.json` records a passing reconciliation using the
existing `validate_phase` routine after custody verification. All 4,199,692
accepted producer events reconcile with 4,199,692 consumer events, including
one drained event; producer FULL count is zero. The consumer made 5,000,000
attempts, including 800,309 EMPTY observations. The retained prefix elapsed
1,472,506,585 ns. Arena replay hashes, raw identities, ordinals, checksums,
timestamps, demand/issue boundaries and drain accounting pass that routine.

This is explicitly **FAILED_WARMUP_PREFIX_ONLY**. Reset was correctly absent
after the failed warmup, and measurement origin is null. The full-capture
validator rejects the evidence with `mandatory session stop`; no full-study
retention report or duration selection is fabricated. Duration remains
`UNRESOLVED_NOT_ELIGIBLE`, with zero formal runs contributed.

## Subsequent planning

The inherited capacity table also conflicts with the immutable protocol's
full-footprint working-set rules. Preserve this attempt as failed history.
The [versioned amendment proposal](../../../STAGE17_EXT007_WORKING_SET_AMENDMENT_V1_PROPOSAL.md)
and proposed recovery study remain unapproved. Automatic approval review
rejected the new stand footprint helper before execution, citing the owner's
restriction on new work and the helper's remote allocations. No helper or
new study has run on the stand.

The PC observation after copy completion found 393,836,142,592 available
bytes, exceeding the proposed R2 allowance (including its 10 GiB reserve)
by 5,291,290,602 bytes. This is a dated resource observation, not a future
space guarantee; the stopped attempt remains retained and a fresh check is
required before any approved new launch.
