# Stage 16 pre-pilot readiness report

Protocol: **`2.0.0-pre.2`**

Bundle profile: **`STAGE16-STAND-BUNDLE-v1`**

Assessment scope: software verification and stand transfer only

## Verdict

- Software/bundle state: **`READY_FOR_STAND_PREFLIGHT`**.
- Pilot state: **`BLOCKED_BEFORE_PILOT`**.
- Confirmatory state: **`BLOCKED_BEFORE_CONFIRMATORY_EXECUTION`**.

This verdict authorizes installation verification and read-only inventory on a
candidate stand. It does not authorize privileged mutation, calibration,
pilot, or confirmatory execution. Development-host and synthetic evidence are
correctness evidence only.

## Requirement-by-requirement verification matrix

| Requirement | Verification seam | Fresh Stage 16 evidence | State |
|---|---|---|---|
| Protocol authority and immutable hashes | Dual-snapshot manifest, authoritative hashes, Draft 2020-12 schemas | 36 artifact sizes/hashes, eight authoritative hashes, 14 imported plus nine implementation schemas, 67 fixtures, and three JCS-I64 cases pass | `PASS` |
| Primary and secondary clean builds | GCC/libstdc++ and Clang/libc++ clean preset builds | Clean development and release configure/build/test: 187/187 in each of four matrices | `PASS` |
| Unit/property/integration coverage | All CTest targets and deterministic RapidCheck seed | GCC and Clang development matrices each pass 187/187 tests | `PASS` |
| Schedule determinism | Accepted direct/integrated goldens and namespace rules | `schedule-check` passes eight Python tests; schedule-labelled CTest and all four recorded hashes pass | `PASS` |
| Queue correctness | FIFO/refinement/model/phase/stress/provenance | Full suites, direct stress, two provenance records, and four-operation dual-disassembler/mutant audit pass | `PASS` |
| Timing boundaries | Fake-clock equations, real-reader smoke and release assembly rules | Full timing suite and 11-operation/six-source-mutant/three-machine-mutant dual-disassembler audit pass | `PASS_SOFTWARE`; stand qualification open |
| Workload/package operations | Layout/checksum/target/no-allocation and release assembly | Full suite and six-operation dual-disassembler/mutant audit pass | `PASS_SOFTWARE`; platform encodings open |
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
| Timed-path allowlist | Source review plus queue/workload/timing/storage generated code | All four GNU/LLVM reports and negative mutants pass; no integrated production worker exists | `PASS_COMPONENTS`; `BLOCKED_BEFORE_PILOT` for final worker audit |
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
This evidence is component-level. The absent production measurement executable
means there is no final combined worker call graph or assembly to approve; that
is a mandatory pilot blocker rather than an inferred pass.

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

The repository has no authorized production measurement executable. The
generic lifecycle, statically bound capture backend, queues, workload packages,
timing boundaries, and bounded storage are independently implemented and
tested, but final platform relax/prefetch mappings, concrete reset/package
specializations, watchdog values, and combined-worker generated code do not
exist as a frozen release. The bundle therefore contains only smoke and
read-only preflight executables.

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
statically eligible far candidate; neither is selected or dynamically
qualified. The hashed
[storage set](evidence/stage16/STAND-STORAGE-XEON-CPU-FETCH-20260822-01/README.md)
observes only one suitable mounted durable namespace, `/dev/md3`. Its RAID1
members are not separate artifact-copy domains under D-020. The
[Stage 17 entry bundle](STAGE17_ENTRY_DECISION_BUNDLE.md) awaits Q13 review and
grants no execution authority.

## Mandatory evidence remaining before pilot

- owner acceptance and dynamic qualification of the proposed near/far non-SMT
  CPU pairs;
- runtime atomic/layout probes on the selected release and pairs;
- named least-privilege platform authority, exact whitelist, independent
  readback/probes, and successful restoration exercise;
- accepted/generated-code-qualified processor relax plus an independently
  documented hardware-prefetch instruction/control mapping;
- full selected-pair clock qualification and before-block repetition;
- producer-home/worker-local before/during/after address-residency proof;
- a second real independent durable storage domain, permissions/custody, exact
  capacity/reserve proof, and crash/recovery/readback exercise;
- authorized prospective calibration/pilot plans, durations, counts,
  namespaces, seeds, budgets, environmental limits, and stand-hours; and
- the production measurement executable and complete release-specific
  combined-worker source/assembly audit.

## Additional evidence remaining before confirmatory execution

All pilot-derived and owner-supplied freeze inputs remain required, including
`delta_star`, `mu_ref`, final loads/capacities/`d2`, horizon/warm-up/recovery,
matrix feasibility, `B_boot`, precision curves and repetition counts, master
and derived seeds, exact schedules/block plans, replacement budget/authority,
technical custody, unseal/signature policy, and final stand budget.
