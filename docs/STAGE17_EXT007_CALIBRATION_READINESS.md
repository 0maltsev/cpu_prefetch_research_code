# EXT007 calibration continuation

State: **LOCAL_ENGINEERING_PROGRESS; NOT_AUTHORIZED_FOR_CALIBRATION_EXECUTION**.
Protocol: `2.0.0-pre.3`, unchanged. The external v5-12 journal retains its six
resolutions; EXT007 is not resolved by software tests or prospective policy.

The owner approved studying the missing parameters in a separate setup study.
[ADR-0178](decisions/0178-stage17-q16a-duration-discovery-proposal.md)
records the accepted route: a separate finite diagnostic setup study, followed
by a prospectively frozen formal D-037 plan with fresh data. It does not
allow changing duration/count thresholds during formal collection and has
not yet been executed. The owner accepted its design on 2026-10-30; exact
execution authority and the remaining prerequisites are still required.

ADR-0179 implements the accepted 36-key design and count-only selection
logic in `tools/stage17_q16a_discovery_v1.py`; thirteen synthetic tests pass.
The describe command produces no executable plan or empirical result. The
selector requires already-verified diagnostic facts and cannot admit them
as operational evidence. The
[resource inventory](evidence/stage17/STAND-AUDIT-CPU-PREFETCH-V5-20261030-01/discovery-resource-inventory.json)
records actual stand observations for future finite budget preparation;
it freezes no budget or owner capability and needs fresh pre-run readback.

ADR-0180 adds the C++ discovery worker component in
`include/cpu_prefetch/calibration/discovery_capture.hpp` and explicit trace
owner-prefaulting. It checks a fixed deadline and capacity before attempts,
retains partial counts/statuses, and cancels peers on failure. A separate
validator cross-checks trace counts only after both workers have joined.
It is exercised with the real SPSC ring and synthetic time;
it is not yet a standalone authorized diagnostic capture action. Warm-up
coordination/reset, actual thread/NUMA/page verification, the process
watchdog, raw publication/custody, and qualified diagnostic admission still
need integration before the 36-capture study can run. The old formal Q16a
sample-count loop remains unchanged; it must not be used under a new label.

## Implemented prerequisites

ADR-0177 integrates the existing hardware mappings into a testable whole-plot
controller and both Linux MSR adapters. Actual CPUID is checked before entry;
H0 reads preserve the default; H1 preserves reserved bits, verifies the full
value, and restores in reverse order. An ambiguous write is included in
restoration. A failed restore stays failed and prevents re-entry. Exception
handling attempts restoration on the remaining CPUs instead of silently
skipping them.

Worker preparation now checks the requirements of the registered software
mapping. The T0-only form accepts an observed lack of PRFCHW without changing
that observation into a claimed capability. The original form still requires
PRFCHW, and unknown mappings are rejected before private-stream preparation.

Calibration hardware evidence emits the existing v2 schema and actual mapping
ID. The additive fixed-action plan v6, registry v8, operational semantics v12,
phase controller v21, CLI v14, journal v48, and prospective policy v54 bind
the corrected path. Admission derives the mapping from schema-validated
Q15-R output and compares Q15-W prestate/result lineage. Both CPU identity
and exact apply/restore values are checked. The admission regression reaches
the CLI's real validator and the output registry's real byte-reading helper.

These are versioned successors, not an in-place migration of v5-12. They
require a clean release and fresh dependent qualification; they grant no
action authority. Pilot hardware-schema integration remains a later task;
this work does not claim pilot readiness or Stage B/C scope.

## Concrete execution blockers

The [read-only input audit](evidence/stage17/STAND-AUDIT-CPU-PREFETCH-V5-20261030-01/ext007-input-audit.json)
hashes the actual v5-12 Q16a draft. It has 708 captures and 100,000 samples
per capture. Its per-capture fields contain neither `duration_ticks` nor
`minimum_observations_per_series`, although the accepted D-037 method and
`calibration-plan-v1.schema.json` require prospective values. No approved
typed calibration plan supplying those values was found in the inspected
Q16a authoring directories. The draft freeze is `NOT_EVALUATED` and retains
Q16a/b/c as unresolved inputs.

