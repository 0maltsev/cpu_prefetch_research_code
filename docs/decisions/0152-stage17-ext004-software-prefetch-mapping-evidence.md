# 0152. Stage 17 S17-EXT-004 software-prefetch-mapping evidence

Status: ACCEPTED

## Context

S17-EXT-004's `SOFTWARE_PREFETCH_MAPPING` qualification-evidence kind
requires (`config/schemas/qualification-evidence-v1.schema.json`'s
`software_prefetch_mapping_details`) fourteen fields split across two
real, distinct gaps. This kind was originally scoped together with
`RUNTIME_ATOMIC_LAYOUT` in ADR-0147, on the assumption both were pure
wiring of already-real data; that assumption held for `RUNTIME_ATOMIC_
LAYOUT` but not for this kind, so it is split out here.

### Gap 1: CPUID/PRFCHW capability data belonged to a different, never-run action

`producer_maximum_extended_leaf`/`producer_extended_leaf_ecx`/`producer_
prfchw_supported` and the matching `consumer_*` fields need a real
`SoftwarePrefetchCapabilityObservation` (`include/cpu_prefetch/runner/
software_prefetch.hpp`) per worker. The real backend that produces this,
`X86CurrentCpuSoftwarePrefetchCapabilityBackend::observe()` (`src/runner/
runner.cpp:176`), is real, compiled, production code -- but before this
ADR its only caller was `PilotObservationPreparation` (`src/runner/
stage17_fixed_action.cpp:1477`), used exclusively by `run_pilot_session_
worker` (`--execute-stage17-pilot-session-v1`), a real action entirely
separate from Q15-R and never actually run for real anywhere (only its
schema has ever shipped in a bundle). Q15-R's own probe-pass code
contained no CPUID/PRFCHW check at all.

### Gap 2: dual-compiler codegen verification was not wired for this mapping

`gcc_codegen_passed`, `clang_codegen_passed`, `gnu_objdump_passed`, and
`llvm_objdump_passed` require verifying the D-047 `X86RetainingPrefetch
Emitter` mapping (`ring_producer_write` emits `prefetchw`, `ring_
consumer_read`/`successor_header` emit `prefetcht0`) was correctly
compiled under two different compilers, disassembled by two different
tools. Empirically confirmed before implementing: `tools/check_runner_
codegen.py` already accepts and exercises both `--gnu-objdump` and
`--llvm-objdump` against a single binary (running it against the real
`runner-relax-codegen-check` probe/mutant pair showed both tools PASS);
`tools/check_ci.py` already runs that same check under both the
`release-gcc` and `release-clang-libcxx` presets in CI -- the dual-
compiler pattern this kind needs already exists end-to-end for other
mappings, just not for the D-047 symbols specifically.

## Decision

**Gap 1**: added a real CPUID/PRFCHW capability check directly to Q15-R's
own worker path, per the resolved scoping question (the alternative --
running the never-executed pilot-session action for real and cross-
binding its evidence -- would have required standing up a second real
action's full authoring/admission/execution lifecycle for no benefit,
since S17-EXT-004's `EXPECTED_ROLES` otherwise binds everything to one
Q15-R session's lineage).

**Gap 2**: added a real, dual-disassembler-verified codegen-probe/mutant
pair for the D-047 symbols, mirroring the six existing `check_*_codegen.
py` patterns exactly.

## Implementation

- `publish_q15_r` (`src/runner/stage17_fixed_action.cpp`) now also
  publishes `Q15_R_SOFTWARE_PREFETCH_RAW` (`q15-r-software-prefetch-raw-
  v1.json`, new schema `stage17-q15-r-software-prefetch-raw-v1.schema.
  json`): one real `X86CurrentCpuSoftwarePrefetchCapabilityBackend::
  observe()` call, reported for both `producer_*` and `consumer_*`
  fields. PRFCHW support is a CPU-model-wide microarchitectural fact, not
  per-core, and Q15-R has no real producer/consumer thread pair (a single
  probe CPU) -- one real observation honestly stands for both schema
  fields; this is noted in the code.
- New `tools/software_prefetch_mapping_codegen_probe.cpp` (calls the real
  `X86RetainingPrefetchEmitter` methods through three `extern "C"`
  symbols) and `tools/software_prefetch_mapping_codegen_mutant.cpp`
  (deliberately swapped mapping, to prove the check catches mistakes).
- New `tools/check_software_prefetch_mapping_codegen.py`, mirroring
  `check_runner_codegen.py`'s structure: verifies each probe symbol
  contains exactly one correct prefetch mnemonic and no other, and each
  mutant symbol contains exactly the wrong one, under both `objdump` and
  `llvm-objdump`.
- New CMake targets: `cpu_prefetch_software_prefetch_mapping_codegen_
  probe`/`_mutant`, `software-prefetch-mapping-codegen-check`.
- New `Q15_R_SOFTWARE_PREFETCH_RAW` role added to `stage17-operational-
  artifact-v4.schema.json`'s closed role enum.

Verified for real: `software-prefetch-mapping-codegen-check` PASSES
under both `release-gcc` (GCC 16.1.1) and `release-clang-libcxx`
(Clang+libc++) presets, with both `objdump` and `llvm-objdump`, on the
first attempt under each. `cpu_prefetch_runner_tests` (20/20) and both
`check_qualification_schema.py`/`check_runner_schema.py` pass unchanged.

Deliberately not done in this pass: `software-prefetch-mapping-codegen-
check` was not added to the `create-stand-bundle`/`stage17-hermetic-
handoff-check` bundle-gating `DEPENDS` lists, nor to `check_ci.py`'s
`REQUIRED_COMMANDS`/README/workflow wiring. Precedent supports leaving
this open: `q15-probe-codegen-check`, `q15-runtime-codegen-check`, and
`q15-controller-codegen-check` are real, existing, passing codegen
checks that are *also* absent from both the bundle-gate and CI lists --
not every codegen check is curated into those two lists, and widening
either is a separate decision from building the check itself.

## Consequences

- Both real gaps in this ADR are closed at the wiring/verification level.
  What remains, matching ADR-0147's own remaining work: a real Q15-R
  re-run on the stand to produce `q15-r-software-prefetch-raw-v1.json`
  for real (no existing captured session has it), a Python authoring
  tool (ADR-0151's pattern) combining that raw artifact with the
  `software-prefetch-mapping-codegen-check` report's real PASS/FAIL
  results into the final schema-compliant `SOFTWARE_PREFETCH_MAPPING`
  `QUALIFICATION_EVIDENCE` record, and a bundle reseal to carry the
  recompiled binary and new schemas.
- Whether `software-prefetch-mapping-codegen-check` should become a hard
  bundle/CI gate is left open for a separate decision.
- Blocks S17-EXT-004 admission independent of ADR-0147/0148/0149/0150 --
  all five `QUALIFICATION_EVIDENCE` kinds are required together.
