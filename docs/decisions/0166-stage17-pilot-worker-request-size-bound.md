# ADR-0166: Stage 17 compiled worker request size bound for the real pilot

- **Status:** `ACCEPTED`
- **Decision ID:** D-166
- **Classification:** implementation correctness, compiled-binary
  defensive-bound adjustment; requires a new pilot-candidate release
  and a fresh journal
- **Owner:** repository/build/runner owner
- **Gate:** before any real `STAGE17-BLINDED-PILOT` `execute-action`
  can succeed; a new pilot-candidate bundle and a fresh journal's
  `S17-EXT-001` through `S17-EXT-010` admission are both required
  downstream of this fix

## Context

The first real `execute-action` attempt for `STAGE17-BLINDED-PILOT` on
standv2-30 (authorization window 2026-09-15T06:49:32Z-09:54:32Z)
failed in 0.65 seconds, before any real hardware run started
(`stage17-blinded-pilot-output-standv2-30/` left empty; restoration
verified for all three MSRs), with `stage17-operational: FAIL: fixed
worker returned 1` and real worker stderr `"runner: FAIL: pilot sealed
input read failed"`.

Root-caused by direct code reading, not assumed:
`src/runner/stage17_fixed_action.cpp`'s `run_pilot_session_worker`
reads the real request file via `read_regular_fd(*request_fd)`, bound
by the file's own `kMaximumRequestBytes` constant. That constant was
already raised once, from 16 MiB to 64 MiB, earlier in this same file
(see the comment immediately above it) for Q16b's real ~35-47MB
request. The real `STAGE17-BLINDED-PILOT` request is larger still:
`STAGE17-BLINDED-PILOT`'s real request must embed the complete, real,
admitted `S17-EXT-008` pilot plan verbatim (`_validate_action_inputs`
and `verify_manifest_v4`'s `S17-EXT-010` branch both require exact,
byte-for-byte equality with the admitted plan, not a reference) -- 180
cells x 3 repetitions = 540 runs, each carrying its own complete
`schedule_deadline_ticks`/`warmup_schedule_deadline_ticks` arrays and
runner_admission ticket, per the same no-shared-reference contract
Q16b's own runs use. The real request file is 68,835,354 bytes, past
the 64 MiB (67,108,864-byte) ceiling.

This is a *compiled* bound: unlike the four independent Python-side
size caps already fixed this session (ADR-0162 through ADR-0165, all
additive-successor monkeypatches), this one lives in the worker binary
itself and cannot be patched at runtime. An architectural alternative
-- referencing the plan by hash instead of embedding it, so the
request stays small -- was considered and rejected: it would require
changing both `_validate_action_inputs` and `verify_manifest_v4`'s
`S17-EXT-010` semantic check, a larger and riskier redesign than
raising one constant, for no real benefit (the plan's own bytes are
genuinely needed by the worker to execute against). The separate
`--context-fd` channel is not a viable alternative either: it carries
only small IDs/hashes (`stage17_fixed_action_executor_v2.py`'s own
`context` dict has six scalar fields), with no existing large-payload
channel to redirect the plan through.

## Decision

Raise `kMaximumRequestBytes` in `src/runner/stage17_fixed_action.cpp`
from 64 MiB to 128 MiB -- real headroom over the measured 68.8 MB
request, so a modest future plan variant (e.g. a different
`repetitions_per_cell`) does not immediately repeat this failure.
`kMaximumWorkerBytes` (bounding the worker's own self-read of `/proc/
self/exe` for identity verification, unrelated to request/context
size) is untouched.

## Effects

- Changes a file already hash-pinned by the real, already-admitted
  `S17-EXT-002` resolution (`RUNTIME_WORKER_BINARY`). Per this
  engagement's established pattern for compiled-file changes (ADR-0159
  through ADR-0161), this requires: a real rebuild of the worker binary
  (`release-gcc` CMake preset, GCC 16.1.1, matching ADR-0151's
  documented real build facts), a new pilot-candidate bundle with a new
  worker `binary_sha256`, and a fresh journal admitting `S17-EXT-001`
  through `S17-EXT-010` again from scratch against that new build --
  including real hardware re-execution of Q15-R, Q15-W, Q16a, Q16b
  (3540 real runs), and Q16c, followed by rebuilding the `S17-EXT-007`
  calibration freeze, `S17-EXT-008` pilot plan, `S17-EXT-009`
  custody/storage evidence, and a freshly-signed `S17-EXT-010`
  authorization.
- None of the four Python-side additive-successor fixes from this
  session (ADR-0162 through ADR-0165) are affected by or need
  reapplying differently for this change -- they remain valid, real
  fixes to genuine, independent bounds, and should still be folded into
  the next pilot-candidate release's own import chain (already noted
  in each of their own ADRs) rather than continuing to rely on the
  wrapper pattern once a fresh journal exists.