The separate warm-up record declares 10 ms, but `q16a_capture` does not read
it or warm up before collecting. Its current loop stops by sample count,
not a frozen duration. The event arena and ring are allocated/initialized
on the controller thread; the capture path does not independently establish
producer-home NUMA residency or implement the proposed warm-up record.
These gaps must be corrected against an approved prospective plan before
calibration; they cannot be repaired by relabeling a completed capture.

Before any stand execution:

1. Supply the approved D-037 duration and minimum observations for each
   context, and bind them in a typed prospective plan. Confirm the intended
   warm-up/reset behavior in the same record. If a different scientific method
   is desired, obtain the required versioned protocol amendment first.
2. Implement and test those exact capture/termination/preparation semantics,
   verify class-specific memory residency, and check the failure/quarantine
   path under restoration uncertainty. Preserve every invalid capture.
3. Produce the clean release with every mandatory codegen/dependency/schema
   check, integrate the new policy into a versioned candidate profile, and
   requalify dependent evidence. Do not copy qualification from the old binary.
4. Append the required operational transition only after all prerequisites
   validate, then issue the finite, signed Q16a authority for the exact plan.
5. Execute Q16a, derive its registered distance freeze, then prepare and
   authorize Q16b and Q16c in order. Only complete valid action families and
   their accepted freeze may resolve EXT007. A low/unfavorable result grants
   no retry, top-up, or extension.

## Verification commands

```sh
cmake --build --preset dev-gcc --target cpu_prefetch_q15_tool_tests cpu_prefetch_runner_tests stage17-calibration-mapping-check
build/dev-gcc/cpu_prefetch_q15_tool_tests
build/dev-gcc/cpu_prefetch_runner_tests
ctest --preset dev-gcc -R '^runner.stage17_calibration_mapping$'
cmake --build --preset dev-gcc --target stage17-calibration-policy-check
cmake --build --preset dev-gcc --target cpu_prefetch_calibration_tests
build/dev-gcc/cpu_prefetch_calibration_tests --gtest_brief=1
ctest --preset dev-gcc -R '^DiscoveryCaptureWindow\.'
```

The affected C++ suites pass 12/12 and 29/29 under GCC development,
ASan/UBSan, and TSan. Python checks pass for two mappings, six output
families, 36 output mutants, six request mutants, and eight malformed
prestates. The strict release combined-prefetch check passes both GNU and
LLVM disassemblers, 16 operations, and five mutants. Changed C++ files pass
formatting and the diff passes whitespace checking.
The policy author check reproduces the v54 bytes, and journal replay under
that policy independently retains `PREPARED`, zero resolutions/transitions,
ten missing inputs, and `pilot_ready=false`.

The missing old Clang/libc++ prefix was restored as an isolated new prefix
`/tmp/cpu-prefetch-ext007-deps.dRlOzG`, using the unchanged archive hashes
and licenses in `config/dependencies.json`, system Python 3.14.5, and
compiler-specific GoogleTest/RapidCheck builds. All 66 affected C++ tests
(25 calibration, 12 Q15, 29 runner) pass under development Clang/libc++.
The 25 calibration tests also pass under GCC ASan/UBSan and TSan. All 66
affected tests pass under Clang/libc++ ASan/UBSan and TSan after restoration.
The global
format target fails on untouched baseline files; the `HEAD` version of
`tests/platform_model_test.cpp` independently reproduces its formatting
errors. These failures were not bypassed or reported as passing.
Static analysis also retains the baseline `spin_wait_nanoseconds` exception
diagnostic and the two baseline optional-access diagnostics in
`tests/runner_model_test.cpp`; the affected code is unchanged, and the same
diagnostics exist in the earlier baseline logs. They remain release blockers.

The immutable pre.3 Section 5.4 and D-116 amendment already require exactly
five seconds for pre-freeze formal calibration/pilot warm-up. The external
10 ms draft cannot override that rule. The diagnostic implementation must
prospectively bind its warm-up and retain the same drain, quiescent reset,
persistent mappings, and synchronized measurement-start obligations.
