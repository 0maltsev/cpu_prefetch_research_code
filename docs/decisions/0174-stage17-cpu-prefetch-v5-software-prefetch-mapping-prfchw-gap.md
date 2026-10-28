# 0174. Stage 17 `cpu-prefetch-v5` lacks PRFCHW: `SOFTWARE_PREFETCH_MAPPING` evidence is genuinely ineligible

Status: ACCEPTED (Option 2 chosen; implemented in ADR-0175)

## Context

While building a real `S17-EXT-004` manifest on `cpu-prefetch-v5` (a fresh
evidence root, `local-authoring-cpuprefetchv5-9`, built from a real, live,
held-open Q15-R session sealed at `H0_SEALED_WAITING_FOR_Q15_W`), 4 of the
5 required `QUALIFICATION_EVIDENCE` kinds passed with real data:
`RUNTIME_ATOMIC_LAYOUT`, `ACTUAL_CPU_MIGRATION`, `ADDRESS_RESIDENCY`, and
`SELECTED_PAIR_CLOCK` (the last requiring a real, non-mutating wall-clock
cross-core timing measurement, also run for real on this stand: PASS,
`producer_per_core_passes=1 consumer_per_core_passes=1
cross_core_passes=1`).

The 5th, `SOFTWARE_PREFETCH_MAPPING`, genuinely failed:
`cpu_prefetch_q15_qualification_evidence_tool --kind
SOFTWARE_PREFETCH_MAPPING` reported `eligible=false` against this
session's own real `q15-r-software-prefetch-raw-v1.json`, whose real,
already-captured CPUID observation shows
`producer_prfchw_supported: false` and `consumer_prfchw_supported:
false` for both the producer and consumer roles (the real worker has no
real thread pair, so one real observation honestly stands for both, per
ADR-0152). Confirmed directly from `include/cpu_prefetch/runner/
software_prefetch.hpp`'s own `SoftwarePrefetchCapabilityObservation::
passes()`: eligibility unconditionally requires
`maximum_extended_leaf >= kPrfchwExtendedLeaf && (extended_leaf_ecx &
kPrfchwEcxMask) != 0 && prfchw_supported` -- there is no path to
`eligible=true` without real PRFCHW support.

This is a genuine, permanent, CPU-model-wide hardware fact, not a bug or
a flaky measurement: `cpu-prefetch-v5` is an Intel Xeon E5-2667 v2 (Ivy
Bridge-EP, family 6 model 62/`0x3E`), and Intel did not add PRFCHW
support until Broadwell. Confirmed independently via a fresh read-only
`/proc/cpuinfo` query on the stand: the real `flags` line has no
`prefetchw`. The prior stand this exact evidence kind was built and
admitted on (`XEON-CPU-FETCH`, ADR-0152's own "real envelope" section)
was a newer Xeon Gold chip that does support PRFCHW -- that precedent
does not transfer to this stand's older silicon, and was not assumed to.

`tools/stage17_operational_semantics_v4.py`'s real `S17-EXT-004`
admission branch (reached via `stage17_semantic_verifier_v41.py`'s
dispatch, unchanged through the currently-bound policy v52) hard-requires
all 5 `QUALIFICATION_EVIDENCE` kinds to report `eligible: true`
(`any(not item["eligible"] for item in evidence...)` raises otherwise).
There is exactly one registered software-prefetch mapping in this
codebase (`kSoftwarePrefetchMappingId`, "X86-64-PREFETCHW-PREFETCHT0-v1"),
which requires PRFCHW for one of its two instructions. No alternate,
PRFCHW-free mapping exists. Consequently: **`S17-EXT-004` cannot be
admitted on `cpu-prefetch-v5`, on any evidence root, under the protocol
and codebase as they currently stand** -- and since Q15-W's own
action-registry entry requires `S17-EXT-004`, this transitively blocks
Q15-W, and everything downstream of it (Q16a/b/c, pilot), on this stand.

This is exactly the situation AGENTS.md's own governing rule describes:
"Code must not silently change the experiment design. A contradiction or
missing scientific decision blocks the affected implementation and
requires a versioned protocol amendment." No workaround was attempted;
the owner was informed and chose to let the live session lapse (its
worker process reaped on timeout, the same safe, no-manual-recovery
mechanism already confirmed for the prior `local-authoring-
cpuprefetchv5-8` session) rather than force a decision under the
pressure of a live, time-boxed session.

## Real evidence preserved

Under `local-authoring-cpuprefetchv5-9` (not yet admitted, not deleted):
`ext004-authoring-1/q15-clock-pair-raw-near-1.json`,
`qualification-evidence-runtime-atomic-layout.json`,
`qualification-evidence-actual-cpu-migration.json`,
`qualification-evidence-address-residency.json`,
`qualification-evidence-selected-pair-clock.json` (all real, all
`eligible: true`), and `qualification-evidence-software-prefetch-
mapping.json` (real, `eligible: false`, the artifact this ADR is about).
The underlying `q15-r-software-prefetch-raw-v1.json` (and the rest of
that session's real Q15-R output) remains on disk at the evidence root's
top level.

## Options (not yet decided)

1. **Accept that `cpu-prefetch-v5` cannot reach Q15-W under the current
   protocol.** No code change; this stand's own scope is limited to
   whatever Q15-R alone (and any action not gated on `S17-EXT-004`)
   already provides.
2. **Amend the protocol/codebase to add a second, honestly-scoped
   software-prefetch mapping** that does not depend on PRFCHW (e.g., a
   PREFETCHT0-only mapping for CPU models lacking it), mirroring the
   precedent already set by ADR-0172/0173 for the hardware-prefetch MSR
   mapping and the near/far pair identity -- a real `kSoftwarePrefetch
   MappingIdNoprfchw`-style registry entry, a new emitter/codegen check
   (D-047's own dual-disassembler discipline would need to cover it too),
   and a schema/`EXPECTED_ROLES` change to accept either mapping.
3. **Amend `S17-EXT-004`'s own admission requirement** to make
   `SOFTWARE_PREFETCH_MAPPING` conditionally required only for CPU models
   that support PRFCHW, with an honest "not applicable" artifact shape
   for those that do not -- a different, narrower protocol amendment than
   option 2, touching admission semantics rather than adding new runner
   capability.

Each of these is a real engineering/protocol decision with scientific
interpretation consequences (AGENTS.md: "every implementation decision
that affects scientific interpretation requires an ADR") and is
deliberately left open here rather than decided unilaterally.

## Consequences

- `S17-EXT-004`, and therefore Q15-W/Q16/pilot, is blocked on
  `cpu-prefetch-v5` until one of the above (or another option) is
  decided and implemented.
- The 4 genuinely-eligible qualification-evidence kinds, and the full
  EXT-004 authoring script (`/tmp/build-ext004-from-live-q15r-session.sh`,
  staged on the stand, not yet successfully run end-to-end) remain valid
  and reusable once this is resolved -- only the `SOFTWARE_PREFETCH_
  MAPPING` step needs revisiting.
- `local-authoring-cpuprefetchv5-9`'s live Q15-R session (sealed at
  `H0_SEALED_WAITING_FOR_Q15_W`) was allowed to lapse; a fresh Q15-R
  session (on this or another evidence root) will be needed once this
  ADR is resolved, following the same real authoring chain documented in
  ADR-0173's implementation notes.
