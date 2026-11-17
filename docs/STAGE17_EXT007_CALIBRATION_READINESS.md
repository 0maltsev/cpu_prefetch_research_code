# EXT007 calibration continuation

State: **Q16A_Q16B_FIXED; Q16C_SOURCES_LAYOUTS_COMPLETE; CLOCKS_PASS; Q15_QUALIFICATION_RUNNING; AUTOMATIC_HANDOFF_ARMED**.

**Current EXT007 checkpoint (2026-11-17,19:48Moscow): fresh Q16c qualification RUNNING; near and far clocks PASS.** [Launch receipts, actual resource proof and automatic handoff](evidence/stage17/Q16C-D275-LAUNCH-20261117-01/REPORT.md): near completed19:43:37 and far19:45:38Moscow, each once with unchanged limits. The single Q15-R/W session is next; no terminal Q15 result or Q16c capture was published at this checkpoint. A separate root unit automatically proceeds only after successful retained qualification through exact source/history/platform/resource admission, signed authority, all180 captures, verified restoration and independent analysis. First failure stops without retry. The prospective total ceiling17h27m and original18November13:39Moscow deadline remain fixed; no new window. All360 original schedules,180 real layout queries,708 Q16a and120 Q16b reports remain preserved. Scoped freeze and EXT007/Stage17 exit remain pending; Stage18 is prohibited.

The engineering checkpoints below are historical.

Current implementation checkpoint: ADR-0200 adds caller-owned one-shot shared
coordination/results and exercises the complete R0 session on a mapped
controller stack, mapped runtime objects and both persistent worker stacks.
It also retains native cold TLS payload ranges, owner identity, FS base and
loader generation, rejecting truncated or mismatched observations. Actual TLS
payloads do not describe the entire libc/runtime footprint. Tests inject NUMA
binding and synthetic capture time; no stand qualification follows. Complete
runtime coverage, live control monitoring, publication/watchdog, finite budgets
and qualified diagnostic admission remain open. SSH works through the local VPN
bypass; the refreshed inventory finds the same boot and operational journal
head. This is not a fresh semantic replay. The stand is dedicated to these
experiments. Final precision `delta_star` remains unresolved without blocking
independent engineering or the approved duration study. Stage 17 remains
incomplete; Stage 18 requires the subsequent accepted calibration, pilot and
freeze chain.

Both integrated development suites pass 519/519; all 107 calibration and 44
platform cases pass the four sanitizer configurations. Evidence is retained in
the [local verification record](evidence/stage17/LOCAL-VERIFICATION-EXT007-20261103-01/README.md).

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

ADR-0181 separately retains actual queue-operation outcomes when a clock or
trace failure is discovered after the queue call. Producer/consumer advances
and FULL/empty counts therefore remain available for drain reconciliation,
while the original capture failure and peer cancellation stay mandatory.
Three real-ring regression tests reproduced six missing-count failures
before the fix. The corrected calibration suite passes 28/28 under GCC and
Clang development, and under both compiler ASan/UBSan and TSan matrices.
This does not supply the missing coordinator or qualify a diagnostic release.

ADR-0182 implements time/attempt-bounded quiescent consumer drain and optional
ring reset. It requires observed empty, zero audited occupancy, and exact
pending-event reconciliation; failures retain partial counts and do not
reset. The concurrent capture test now uses this real primitive. The suite
passes all 35 C++ cases, including seven drain cases, under GCC and
Clang/libc++ development, both ASan/UBSan presets, and both TSan presets.
Changed-file clang-tidy and formatting checks pass.

ADR-0183 implements the backend-driven warm-up/start coordinator in
`include/cpu_prefetch/calibration/discovery_session.hpp`. The same two
threads prepare once, capture warm-up, publish independent results, drain
and reset, then enter measurement through a separate barrier. Validation
and drain occur only when both capture workers are quiescent; threads
remain alive across the reset. Both private resets must pass before the
measurement origin is released. Failed starts retain observed clocks
separately from released origins, and post-capture exceptions retain the
worker results. Eleven session tests bring the calibration suite to 46
cases. The real stand backend, consumer integrity observations, placement
verification, outer watchdog, durable raw retention, and exact diagnostic
admission remain open.
All 46 cases pass in both development compilers and both ASan/UBSan and TSan
matrices. [Fresh verification and restored inputs](evidence/stage17/LOCAL-VERIFICATION-EXT007-20261101-01/README.md)
record the exact scope and release limitations.

