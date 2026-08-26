# Stage 16 pre-pilot readiness report

Protocol: **`2.0.0-pre.2`**

Bundle profile: **`STAGE16-STAND-BUNDLE-v1`**

Assessment scope: software verification and stand transfer only

## Verdict

- Software/bundle state: **`READY_FOR_STAND_PREFLIGHT`**.
- Pilot state: **`PREPARED_EXTERNAL_INPUTS_REQUIRED_NOT_READY_FOR_STAGE17_PILOT_EXECUTION`**.
- Confirmatory state: **`BLOCKED_BEFORE_CONFIRMATORY_EXECUTION`**.

This verdict authorizes installation verification and read-only inventory on a
candidate stand. It does not authorize privileged mutation, calibration,
pilot, or confirmatory execution. Development-host and synthetic evidence are
correctness evidence only.

## Q14 addendum

Q14/ADR-0044 through ADR-0046 do not change the Stage 16 verdict or its sealed
bundle. The current repository adds v2 affined preparation, qualification and
authority validation, combined-operation codegen evidence, and a separate
pilot-candidate profile. Fresh local Q14 GCC 207/207 and complete Clang
development tests passed; the 44 then-affected runner/lifecycle tests passed
under both compilers' ASan/UBSan and TSan presets. D-047 subsequently fixes the
physical mapping, adds per-owner PRFCHW gating, and passes the strict GCC/Clang
plus GNU/LLVM ten-operation audit and four mutants. The fresh post-D-047 pass
completes 208/208 development tests under each compiler, 208/208 in both
ASan/UBSan matrices, 208/208 under GCC TSan, the applicable 206/206 under
Clang/libc++ TSan, and all 45 runner/lifecycle tests in every sanitizer preset.
The separately sealed pilot-candidate release remains no-authority input to
Q15 preparation. Pilot and confirmatory states remain blocked on operational
and frozen evidence.

## Q15-P0 addendum

Q15-P0 was accepted on 2026-08-24 for repository-local prerequisite closure
only. ADR-0048 removes in-measurement poll-count expiry that could invalidate a
legitimate open-loop gap or drain backlog and moves hang containment to a
future exact external process watchdog. ADR-0049 fixes the Intel family-06
model-55H MSR 0x1A4 H0/H1 mapping in a narrow fake-tested transaction engine.
ADR-0050 fixes the four-role/two-domain authority policy. The complete local
Q15-P0 verification passes 216/216 tests in both development and release
compiler/library matrices, 216/216 in both ASan/UBSan matrices and GCC TSan,
and 214/214 applicable tests in Clang/libc++ TSan. Formatting, full 73-file
static analysis, schemas, protocol hashes, repository policy checks, and every
dual-disassembler generated-code gate pass. Clean revision
`693f00b3878ed027dc09aea7916f149874fb12a1` is now sealed as the
no-authority candidate; archive SHA-256 is
`f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1`,
and its 94-file clean extraction and two nonprivileged self-tests pass. Exact
Q15 tool/authority/command/limit/custody inputs remain open.

The sealed Stage 16 bundle remains `READY_FOR_STAND_PREFLIGHT`; the current
pilot disposition is `PREPARED_EXTERNAL_INPUTS_REQUIRED`, and confirmatory
execution remains `BLOCKED_BEFORE_CONFIRMATORY_EXECUTION`. Q15-P0 did not
authorize stand access, MSR operations, dynamic qualification, accounts,
privilege, calibration, pilot, or confirmation.

## ADR-0104 operational-governance addendum

ADR-0104 does not change the sealed Stage 16 bundle verdict. It replaces the
later open-ended pilot governance chain with one finite successor and one
external-input checklist. The operational record is `PREPARED`; positive and
negative local tests prove only the transition model. D-099 through D-108 are
hash-preserved, the D-104 self-test is hermetic, and a real qualification
archive is an explicit integration/action input. No stand observation was made
for this addendum. The ten unresolved checklist entries are the authoritative
pilot blockers. Stage 18 remains blocked on the unchanged imported sealing and
access chronology plus all pilot-derived freezes.

