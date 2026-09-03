# 0151. Stage 17 S17-EXT-004 platform manifest and pilot platform measurements

Status: ACCEPTED

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

## Decision

Hand-author `PLATFORM_MANIFEST` and `PILOT_PLATFORM_MEASUREMENTS` typed
records, following the same pattern established for S17-EXT-002/003's
`author-manifest`/typed-record authoring, using real, already-known
facts: real CPU identity, real cache-line/page-size/topology facts, the
real, already-admitted Q15-R result file's own hash for the chosen
session, and `record_sha256` binding to that same real hash.

An earlier draft (`stage17-owner-evidence/ext004-authoring-18/`) did
this for session `-18`, before this ADR was implemented. Two things
about it needed correcting rather than reusing as-is:

- Session `-18` predates ADR-0147/ADR-0148/ADR-0152's raw-artifact
  wiring into `publish_q15_r`. `stage17_operational_semantics_v4.py`'s
  S17-EXT-004 handler resolves one shared Q15-R phase family
  (`_phase_family(..., action_id="Q15-R", ...)`) for *both* the five
  `QUALIFICATION_EVIDENCE` envelopes and `PILOT_PLATFORM_MEASUREMENTS`'s
  `q15_r_result_sha256` -- they must all reference the same session. Only
  session `-20` (the real, successful run made after that wiring existed)
  can be that session, so the binding was redone against `-20`.
- Its `record_sha256`/`q15_r_result_sha256` were bound to `Q15_R_
  READ_ONLY_PRESTATE`'s own file (`q15-r-output-v3.json`) rather than the
  real `Q15_R_RESULT` phase artifact `_phase_family` actually validates
  (`stage17-q15-r-result-v4.json`, which carries `artifacts`/
  `request_sha256`/`authorization_sha256`/`attempt_id` -- confirmed by
  reading both files' real content on the stand; `q15-r-output-v3.json`
  has none of those fields, only the prestate/probe observation itself).
  session `-20`'s records use the real `Q15_R_RESULT` file's hash.

Real facts for session `-20` were obtained via a read-only SSH query
against the stand (find the real result files, `sha256sum`/`stat` them,
re-observe kernel/CPU/topology fresh rather than assume session `-18`'s
values still held) plus this repository's own real build facts (GCC
16.1.1, C++20, `-O3 -DNDEBUG`, dynamic linking -- confirmed by actually
compiling and inspecting a binary here, not assumed). No admission,
signing, or state mutation was performed; every command was a read.

This can be done in advance of ADR-0147 through ADR-0150's own
implementation, since it does not depend on them, but does not by
itself unblock S17-EXT-004 admission -- `stage17_operational_semantics_
v4.py`'s `EXPECTED_ROLES["S17-EXT-004"]` requires all eleven typed
artifacts (the six `Q15_R_*` phase-family roles, five `QUALIFICATION_
EVIDENCE` items, `PLATFORM_MANIFEST`, and `PILOT_PLATFORM_
MEASUREMENTS`) present together in one manifest.

## Implementation

`platform-manifest-20.json` and `pilot-platform-measurements-20.json`
(`/home/omaltsev/stage17-owner-evidence/ext004-authoring-20/`, outside
the repository like all other real S17-EXT-00x hand-authored records
this session), bound to real session `-20`:

- `platform-manifest-20.json`: real CPU (`GenuineIntel`, `06_55H`,
  stepping `7`, microcode `0x5003901`, all re-confirmed fresh via SSH,
  unchanged from session `-18`), real topology (2 sockets, 2 NUMA nodes,
  52 physical cores, SMT on, near pair `[0,1]`/far pair `[0,26]` matching
  `kNearWorkerPair`/`kFarWorkerPair`), real software facts from this
  build environment (kernel `7.0.0-30-generic`, GCC 16.1.1, C++20,
  `-O3 -DNDEBUG`, dynamic linking), `hardware_prefetch_states` with H0
  honestly `VERIFIED_DEFAULT` (Q15-R only ever observes the default
  state) and H1 honestly `UNKNOWN` (no real H0/H1 toggle has ever been
  performed by any action in this codebase -- `privileged_authority_id:
  "NONE"`), and `record_sha256` bound to the real `stage17-q15-r-
  result-v4.json` for session `-20`
  (`180fa0ea0374348b4fe0a7ceadf4c597835743e45e1761bca21e144954dbcfd4`,
  2887 bytes).
- `pilot-platform-measurements-20.json`: `subject_id: "XEON-CPU-FETCH"`
  (confirmed against the real admitted `stand_id` in `ext002-manifest-
  20.json`), `measurements.platform_manifest_sha256` bound to the real
  bytes of the file above, `measurements.q15_r_result_sha256` bound to
  the same real `Q15_R_RESULT` hash.

Verified: both validate against their real schemas (`protocol/2.0.0-
pre.3/handoff/schemas/platform.schema.json`,
`config/schemas/stage17-operational-typed-record-v4.schema.json`); the
two hashes referenced internally are self-consistent (`source_bindings`
entries match `measurements`).

Not resolved by this: session `-20`'s own real `Q15_R_RESULT.artifacts`
lists only `Q15_R_READ_ONLY_PRESTATE`/`Q15_R_ATOMIC_LAYOUT_RAW`/
`Q15_R_SOFTWARE_PREFETCH_RAW`/`Q15_R_CPU_MIGRATION_RAW` -- it predates
ADR-0149 and has no `Q15_R_ADDRESS_RESIDENCY_RAW`, and no session
anywhere has real `SELECTED_PAIR_CLOCK` data (ADR-0150's own gap). If
S17-EXT-004 ultimately needs a session with all five raw kinds, a fresh
real Q15-R session will have to run against a build that includes
ADR-0149's wiring, and these two records will need rebinding to it the
same way session `-18`'s needed rebinding to `-20` here -- the same
lesson this ADR just re-learned should be applied again rather than
assumed away.

## Consequences

- Lowest-risk, most immediately actionable piece of S17-EXT-004's own
  evidence set -- no new real hardware time (session `-20` already ran),
  no C++ change, same discipline already proven for S17-EXT-002/003.
- Does not reduce the real scope of ADR-0147 through ADR-0150; S17-
  EXT-004 admission still waits on all of them, plus a session that has
  every raw kind at once, which none does yet.
- Found and fixed a real, previously undetected mistake in the
  `-18`-bound draft (bound to `Q15_R_READ_ONLY_PRESTATE` instead of
  `Q15_R_RESULT`) before it could propagate into a real admission
  attempt -- worth remembering for whichever session's records replace
  session `-20`'s in turn.
