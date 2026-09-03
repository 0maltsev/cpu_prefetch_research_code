# 0152. Stage 17 S17-EXT-004 software-prefetch-mapping evidence

Status: PROPOSED

## Context

S17-EXT-004's `SOFTWARE_PREFETCH_MAPPING` qualification-evidence kind
requires (`config/schemas/qualification-evidence-v1.schema.json`'s
`software_prefetch_mapping_details`) fourteen fields split across two
real, distinct gaps. This kind was originally scoped together with
`RUNTIME_ATOMIC_LAYOUT` in ADR-0147, on the assumption both were pure
wiring of already-real data; that assumption held for `RUNTIME_ATOMIC_
LAYOUT` but not for this kind, so it is split out here.

### Gap 1: CPUID/PRFCHW capability data belongs to a different, never-run action

`producer_maximum_extended_leaf`/`producer_extended_leaf_ecx`/`producer_
prfchw_supported` and the matching `consumer_*` fields need a real
`SoftwarePrefetchCapabilityObservation` (`include/cpu_prefetch/runner/
software_prefetch.hpp`) per worker. The real backend that produces this,
`X86CurrentCpuSoftwarePrefetchCapabilityBackend::observe()` (`src/runner/
runner.cpp:176`), is real, compiled, production code -- but its only
caller is `PilotObservationPreparation` (`src/runner/stage17_fixed_
action.cpp:1477`, via its `AffinedObservationPreparation` member), which
is used exclusively by `run_pilot_session_worker` (`--execute-stage17-
pilot-session-v1`), a real action entirely separate from Q15-R (`run_q15_
phase_session_worker`). A repository-wide search confirms Q15-R's own
probe-pass code (`src/platform/q15_runtime.cpp`, `src/platform/q15_
probe.cpp`, `include/cpu_prefetch/platform/q15_runtime.hpp`) contains no
CPUID/PRFCHW check at all. A further search of every `stage17-owner-
evidence` admission root and release-bundle extraction confirms the pilot
session action has never actually been run for real anywhere -- only its
schema (`stage17-pilot-session-completion-v1.schema.json`) has ever
shipped in a bundle.

### Gap 2: dual-compiler codegen verification is not wired for this mapping

`gcc_codegen_passed`, `clang_codegen_passed`, `gnu_objdump_passed`, and
`llvm_objdump_passed` require verifying the D-047 `X86RetainingPrefetch
Emitter` mapping (`include/cpu_prefetch/runner/software_prefetch.hpp`:
`ring_producer_write` emits `prefetchw`, `ring_consumer_read`/`successor_
header` emit `prefetcht0`) was correctly compiled, under two different
compilers, disassembled by two different tools. This gap is smaller than
first assessed: real, already-built Clang+libc++ toolchain configurations
exist and are actively used (`dev-clang-libcxx`/`release-clang-libcxx`/
`asan-ubsan-clang-libcxx`/`tsan-clang-libcxx` in `CMakePresets.json`,
exercised today for sanitizer analysis per `docs/ANALYSIS.md`), and
`llvm-objdump` is installed (`/usr/bin/llvm-objdump`). `CMakeLists.txt`
already has a real, working pattern for dual-disassembler codegen audits
(`runner-relax-codegen-check`, `runner-combined-codegen-check`, `q15-
probe-codegen-check`, etc., each comparing a probe/mutant binary pair via
`tools/check_*_codegen.py --gnu-objdump ...`) -- every one of these is
GNU-objdump-only today, and none targets the D-047 `ring_producer_write`/
`ring_consumer_read`/`successor_header` symbols specifically. What is
genuinely missing is: a codegen-probe/mutant executable pair for the
D-047 symbols, a second build of that pair under the `dev-clang-libcxx`
preset, and a `check_*_codegen.py`-style script extended to accept both
`--gnu-objdump` and `--llvm-objdump` and compare all four combinations --
real wiring work following an already-proven in-repo pattern, not new
toolchain standup. The four schema fields have no real implementation
path today; they appear only as synthetic literals in `tests/runner_
model_test.cpp`.

## Decision (proposed)

Before any implementation, resolve one scoping question (Gap 2's own
wiring, once scoped, follows the existing dual-disassembler pattern
directly and needs no further decision):

1. **CPUID wiring.** Either (a) add a real CPUID/PRFCHW capability check
   directly to Q15-R's own worker path (smallest real code change, keeps
   all S17-EXT-004 evidence tied to one action/session), or (b) actually
   run the never-executed pilot-session action for real on the stand and
   cross-bind its evidence into S17-EXT-004's manifest alongside a Q15-R
   session (larger: a second real action needs its own full authoring/
   admission/execution cycle established, mirroring the work already done
   for Q15-R). (a) is very likely the more consistent match with S17-
   EXT-004's own `EXPECTED_ROLES`, which otherwise binds everything to a
   single Q15-R-session's lineage.

Only after this question is resolved should a real implementation be
designed.

## Consequences

- Gap 1 (CPUID wiring) is the real open design question here; Gap 2
  (dual-compiler codegen verification) is real but mechanical, following
  an already-proven six-times-repeated in-repo pattern once a probe/
  mutant pair for the D-047 symbols exists.
- Smaller in total scope than originally assessed, but still larger than
  ADR-0147's `RUNTIME_ATOMIC_LAYOUT`, since Gap 1 requires a real design
  decision plus a new C++ measurement call site (or a second real action's
  full lifecycle).
- Blocks S17-EXT-004 admission independent of ADR-0147/0148/0149/0150 --
  all five `QUALIFICATION_EVIDENCE` kinds are required together.
