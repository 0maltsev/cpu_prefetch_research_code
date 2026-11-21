# D320: actual S180 machine-code audit and clean release verification

Accepted engineering implementation under D310 S180. Date:22November2026
(Moscow). Add an explicit generated-code gate for the new native pilot and
preserve the existing formal audit. No scientific method, capture, protocol,
deadline, calibration artifact, queue provenance or prior rule file is changed.

## Confirmed classifier gap

The original `check_formal_codegen.py` predates `PilotRuntimePolicy`. Its worker
classifier interprets the new pilot instantiations as formal service workers.
The optimized release contains20 actual pilot roots and20 distinct service
roots that consequently share legacy audit identities. The original audit
rejects the actual new runner with `duplicate formal worker identity`.

This failure must not be hidden by removing pilot code, accepting duplicates,
auditing a replacement probe or changing the historical formal report contract.
`check_s180_codegen.py` is an additive successor. It positively identifies the
20 actual pilot roots, keeps them distinct, audits their native reference paths
and applies the original active-region/closure/raw-clock/exact-prefetch rules.
The complete42 formal workers are audited using the original functions with
only those positively identified pilot roots excluded from root classification.
Other callees remain present for closure/reference checks. Missing, duplicate,
unknown, unreferenced or unclassified worker shapes still fail closed.

The producer/consumer vectors are exact counts for all five packages and both
registered emitter mappings. The gate checks actual `run_native_pilot_capture`
reference paths, primary writers, CLOCK_MONOTONIC_RAW argument definitions,
active/cold cuts, bounded closure calls and registered worker-control atomics.
Its scope matches the original formal audit: separate queue/timing gates remain
mandatory, and it does not independently prove all timestamp dataflow or actual
runtime platform placement. No empirical performance claim follows from it.

## Actual mutants and retained report bindings

The original12 formal machine-instruction mutants remain mandatory. An internal
copy of those same tests specializes the selected roots to pilot R0/T0 producer
and pilot R1/retaining producer. It rejects allocation, indirect calls, syscalls,
unregistered atomics, hidden hot TLS, capture hidden beyond a cold cut or inside
TLS/loader callbacks, wrong clock domain, missing workers, wrong prefetch intent
and duplicate prefetches. These mutate decoded actual binary instructions, not
replacement benchmark source. Both GNU and LLVM independently perform both
12-case families:48 rejected mutants in total.

The separate S180/1 report binds the exact actual binary, all71 source-evidence
files and the three audit rule files. It retains the complete formally validated
42-worker report inside its new scope. It does not relabel a pilot-only result
as a legacy42-worker report. Both audits consume the same full disassembly for
each tool. GNU/LLVM must agree on worker/active/cold addresses and exact prefetch
vectors/witnesses. Missing tools block; LLVM22 is required. Retained-report
validation repeats identity, completeness, hash, witness and agreement checks.

`s180-codegen-check` invokes the new gate on the actual built runner and runs
the retained-report tests. The legacy formal target and legacy bundle/profile
contracts remain unchanged. The future qualified S180 package must explicitly
consume this separately scoped audit; the old pilot-candidate profile cannot
become launch-ready merely because this new report passes.

## Clean native revision and toolchain diagnosis

The candidate is built in an isolated clean worktree of
`34247cedab4abe4b44732daae8fdac1700eccffd`. Its runtime identity reports
`source_dirty=false`; the actual worker is6151832bytes, SHA256
`7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc`.
The new codegen changes are Python/CMake only. All71 native/source-evidence
members match the isolated revision byte for byte.

The initial build used the smaller provisioned compiler prefix. Although its
GCC binary matches the accepted16.1.1 compiler, missing full runtime inputs let
the driver use host startup objects and binutils2.47. Queue operation bodies
matched, but strict whole-probe provenance failed. Merely pinning objdump/ld did
not restore the complete probe hash. Diagnostics distinguish the different
host versus full-runtime Scrt1/crti/crtn inputs; no provenance record was edited.

Reconfiguring with the existing full accepted runtime/compiler prefix resolves
those startup/link inputs. CMake's compiler-change cache reset required explicit
reconfiguration with the original dependency revision and Release settings.
The pinned old library directory also cannot be used wholesale by the newer
host Python: its libm lacks GLIBC_2.44 required by that interpreter extension.
A build-local library directory supplies only pinned binutils libraries, along
with the existing provisioned compiler libraries, leaving the host Python's
glibc/libm coherent. Versions and actual files remain explicitly recorded.

The corrected complete rebuild reproduces the immutable queue-probe SHA256
`84551849f1244cd0c7e9d1b05fbb9f55e74e4ab6fa7d6058fdb6fa97baec840c`
and passes the original queue/workload/timing/storage/relax/combined/Q15-runtime/
discovery gates. Failed build/check reports and the correction are retained;
they are not scientific failures, replacement measurements or deleted evidence.

## Software IPC environment

The optimized41-entry S180 regression initially passed36 entries. Five tests
failed at the managed Unix credential boundary; an independent local probe
confirms SO_PEERCRED returns EPERM there. The same unchanged release's six
channel/entry IPC cases pass outside that boundary, including all five failed
cases and the negative-ACK test. No production guard was bypassed or weakened.
The original failure log and final targeted proof both remain visible.

A pre-commit whitespace check caught trailing spaces in generated failure logs
and a surplus rule-file EOF newline. Original log hashes and exact first rule
bytes are retained, with an unchanged-AST record. A fresh complete audit and its
six report tests pass against the final rule bytes; native bytes are unchanged.

The six retained-report tests pass against the actual dual-disassembler report,
and an explicit missing-tools invocation blocks with exit3. This is software
verification only. D318's relevant native sanitizer evidence remains preserved;
this Python/CMake audit change does not introduce a new native behavior.

## Remaining operational gates

The native release has generated-code evidence, not stand qualification or
execution authority. The qualified scoped semantic producers/journal replay,
parent/profile and one-attempt/archive orchestration, actual original sources/
namespace provenance, complete time/storage/recovery budget, scoped EXT008–010,
actual qualification/compatibility and one pilot plus independent validation/
restoration/exit remain. No operational window has started. A separate read-only
SSH process/storage/memory observation is not full quiescence or EXT009 admission.
Completed calibration remains preserved; Stage17 is incomplete and Stage18 deferred.
