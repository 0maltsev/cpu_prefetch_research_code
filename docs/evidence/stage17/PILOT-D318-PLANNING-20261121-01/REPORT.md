# D318: prospective S180 layouts and parent plan preparation

The native worker now computes all180 prospective layouts without allocating
represented sources or shared data mappings. The parent planning module pins
that actual image and its sizing input in sealed descriptors, validates the
full frozen declaration and assembles an execution-plan candidate from exact
declared counts and explicit original artifact bindings. Candidate preparation
is separate from signed admission, source-byte verification and launch authority.

[D318 decision](../../../decisions/0318-s180-prospective-layout-and-parent-planning.md)
describes the source-count, layout, memory and authority boundaries.

A concrete R1 defect was found before launch: the input parser supplied
calibration evidence for its fixed one-line distance, contrary to the original
native policy. R1 now carries an empty evidence ID, and the declaration validator
rejects that mismatch. R2 retains the accepted descriptive freeze. No pilot failed
or was repeated to fix this software error.

The native sizing schema explicitly distinguishes exact declared counts and
prospective upper ceilings; null means an original source is not materialized.
Execution retains its physical source/descriptor and live mapping checks. No
unknown hash, source observation or platform value is invented for sizing.
The planner reports native resource minima and4501 native/broker/codec processes;
external preparation/qualification/analysis resources and a whole-run ETA remain
unverified. These minima cannot resolve EXT009 by themselves.

## Verification

- 56 focused CTest entries passed, including38 native S180 cases, archive and
 parent process integrations; the new parent suite exercises3 actual sealed CLI
 cases. The latter are software tests using explicitly synthetic declarations.
- 139 existing runner,22 mapped-pilot and213 calibration cases passed after the
 shared native layout arithmetic refactor.
- GCC ASan/UBSan, GCC TSan, Clang/libc++ ASan/UBSan and Clang/libc++ TSan each passed
 all32 affected S180 cases. Six unchanged worker-entry cases remain covered by
 the dev regression and D317; these are not claimed in this32-case matrix.
- Format/protocol/schema fixtures/canonical/provenance/runner schema gates passed.
- The first full6-file static check rejected4 optional-value accesses in a new
 test; production files passed. Explicit guards fixed that test; the affected
 file passed the final static check, and a fresh dev rebuild plus all9 input/
 prospective-layout cases passed. Both initial and corrected check logs remain.
 The full56 entries and first GCC ASan/Clang TSan matrices preceded this test-only
 guard cleanup; production sources were unchanged. The remaining two sanitizer
 matrices used the final test source. No check failure is relabeled as a pass.

The original fixed-action entry is unchanged (SHA256
`03130e61fcd1b61b4cb7b2d1bfc564f1420e87eebcbff428a2b3f7ff4eec764e`).
No immutable protocol file, calibration result, source raw or historical evidence
was modified. No schedule preparation, qualification or experiment was started,
and there was no stand access in this step. No raw data was copied to this PC.

## Remaining ordered gates

1. Qualified signed parent/profile with exact scoped launch/admission and original
   source generation/provenance plus namespace reservation/consumption.
2. Exact complete memory/storage/recovery/time plan and scoped EXT008/009/010;
   present the all-inclusive estimate before starting the single24h window.
3. Clean release, strict codegen and actual stand qualification/compatibility.
4. One approved180-capture pilot, stopping/restoring on the first new failure.
5. Preserve results, independent scientific validation, restoration/quiescence
   and scoped Stage17 exit. Stage18 remains deferred.

Completed Q16a/Q16b/Q16c data and validation remain preserved without reruns.
