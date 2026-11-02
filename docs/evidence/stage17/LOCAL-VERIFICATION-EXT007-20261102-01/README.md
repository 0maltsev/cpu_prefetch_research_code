# EXT007 release-prerequisite verification, 2026-11-02

Local software evidence only. No stand capture, external resolution, scientific
parameter freeze, release qualification, or execution authority follows.
The date is the workspace's Moscow date; runtime probes occurred on
2026-11-01 UTC.

The [runtime input record](runtime-restoration.json) identifies 116 cached
package inputs, their signatures, hashes, licenses, and the provisioning and
launcher hashes. Every signature was verified before extraction. The isolated
tree is `build/ext007-runtime-20261101/root`; the host system was not changed.
Unlike the earlier frontend-only recovery, this runtime reports glibc 2.43,
GCC 16.1.1, LLVM 22.1.6, CMake 4.3.3, Git 2.54.0, and Python 3.14.5.
The runtime uses user/PID namespaces and read-only runtime mounts. Network
restrictions are inherited; no network namespace isolation is claimed.
Configure and build fetch no inputs. Frozen GoogleTest/RapidCheck sources
from the preceding restoration were rebuilt against this runtime.

Run a recorded local command through:

```sh
python3 build/ext007-runtime-20261101/run.py -- command arguments
```

Fresh development directories are `build/accepted-dev-gcc` and
`build/accepted-dev-clang-libcxx`. Both full builds completed. They use the
isolated compiler and `CMAKE_SYSROOT` pointing to that runtime, rather than
linking against the newer host glibc. The targeted platform (20), timing (18),
and clock-pair (2) tests pass after the D-184 repairs. The clock tool's
`--self-test` passes with device not opened, clock not read, threads not pinned,
and authority `NONE`.

All 18 timing and two clock-pair cases also pass in each fresh isolated
`build/accepted-{asan-ubsan-gcc,tsan-gcc,asan-ubsan-clang-libcxx,tsan-clang-libcxx}`
directory. The preceding focused runner/Q15 repairs passed 29 + 12 tests in
both compiler sanitizer matrices. Global formatting and focused strict
clang-tidy checks pass. The full static check remains in progress at this
checkpoint; it is not represented as a pass.

The first full GCC CTest run passed 398/408. Adding the missing signed
OpenSSH and zsh runtime prerequisites repaired five cases: both authorization
checks and all three SSH/preflight lifecycle checks pass on rerun. Four
legacy policy/journal checks fail against the current source because their
historical schema pins differ. Their unchanged checks pass against complete
Git snapshot `05035cec1d1c1c88a08e9012996e5a6e4ccfd2a5`; this does not make
current policy v54 qualified. The D-100 decision check still requires its
historical external archive and sidecar. These remaining failures are retained,
not waived or reported as a passing full suite.

ADR-0185 subsequently integrates those four historical tests through
`tools/check_stage17_historical_fixture.py`, retaining their original CTest
assertions and checking current preserved inputs before replay. Six additional
cases reject changed, missing, or symlinked current evidence and failed-child
success output. All five CTest entries pass in the isolated runtime:

```sh
python3 build/ext007-runtime-20261101/run.py -- ctest \
  --test-dir build/ext007-historical-fixture-check --output-on-failure \
  -R '^runner.stage17_(operational_successor|state_journal|external_journal_preflight|external_journal_preflight_v2|historical_fixture_preservation)$'
```

This repairs the four fixture-context failures; a complete current full-suite
pass is still not claimed, and the exact external D-100 archive remains absent.

ADR-0186 subsequently separates D-100's hermetic proposal self-test from its
default external archive integration check, following the existing external
contract. The self-test passes all nineteen negative cases without accessing
the external release bytes; two boundary regressions pass. The default checker
still fails (exit 1) on the missing exact archive and sidecar. No missing byte
is fabricated or waived.

After both fixture repairs, the integrated Clang/libc++ build and full CTest
suite pass **410/410**, exit 0, in the isolated accepted runtime. Commands:

```sh
python3 build/ext007-runtime-20261101/run.py -- cmake \
  --build build/accepted-dev-clang-libcxx -j3
python3 build/ext007-runtime-20261101/run.py -- ctest \
  --test-dir build/accepted-dev-clang-libcxx --output-on-failure -j2
```

The full-suite result supersedes the earlier local CTest failures above. It
does not claim the separate external archive integration passed, replace
current policy checks, or authorize measurement. Full static analysis remains
in progress and strict release code-generation/package checks remain required.

Subsequent completion: the original full static check passes all 111 input
translation units, exit 0. ADR-0187 adds one consumer unit/header; its focused
strict clang-tidy check and current global format target pass. The calibration
suite now passes 50/50 in both development compilers and all four compiler
sanitizer configurations. This is targeted verification after the preceding
410-entry full suite, not a claim that a 414-entry full suite was run.