## Requirement-by-requirement verification matrix

| Requirement | Verification seam | Fresh Stage 16 evidence | State |
|---|---|---|---|
| Protocol authority and immutable hashes | Dual-snapshot manifest, authoritative hashes, Draft 2020-12 schemas | 36 artifact sizes/hashes, eight authoritative hashes, 14 imported plus nine implementation schemas, 67 fixtures, and three JCS-I64 cases pass | `PASS` |
| Primary and secondary clean builds | GCC/libstdc++ and Clang/libc++ clean preset builds | Clean development and release configure/build/test: 187/187 in each of four matrices | `PASS` |
| Unit/property/integration coverage | All CTest targets and deterministic RapidCheck seed | GCC and Clang development matrices each pass 187/187 tests | `PASS` |
| Schedule determinism | Accepted direct/integrated goldens and namespace rules | `schedule-check` passes eight Python tests; schedule-labelled CTest and all four recorded hashes pass | `PASS` |
| Queue correctness | FIFO/refinement/model/phase/stress/provenance | Full suites, direct stress, two provenance records, and four-operation dual-disassembler/mutant audit pass | `PASS` |
| Timing boundaries | Fake-clock equations, real-reader smoke and release assembly rules | Full timing suite and 11-operation/six-source-mutant/three-machine-mutant dual-disassembler audit pass | `PASS_SOFTWARE`; stand qualification open |
| Workload/package operations | Layout/checksum/target/no-allocation and release assembly | Full suite and six-operation component audit pass; D-047 strict combined audit fixes exact `PREFETCHW`/`PREFETCHT0` vectors under both compilers/disassemblers | `PASS_SOFTWARE`; dynamic stand capability open |
| Platform software | Inventory/capability/request/apply/readback/restoration fakes | Full platform suite passes; candidate-stand bundle/internal/self-tests and nonprivileged inventory pass, observing two packages/two NUMA nodes | `PASS_SOFTWARE_AND_INVENTORY`; `BLOCKED_BEFORE_PILOT` on pair/control qualification |
| Lifecycle | Every legal/illegal transition, failure phase and concurrency path | Full suite and focused partial-failure/no-retry flow pass in normal and sanitizer matrices | `PASS_SOFTWARE` |
| Storage | Codec/boundary/overflow/crash/recovery/no-allocation/large stream | Full suites, two-append-body dual-disassembler audit, and 200,000-row synthetic smoke pass | `PASS_SOFTWARE`; operational domains/capacity open |
| Reconciliation and invalidity | Exact join and all registered mismatch/failure categories | Full unit/property/schema matrix and focused first/internal/last-loss rejection pass | `PASS_SOFTWARE` |
| Calibration framework | Exact synthetic estimators, records and forbidden access | `calibration-check` and full CTest matrices pass using synthetic evidence only | `PASS_SOFTWARE`; stand values open |
| Full Stage A plan | Exact synthetic 180-cell product, roles and replacements | Exact product/seed-sharing and complete-replacement tests pass without execution | `PASS_SOFTWARE` |
| Sealing and analysis | Synthetic access chronology, H1/H2/H3 known answers | `analysis-check`, `orchestration-check`, deterministic known-shift and seal chronology pass | `PASS_SOFTWARE` |
| Synthetic end-to-end dispositions | success, valid `FULL`, low `N_eff`, partial failure, invalid join, replacement | Focused lifecycle/storage/reconciliation/analysis flows all pass | `PASS` |
| Sanitizers | ASan/UBSan and applicable TSan in both toolchain matrices | GCC ASan/UBSan 187/187, GCC TSan 187/187, Clang ASan/UBSan 187/187, Clang TSan 185/185 | `PASS`; documented two-test Clang TSan exclusion remains |
| Formatting/static analysis | Full repository C++ inventory | `format-check` and full `static-analysis` pass after the preflight defects below were fixed | `PASS` |
| Timed-path allowlist | Source review plus queue/workload/timing/storage and combined-runner generated code | Component reports pass; D-047's ten-shape combined report passes exact source/site/count and GNU/LLVM instruction-vector checks plus four mutants | `PASS_SOFTWARE`; dynamic stand qualification remains `BLOCKED_BEFORE_PILOT` |
| Release/bundle reproducibility | Release policy, metadata, SBOM, internal/external hashes | Unsafe/native flags rejected; CPack, two identical bundle builds, clean extraction, internal verification, smoke and preflight self-tests pass | `PASS` |

