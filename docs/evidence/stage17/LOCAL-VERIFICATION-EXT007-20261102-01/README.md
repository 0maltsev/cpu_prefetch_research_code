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

The latest read-only SSH attempt to the authorized stand timed out during
banner exchange (exit 255), before any remote command. The last validated
external journal remains the 2026-10-30 v5-12 checkpoint with six resolutions.
Prospective policy v54 is intentionally preserved and stale against the
D-184 runner source. A new policy, qualified release, real backend, complete
capture controls and exact diagnostic authority remain required.
