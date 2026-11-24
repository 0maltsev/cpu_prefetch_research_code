# D338: bind actual T0-only software-prefetch code generation

Accepted engineering correction within D310's qualification preparation. ADR0175
already approves the stand's `X86-64-PREFETCHT0-ONLY-v1` mapping. No mapping,
scientific method, native measurement instruction, count or timing limit changes.
The frozen34247ce measurement worker and original source tree stay unchanged.

The existing standalone mapping probe/checker instantiates only the original
`X86RetainingPrefetchEmitter`. Its passing report names
`X86-64-PREFETCHW-PREFETCHT0-v1`; it cannot establish the T0-only mapping's
GCC/Clang codegen flags for qualification-evidence/3. D320 independently covers
actual GCC pilot/formal call paths, but does not supply this missing standalone
two-compiler mapping proof. Never copy passing flags across different mappings.

Extend the existing probe with three explicitly named sites instantiating the
actual accepted `X86PrefetchT0OnlyEmitter`: ring producer, ring consumer and
linked successor. Preserve the original sites, default CLI mapping and audit.
Select the separately named T0-only check explicitly; its three sites must each
contain exactly one PREFETCHT0 and no other prefetch mnemonic. GNU and accepted
LLVM22 must independently pass. Five actual machine mutants cover wrong intent
at all three roles, duplicated hints and an absent hint; each must be rejected
by the positive T0 rule under both disassemblers. An accidentally fixed mutant
fails the negative-check family.

The T0 report binds the actual probe/mutant bytes, checker and emitter/probe
source hashes. Retained-report verification checks both tool/site/mutant
families and physical file/source identities. Its caller must independently
authenticate report custody, compiler/build provenance and qualified package;
this checker does not infer compiler identity from a report label or prove full
native call-graph coverage. Both GCC16 and Clang22 Release builds are required
to establish both compiler-axis flags. Their actual build metadata, compile
commands, compiler observations and reports must be retained. The measured
emitter header must match the frozen measurement source exactly.

The header-only probe needs no runner-library linkage. Remove that unnecessary
dependency and retain its actual source include path and project warnings/
sanitizers. This prevents the probe audit from rebuilding the measurement
implementation. Its default main preserves original calls. The separate
`--t0-only-software-self-test` branch exercises only the T0 sites under GCC and
Clang ASan/UBSan. Never execute instruction mutants. These are software checks,
not PMU/stand measurements, eligibility or a pilot window.

Missing tools remain blocked with exit3; wrong LLVM, missing roles, wrong intent,
duplicates, absent hints and drifted source/binary/rule bindings fail. Original
default-report mapping and original two-mutant checks are preserved. Targeted
tests cover both scopes; the original and new targets must pass for both
compilers. Existing D320 full native proof is preserved separately.

This closes a qualification-codegen prerequisite. Complete EXT008 semantic
facts/replay, actual qualified operator/profile, calibration compatibility,
independent pilot validator and exact whole ETA/admission remain required.
No stand preparation, qualification, source generation or operational window
starts through this change. Evidence: [report](../evidence/stage17/PILOT-D338-T0-CODEGEN-20261123-01/REPORT.md).
