# D320: clean native release and actual pilot codegen

The clean native candidate34247ce now has generated-code evidence. A separate
S180 audit verifies all20 actual pilot workers and preserves all42 formal worker
audits under GNU2.46.0 and LLVM22.1.6. Each tool rejects12 pilot and12 formal
machine-instruction mutants:48 rejected mutants across both tools. Six fresh
retained-report tests pass. Missing tools explicitly block with exit3.

[D320 decision](../../../decisions/0320-s180-native-codegen-and-clean-release.md)
describes the audit boundary, corrected build environment and remaining gates.

The actual release worker is6151832bytes, SHA256
`7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc`,
compiled from clean revision`34247cedab4abe4b44732daae8fdac1700eccffd`.
All71 source-evidence files match that isolated revision. Audit changes are
Python/CMake only; no native measurement behavior changes in this step.

## Confirmed gaps and fixes

The original formal classifier maps pilot roots to service identities and
rejects the correctly pinned candidate with`duplicate formal worker identity`.
The new audit positively identifies pilot roots and checks them separately;
legacy rules and negative tests remain unchanged. The nested original formal
report remains complete and independently validated. New report bindings cover
actual binary/rules/sources, native reference paths, raw-clock definitions,
active/cold addresses, exact prefetch counts/witnesses and both-tool agreement.
This is separate S180 scope; it does not activate the legacy candidate profile.

The initial compiler prefix fell back to host startup/link inputs. The probe
operation bodies matched, but immutable whole-probe provenance rejected the
result. Pinning only binutils was insufficient; using the full existing compiler/
runtime prefix also binds its original startup objects. A filtered binutils
library directory avoids mixing the old runtime libm with host Python's newer
GLIBC_2.44 requirement. The complete corrected rebuild reproduces original
queue-probe SHA256`84551849f1244cd0c7e9d1b05fbb9f55e74e4ab6fa7d6058fdb6fa97baec840c`.
No provenance record, accepted hash or historical artifact was changed to pass.
All initial failures, cache-reset/reconfiguration logs and final reports remain.

## Fresh verification

- Original queue, workload, timing, storage, runner-relax, runner-combined,
 Q15-runtime and discovery generated-code gates:PASS.
- Separate actual S180/formal audit:PASS;20+42 workers and24 rejected mutants
 per disassembler. Six report custody/membership tests:PASS.
- Explicit missing-tools command:blocked as required, exit3.
- Optimized S180 regression:36/41 entries passed inside the managed boundary.
 Five IPC entries failed because its SO_PEERCRED queries return EPERM. The exact
 unchanged release's six channel/entry cases, covering all five failures and
 the negative-ACK case, passed outside that boundary. Both logs remain; this
 is not reported as an all-green initial41-entry run.
- Format, protocol/schema integrity, canonical bytes, Python AST and whitespace
 checks:PASS. Actual generated CMake command registration is inspected; the new
 CLI and report tests were invoked directly against the clean candidate and
 matching frozen sources. The new CMake aggregate target itself was not run.

The pre-commit whitespace check caught trailing spaces in generated failure logs
and a surplus newline at the end of the new rule file. Log-only normalization
is recorded with original hashes. The first rule bytes are retained as an exact
JSON source snapshot; its AST equals the final rule. The full audit and report
tests are rebound by a fresh run using the final rule bytes; native bytes and
previous gate outcomes are unchanged. The first passing report remains historical.

D318's relevant native sanitizer evidence is preserved; no sanitizer or empirical
measurement rerun is claimed for these Python/CMake changes. The full3.9MiB
machine-code report is retained without experimental raw data or binary copies.

## Stand and plan

A read-only SSH query at22November00:13Moscow found the unchanged boot,
6,276,435,984,384 root-filesystem bytes available,262,021,959,680 MemAvailable
bytes and no native process-name matches. This narrow observation is not complete
quiescence/restoration, fresh qualification or EXT009 capacity admission.
No schedule preparation, qualification, collection or24h window was started.

Next: complete qualified scoped semantic producers/journal replay, parent/profile
and durable one-attempt/sealed dispatch/archive orchestration; bind actual
original sources and namespace provenance; freeze the complete time/storage/
recovery plan and scoped EXT008/009/010. Then actual qualification/compatibility,
one180-capture pilot and independent validation/restoration/exit. The6.39h
collection/validation analogy is still not a whole-run estimate or permission
to start. Stage17 remains incomplete; Stage18 remains deferred.

Completed calibration and historical failed evidence remain preserved. No raw
was moved from the stand. Temporary software fixtures/test keys are removed.