## Fresh build and test record

The clean verification used commit `b68979d6b38dffe62dcfafc8b8227a85dc713207`
plus the Stage 16 working-tree source captured by the bundle. GCC 16.1.1 with
libstdc++ and Clang 22.1.6 with libc++ each passed 187/187 tests in development
and release builds. GCC and Clang ASan/UBSan passed 187/187; GCC TSan passed
187/187; Clang TSan passed its applicable 185/185 set. The two global
operator-new no-allocation-hook executables remain intentionally excluded only
from Clang TSan because that runtime defines conflicting allocation
interceptors; they pass in both development, both ASan/UBSan, and GCC TSan
matrices. ASan presets intentionally set `detect_leaks=0` under the managed
ptrace boundary and make no LeakSanitizer claim.

Release-policy inspection passed 64 compile commands and found no
`-march=native`, `-mtune=native`, `-Ofast`, or `-ffast-math`. Protocol, schema,
canonical, dependency/license, pinned-CI, document-link, format, static-analysis,
queue-provenance, schedule, calibration, orchestration, reconciliation, and
analysis checks all pass. These are software-correctness results, not platform
or performance observations.

## Timed-path audit

Source review separates setup/finalization code that legitimately allocates,
parses JSON, or uses the filesystem from the concrete queue/package/capture and
private-stream append bodies. The reviewed hot component bodies contain no
filesystem I/O, console logging, compression, dynamic parsing, analysis,
blocking wait, hidden queue retry, or dynamic growth. Preparation-time arena,
queue, and stream allocation remains outside measurement. The bounded writer
has a sticky fail-closed overflow result.

GNU Binutils 2.46 and LLVM 22.1.6 independently pass the queue, workload,
timing, and storage reports. Those reports cover four queue operations, six
package/workload operations, 11 timestamp operations, and two private append
bodies, and reject their deliberate call/syscall/fence/clock/boundary mutants.
Q14 later adds affined owner preparation and a ten-shape combined operation
call-graph audit. D-047 replaces the unresolved marker with the exact physical
emitter. Both accepted compilers and disassemblers require the registered
empty/`PREFETCHW`/`PREFETCHT0` vectors and reject wrong-write, wrong-read,
duplicate-read, and forbidden-work mutants. This is instruction-presence and
ordering evidence only, not platform-performance evidence.

## Defects fixed during independent verification

- String literals supplied to the local JSON value type could select its
  boolean constructor in the new preflight emitter. Every affected field now
  constructs an explicit `std::string`, and inventory output is canonical
  string-valued JSON.
- The new preflight `main` could let an inventory or JSON exception escape.
  The executable now reports a stable fail-closed error and returns nonzero;
  the fix passes targeted tests in every development, release, and sanitizer
  preset.
- The first repeat bundle proof found that `ldd` embeds per-process load
  addresses in its otherwise stable dependency report. The generator now
  removes only those addresses while retaining every resolved library identity;
  two independent complete bundle builds then produced identical outer bytes.

## Known preflight-versus-pilot boundary

The repository has no authorized production measurement execution command. The
generic lifecycle, statically bound capture backend, queues, workload packages,
timing boundaries, and bounded storage are independently implemented and
tested. Q13/ADR-0043 selects one `PAUSE`, static pair/profile identities, and a
ticket-gated five-specialization entry seam. Q14 adds fake-tested affinity/
readback, owner first touch, qualification records, and combined generated
code. D-047 fixes and strictly audits the physical mapping. Exact watchdog
values and dynamic stand evidence do not exist. The immutable Stage 16 bundle
still contains only smoke and read-only preflight executables; the separate
candidate profile carries no execution authority.