All six strict release codegen checks pass on clean source `6232fee`: queue,
workload, timing, storage, runner relax, and runner combined. Each report uses
both GNU Binutils 2.46.0 and LLVM 22.1.6 and retains its required mutants.
The reports predate ADR-0187's additive helper, which is not yet integrated
into a live worker. [The compact result record](consumer-and-release-checks.json)
records report/source hashes and the exact scope. A prospective policy and
qualified executable remain outstanding.

The owner restored SSH on 2026-11-02. Fresh read-only inspection confirms the
retained journal hashes match the older audit, including record 000008.
The temporary wrapper is absent after reboot; the retained CLI rejects schema
identity drift. That rejection is retained without bypass; a fresh validated
operational state is not claimed. No experiment or stand mutation occurred.

ADR-0188 adds the caller-owned ring storage interface. Its final integrated
GCC CTest run passes **419/419**, exit 0. The queue (17) and calibration (50)
cases plus queue stress pass all four compiler sanitizer configurations.
Development Clang also passes those suites/stress and six RapidCheck properties
with 100 cases each. The five new external-storage cases pass with nonzero
sentinels that expose writes during rejected construction. Global formatting,
focused strict static analysis, queue source provenance, and all six strict
release codegen gates pass. The queue probe binary and each operation body
under both disassemblers are unchanged from the preceding recorded probe.
[external-ring-checks.json](external-ring-checks.json) binds the source and
result scope. This does not close the separate linked-reset allocation blocker,
complete a backend, qualify a release, or admit experimental evidence.

ADR-0189 subsequently repairs that linked-reset allocation. The
[before-fix record](linked-reset-before-fix.json) and
[actual test output](linked-reset-before-fix.txt) retain three failing cases:
eight allocations on each successful reset, three on nonempty rejection, and
silent normalization of an incorrect frozen node cycle. The final tests also
cover every sentinel/cursor combination for capacities one and eight.

Both integrated GCC and Clang/libc++ CTest suites now pass **424/424**, exit 0.
Five allocation-hook workload cases and 18 queue cases plus queue stress pass
GCC ASan/UBSan, GCC TSan, and Clang/libc++ ASan/UBSan. The existing CMake policy
excludes global-new hooks under Clang TSan; its 18 functional queue cases,
including reset/corruption coverage, and queue stress pass. No allocation delta
is claimed for that excluded configuration. Global formatting, focused strict
analysis, source provenance, and all six strict codegen gates pass. The measured
queue probe binary remains unchanged. [The result record](linked-reset-checks.json)
binds the final source and verification scope. This remains local software
evidence; no new stand capture, operational resolution, or execution authority
is claimed.

An isolated clean checkout of historical commit
`34da95d002e912069c959bfef8e88a23b4880cea` rebuilt the old Q15 bundle with
its original source path. Its collector binary exactly matches recorded SHA-256
`4716e1dfc2e65fd61dce1ea54a70fd876a0b4322b69d9ad1fde5c67a65c48a57`.
However, the rebuilt archive SHA-256 is
`3209ecc36b4d05eccc3a6e7bd4c3f64a7d813b965d6b5a6eb0d11552e07171ac`,
not the accepted `f45d25f4...` archive. It remains an unaccepted reproduction
under `build/ext007-d100-repro/`; no expected input was overwritten. The
collector was not run. An exact custody copy is still needed for that legacy
integration check.

Earlier read-only SSH attempts to the authorized stand timed out during
banner exchange (exit 255), before any remote command. The subsequent fresh
audit above records the restored connection and retained-runtime failures.
The last validated
external journal remains the 2026-10-30 v5-12 checkpoint with six resolutions.
Prospective policy v54 is intentionally preserved and stale against the
D-184 runner source. A new policy, qualified release, real backend, complete
capture controls and exact diagnostic authority remain required.

ADR-0190 supplies caller-owned active event-order storage for later producer
mapping preparation. Both integrated GCC and Clang/libc++ suites pass
**427/427**, exit 0. All 14 workload cases pass GCC and Clang/libc++
ASan/UBSan and TSan; the five allocation-hook cases pass the supported
configurations (the existing Clang TSan exclusion remains). Global formatting,
focused strict analysis, source provenance, and all six strict dual-disassembler
codegen gates pass. [external-order-checks.json](external-order-checks.json)
binds the source and result scope. No residency or release authority follows,
and no stand capture occurred.

ADR-0191 supplies caller-owned demand/issue buffers and separate worker-local
trace state. Both integrated development suites pass **435/435**, exit 0.
All 57 calibration cases pass both development compilers and all four
sanitizer configurations. Six allocation-hook cases, including construction,
preparation and bounded recording of caller-owned traces, pass development
GCC/Clang, GCC ASan/UBSan and TSan, and Clang ASan/UBSan; Clang TSan retains
the existing hook exclusion and passes functional/concurrent trace coverage.
Global formatting, strict focused analysis of five affected translation units,
source provenance and all six strict codegen gates pass.
[caller-trace-checks.json](caller-trace-checks.json) binds the source and scope.
These checks do not establish actual placement, qualify a release, authorize
execution, or supply an empirical observation.
