# 0151. Stage 17 S17-EXT-004 platform manifest and pilot platform measurements

Status: PROPOSED

## Context

S17-EXT-004 also requires `PLATFORM_MANIFEST` (1) and `PILOT_PLATFORM_
MEASUREMENTS` (1) artifacts, validated by `stage17_operational_
semantics_v4.py`'s own S17-EXT-004 dispatch branch:

- `PLATFORM_MANIFEST` binds real, already-known hardware/build facts
  (CPU vendor/model/stepping, cache-line bytes, topology, memory
  population method, software toolchain identity, clock source, and a
  `record_sha256` binding to the real Q15-R output file) -- structurally
  close to the `RUNTIME_IDENTITY`/`TRUST_ANCHOR` typed records this
  session already hand-authored for real S17-EXT-002 admissions.
- `PILOT_PLATFORM_MEASUREMENTS` requires `subject_id == stand_id` and
  `measurements.platform_manifest_sha256 == sha(platform_manifest_bytes)`
  plus `measurements.q15_r_result_sha256 == family["result_sha256"]`
  (the real Q15-R result's own hash, already known from any of the three
  real sessions this session captured).

Unlike `QUALIFICATION_EVIDENCE` (ADR-0147 through ADR-0150), neither of
these two artifacts depends on any telemetry the real Q15-R worker
currently fails to serialize -- both can be built today from real,
already-observable facts (hardware topology already queried live via
SSH earlier this session, the real bundle's own compiled-in CPU family/
model constants, and the real, already-admitted Q15-R result file's own
hash), the same way this session hand-authored S17-EXT-002/003's typed
records.

## Decision (proposed)

Hand-author `PLATFORM_MANIFEST` and `PILOT_PLATFORM_MEASUREMENTS` typed
records for one of the three real, already-captured Q15-R sessions
(`-16E`/`-17`/`-18`), following the same pattern established for S17-
EXT-002/003's `author-manifest`/typed-record authoring this session,
using real, already-known facts:

- real CPU identity (family 6, model 85 -- already confirmed via live
  SSH query against the stand earlier this session),
- real cache-line/page-size/topology facts (already queried),
- the real, already-admitted Q15-R result file's own hash for the
  chosen session,
- `record_sha256` binding to the exact real `q15-r-output-v3.json` bytes
  for that session.

This can be done in advance of ADR-0147 through ADR-0150's own
implementation, since it does not depend on them, but does not by
itself unblock S17-EXT-004 admission -- `stage17_operational_semantics_
v4.py`'s `EXPECTED_ROLES["S17-EXT-004"]` requires all eleven typed
artifacts (the six `Q15_R_*` phase-family roles, five `QUALIFICATION_
EVIDENCE` items, `PLATFORM_MANIFEST`, and `PILOT_PLATFORM_
MEASUREMENTS`) present together in one manifest.

## Consequences

- Lowest-risk, most immediately actionable piece of S17-EXT-004's own
  evidence set -- no real hardware time, no C++ change, same discipline
  already proven for S17-EXT-002/003.
- Does not reduce the real scope of ADR-0147 through ADR-0150; S17-
  EXT-004 admission still waits on all of them.
- Should record which of the three real Q15-R sessions (`-16E`, `-17`,
  `-18`) is the one S17-EXT-004 will ultimately bind to, since the
  `Q15_R_RESULT`/`Q15_R_READ_ONLY_PRESTATE` lineage these records
  reference is session-specific.
