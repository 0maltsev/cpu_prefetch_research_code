# ADR-0213: Validate actual whole-plot action readbacks

- Status: `ACCEPTED` — scoped engineering repair under existing authorization
- Date: 2026-11-03
- Scope: independent analysis of retained D207 evidence; no capture-code change
- Scientific design: unchanged; no new experiment, retry or extension

The completed D207 R3 family contains all 36 captures. Its native action and
outer supervisor exited successfully, CPU isolation restoration passed, and
CLI17 custody admission passed. The independent v2 validator then rejected
`whole plot restore prestate: differs` before validating the captures.
Retain that rejected report and its original validator unchanged.

The qualified implementation in `src/platform/q15_msr.cpp` verifies the full
prestate on entry for both H0 and H1. H0 makes no writes: it verifies the same
values again on leave, but its write/apply and write/restore readback vectors
are empty. H1 writes in prestate order and restores in reverse write order.
The two-plot dispatcher preserves these actual vectors in `studyhardware.json`.

The validator incorrectly expects a populated prestate-order restore vector
for both plots and a populated H0 apply vector. Its synthetic fixture does
not represent the qualified native writer. The retained record has empty H0
vectors, H1 apply order 0/1/8 and H1 restore order 8/1/0. These are action-log
semantics, not absent per-capture hardware monitoring.

Add independent validator v3, preserving v2 bytes and every other validation
rule. Require exactly the two ordered H0/H1 plots with true restoration:

- H0 must contain the native no-write form: both action-readback vectors empty.
- H1 apply must equal the complete signed prestate values with the accepted
  disable bits set, in prestate order.
- H1 restore must equal the complete signed prestate in reverse order.

Do not fill or rewrite any original output. Reject extra, missing, duplicate,
misordered or mismatched H1 entries. Preserve the existing independent
before/during/after hardware checks in both phases of every capture, including
all required CPUs, actual eight-byte reads, parsed values, requested state
and mapping identity. An empty action log never substitutes for those reads.

Regression tests must reproduce the rejection of the native-shaped record by
v2, accept the exact native action-log shape in v3, and reject malformed
whole plots and corrupted or missing per-capture hardware evidence. Historical
v2 behavior remains independently tested.

Analyze the same immutable raw and control files on the stand using a separately
hash-bound v3 analysis record and a fresh scratch/result location. Retain the
prior admission and rejected result. Reanalysis is not recollection and does
not supply a new source qualification for experiments. It must validate the
entire family before invoking the unchanged count-only duration selector.
No raw observations return to the PC and no retained stand evidence is deleted.