On 2026-11-01, the previous temporary prefix had disappeared and system
GCC/LLVM/CMake/Git versions had moved outside the accepted ranges. Official
cached package signatures and the frozen libc++/test-source hashes were
verified before restoration to `build/ext007-toolchain-20261101/`. This
recovers accepted compiler/build frontends for local software checks; the
host's glibc 2.44 still prevents claiming full release dependency conformity.
Fresh read-only stand status attempts timed out during SSH banner exchange;
they produced no new journal validation, action, or experiment result.

ADR-0184 repairs the baseline formatting and focused runner checked-access
diagnostics reproduced during that verification. This changes source bytes
bound by prospective v54; its committed record is intentionally preserved
and its author check must fail until a successor binds the repaired source.
The earlier v54 PASS above is historical, not a current source-qualification
claim after this repair. No release or operational authority follows.
The subsequent [2026-11-02 runtime verification](evidence/stage17/LOCAL-VERIFICATION-EXT007-20261102-01/README.md)
restores accepted glibc 2.43 and tool versions in an isolated tree, with no
host-system change. All 20 timing/clock-pair cases pass both compiler
sanitizer matrices. Global formatting and focused strict static checks pass;
the full static check remains pending. Historical source-fixture and external
archive requirements still prevent a full-suite pass. The latest read-only
SSH attempt again times out before login. No stand action was performed.
ADR-0185 supplies a complete pinned historical source fixture for four old
policy-18 regressions. Their original assertions and six preservation/failure cases
pass through the harness, which also checks current immutable records before
replay. This is historical compatibility only; current qualification and the
missing external D-100 archive remain separate requirements.
ADR-0186 adds an explicit hermetic D-100 proposal self-test, retaining all
existing negative cases and adding seven archive-identity mutants plus two
boundary cases. The default integration checker still rejects missing actual
archive/sidecar bytes. The integrated Clang/libc++ CTest suite now passes all
410 entries in the accepted runtime. The historical external artifact is
still absent for its separate integration/action gate; synthetic success
does not supply it or qualify the current policy/release.
ADR-0187 adds a discovery-only consumer helper returning the real event/status
alongside timing and trace validity. The backend can therefore perform the
ordinary immutable-record action even after a failed capture; it must still
retain independent consumer ordinals and reconcile after drain. Four real-ring
cases bring the suite to 50, passing both development compilers and both
compiler sanitizer matrices. The previous full static check passes all 111
units; the added unit passes focused strict analysis. All six required strict
release codegen gates pass with GNU and accepted LLVM disassemblers. These
checks still do not supply the live backend or a source-qualified release.

On 2026-11-02 the owner restored SSH. The retained v5-12 journal hashes match
the preceding audit. Its temporary wrapper disappeared after reboot; using
the retained CLI directly rejects a hardware-prefetch schema identity mismatch.
Fresh replay is pending, and no gate was bypassed or old attempt retried.
The [fresh read-only inventory](evidence/stage17/STAND-AUDIT-CPU-PREFETCH-V5-20261102-01/README.md)
records actual topology/cache and resource observations plus nine journal-file
and six artifact hashes. The latest journal and all six retained artifact
hashes match the earlier audit. Its retained versioned v47 runtime also fails
to import a missing v46 dependency. Preserve this incomplete old context;
qualify a complete new runtime rather than suppressing source/closure gates.