## Candidate-stand inventory evidence

The finalized preflight bundle was transferred to candidate host
`xeon-cpu-fetch`. Its external SHA-256, complete 72-file internal inventory,
smoke executable, and preflight self-test passed. The internal verifier,
executables, and collector ran as UID/GID 65534 (`nobody:nogroup`); root handled
only transfer, extraction, and output sealing. No platform control or
measurement path ran.

Snapshot `STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-01`, captured at
`2026-08-22T10:33:20Z`, has SHA-256
`f3bb301c77918c0287c8a287e3915f5d68929684eece660464c69f62770ac94b`.
It observes an Intel Xeon Gold 6230R system with two packages, two NUMA nodes,
52 physical cores, and 104 logical CPUs. It remains
`INVENTORY_ONLY_NOT_QUALIFIED`: detailed sibling/cache topology, explicit
non-SMT near/far worker pairs, and every dynamic/readback gate remain open.

The first sidecar publication failed after collection because the checksum
command used the wrong working directory. The immutable inventory was not
rerun or changed. The empty sidecar and failure record are retained, while the
separately named recovered sidecar verifies locally and remotely. See the
[evidence record](evidence/stage16/STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-01/README.md).

Clean revision `1b0a7f54db7e1ff699331e9ae05a97f409f01ad4` was then rebuilt
and independently reproduced. Its clean bundle has SHA-256
`e8eb9150d252d38f72b56884b0bcb5026480aee00b969c736fdc124783cb6eac`.
The stand verified its external and internal hashes and ran both
nonprivileged self-tests. Clean inventory
[`STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02`](evidence/stage16/STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02/README.md)
binds the same count-level candidate facts to that revision.

The separate hashed
[topology set](evidence/stage16/STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01/README.md)
proves that `(0,1)` is a statically eligible near candidate and `(0,26)` is a
statically eligible far candidate. Q13 later selects them, but neither is
dynamically qualified. The hashed
[storage set](evidence/stage16/STAND-STORAGE-XEON-CPU-FETCH-20260822-01/README.md)
observes only one suitable mounted durable namespace, `/dev/md3`. Its RAID1
members are not separate artifact-copy domains under D-020. The
[Stage 17 entry bundle](STAGE17_ENTRY_DECISION_BUNDLE.md) is accepted for
implementation only and grants no execution authority.

The [finite Stage 17 operational successor](STAGE17_OPERATIONAL_AUTHORIZATION.md)
is now the authoritative pilot-admission path. It retains the earlier Q14/Q15
software evidence without treating those records as execution authority. The
current state is `PREPARED`; exact preflight, qualification, calibration,
storage, plan, release, and phase-authorization evidence remains absent.

## Mandatory evidence remaining before pilot

- dynamic qualification of the Q13-selected near/far non-SMT CPU pairs;
- runtime atomic/layout probes on the selected release and pairs;
- named least-privilege platform authority, exact whitelist, independent
  readback/probes, and successful restoration exercise;
- release-generated-code-qualified processor relax, accepted physical software-
  prefetch mapping with strict combined audit, and independently documented
  H0/H1 hardware-prefetch control mapping;
- full selected-pair clock qualification and before-block repetition;
- producer-home/worker-local before/during/after address-residency proof;
- a second real independent durable storage domain, permissions/custody, exact
  capacity/reserve proof, and crash/recovery/readback exercise;
- authorized prospective calibration/pilot plans, durations, counts,
  namespaces, seeds, budgets, environmental limits, and stand-hours; and
- a clean exact `STAGE17-PILOT-CANDIDATE-BUNDLE-v1` whose strict reports all
  pass and whose manifest still grants no authority.

## Additional evidence remaining before confirmatory execution

All pilot-derived and owner-supplied freeze inputs remain required, including
`delta_star`, `mu_ref`, final loads/capacities/`d2`, horizon/warm-up/recovery,
matrix feasibility, `B_boot`, precision curves and repetition counts, master
and derived seeds, exact schedules/block plans, replacement budget/authority,
technical custody, unseal/signature policy, and final stand budget.