ADR-0188 adds exact-size caller-owned ring storage and checked requirements
derived from the real private types. It rejects invalid size/alignment/overlap
before initialization, preserves caller ownership, and keeps the same member
layout and measured operations. All 67 queue/calibration cases plus queue
stress pass both compiler sanitizer matrices; strict queue codegen and updated
first-party source provenance pass. The live backend must still establish and
verify the mappings. The same provenance review exposes an earlier linked
reset implementation that allocates through audits/temporary vectors. The
logical-reset validator requires zero allocation delta, so that existing
lifecycle issue is now repaired by ADR-0189. Three regressions first observed
eight allocations per successful reset, three on nonempty rejection, and a
corrupted cycle silently normalized. The replacement verifies the frozen
rotation without scratch storage and rejects invalid state before mutation.
Both development compilers pass all 424 CTest entries; supported allocation
counter matrices and all six strict codegen gates pass. Clang TSan retains
functional reset coverage under its existing allocator-hook exclusion. This
closes that reset prerequisite, not live backend integration or qualification.
ADR-0190 adds caller-owned typed storage for the arena's active permutation.
All three storage forms preserve seeded records, lookup, and checksums;
invalid storage is rejected before writing either supplied region. Both
integrated development suites pass 427/427; 14 workload cases pass all four
sanitizer configurations, supported allocation-counter checks and all six
strict codegen gates pass. The live backend must still owner-prepare and
verify these mappings, integrate worker-local trace/observation storage, and
complete diagnostic qualification before any capture.
ADR-0191 adds caller-owned worker trace metadata and sample buffers, rejecting
overlapping regions before preparation. Producer and discovery-consumer
capture accept this storage interface, and prepared-window/validation helpers
use own-worker views rather than copying peer counts during capture. Both
integrated development suites pass 435/435; all 57 calibration cases pass the
four sanitizer configurations, six allocation-hook cases pass their supported
matrices, and all six strict codegen gates pass. Actual owner construction,
mapping/residency, independent event streams, the watchdog/publication path,
and exact diagnostic admission still need live backend integration.
ADR-0192 adds preallocated page-query scratch and an allocation-free Linux
adapter. Geometry/overlap checks precede scratch writes; query failures and
per-page errors remain distinct and stale successes are cleared before every
query. Both integrated development suites pass 442/442; 26 platform cases
pass all four sanitizer configurations, seven allocation-hook cases pass
supported matrices, and all six strict codegen gates pass. Tests use injected
results; no live residency or stand execution is claimed. The backend still
needs its frozen monitoring schedule and retained clock/status snapshots.
ADR-0193 adds joint event/demand capture with the ordinary primary observation
types. The ring exposes both existing observer boundaries without changing
its private algorithm or member layout. Every actual item receives the record
action even after clock/trace failure. Partial actual readings stay separate
from complete primary rows, absent demand clocks remain absent, and a
pre-operation failure does not add a phantom attempt. Both integrated suites
pass 451/451; 65 calibration cases pass all four sanitizer configurations,
eight allocation-hook cases pass supported matrices, focused strict analysis
and all six existing codegen gates pass. The backend still needs caller-owned
primary streams, independent ordinals and exact reconciliation, observed drain
capture, live owner preparation/residency, watchdog/publication/admission, and
qualification of its exact combined clock-boundary sequence before execution.
ADR-0194 adds caller-owned primary stream storage with the existing raw codec,
golden hashes, literal row run IDs and owner preparation. Invalid/overlapping
regions reject before external writes; caller bytes remain untouched until
preparation. Compiler debug evidence independently preserves both stream
object sizes and all prior hot offsets in both supported ABIs. Both integrated
suites pass 456/456; 20 storage cases pass all four sanitizer configurations,
two storage allocation-hook cases pass supported matrices, strict analysis and
all six codegen gates pass. Actual mapped owner construction and residency,
independent ordinals, observed drain rows and exact phase reconciliation,
watchdog/publication/admission and exact-boundary qualification remain open.
ADR-0195 implements the R0 phase composition with independently maintained
logical/accepted/consumed ordinals. Prepared raw readers retain the old codec;
exact prefix/full joins check literal identity, deterministic mapping, ordinals,
within/across-row time order and replayed checksum without allocation. Observed
drain retains real boundary/record facts and requires final integrity before
reset. Invalid primary prefixes are not renumbered or filled from later drain
rows. Both integrated suites pass 471/471; 78 calibration and 21 storage cases
pass all four sanitizer configurations, three storage allocation-hook cases
pass supported matrices, strict focused analysis and six existing codegen
gates pass. This uses software-only preparation, not actual stand placement.
Linux owner construction/binding/monitoring, durable publication, finite outer
watchdog, versioned diagnostic admission/release and fresh dependent/exact-clock
qualification remain required. No diagnostic or formal capture has run.

ADR-0196 supplies explicit Linux preparation for new private owner mappings:
verified page geometry, pre-touch node binding/no-huge request, independent
affinity/CPU/thread/fault observations, owner prefault, lock and one-shot
cleanup with retained results. It does not wrap/erase borrowed stacks or infer
page residency from accepted syscalls. Native mask tests preserve node zero
and the top supported bit. Controller observers now gate each phase before
release, during capture and after both workers stop. Failures retain bounded
drain and independent raw integrity, prohibit warm reset/measurement release,
and cannot become success after a late report. Missing monitoring is explicit.
Both full compiler suites pass 487/487; 37 platform and 83 calibration cases
pass all four sanitizer configurations. Five affected translation units,
global format, provenance and six existing codegen gates pass. These local checks do not qualify
stand placement or the new boundary sequence. Actual mapped object/stack
composition, retained all-page/control monitoring, finite resource controls,
publication/watchdog/admission and fresh qualified release remain open.
See the [bound verification record](evidence/stage17/LOCAL-VERIFICATION-EXT007-20261103-01/README.md).

ADR-0197 implements the retained residency observer behind those hooks.
Declared regions require full before/after coverage and explicit during-range
queries. Status scratch is distinct per snapshot, page addresses remain
observable, and partial queries cannot establish unqueried placement. Raw
return/errno, node/status errors, clock brackets, wait clocks/polls and completion
masks are retained. Late/missed queries and clock failures cannot pass. Both
full compiler suites pass 499/499; 94 calibration and 37 platform cases pass
four sanitizer configurations, four supported storage allocation-hook cases
and focused strict analysis pass. Global format, provenance and six existing
codegen gates pass. This is software/injected-query evidence;
the actual mapped owner/stack provider, complete live controls, approved finite
monitoring/resources, durable publication/watchdog and qualified action remain
required. No stand residency or experimental result is inferred.

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

The 2026-11-03 downstream source audit also confirms that replacing Q16a alone
will not finish the runtime requirements. In
[`stage17_fixed_action.cpp`](../src/runner/stage17_fixed_action.cpp),
`capture_ticketed_service_rate` stops the producer at the fixed duration but
continues incrementing `report.consumed` through drain. `run_artifacts` exports
that total as `consumed_count`; it supplies no separate completion count
restricted to the measurement interval. Preserve the full total for integrity,
but do not use it as fixed-interval throughput. The new service path needs its
explicit interval count and observed boundary evidence before Q16b admission.
`package_capture` currently parses warmup inputs only for `blinded_pilot`, while
`run_artifacts` sets `warmup_reset_verified=true` for nonpilot actions without
such execution. This flag cannot establish Q16b/Q16c warmup. Correct the live
path and version its output/admission contracts before formal data collection;
do not retrofit these meanings onto retained historical outputs.

Before diagnostic or formal stand execution:

1. Complete the already-approved D-178 diagnostic action's exact prospective
   run set, controls, capacities, validity checks and finite budgets. Its 36
   fixed-duration captures can establish the missing common duration. Then
   bind that result and minimum observations in a fresh formal D-037 plan,
   including persistent five-second warmup/drain/reset and fresh IDs/seeds.
   Formal inputs do not have to be invented before their separate discovery
   study. A different scientific method still requires a protocol amendment.
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
That is historical verification before ADR-0184's repairs. Static analysis
then retained the baseline `spin_wait_nanoseconds` exception
diagnostic and the two baseline optional-access diagnostics in
`tests/runner_model_test.cpp`; the affected code is unchanged, and the same
diagnostics exist in the earlier baseline logs. ADR-0184 now repairs those
diagnostics; the pending full static result and other release prerequisites
remain separate gates.

The immutable pre.3 Section 5.4 and D-116 amendment already require exactly
five seconds for pre-freeze formal calibration/pilot warm-up. The external
10 ms draft cannot override that rule. The diagnostic implementation must
prospectively bind its warm-up and retain the same drain, quiescent reset,
persistent mappings, and synchronized measurement-start obligations.
