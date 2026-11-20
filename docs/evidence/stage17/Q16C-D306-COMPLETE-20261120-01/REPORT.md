# Q16c complete: all 180 reports valid, original results preserved

The approved D306 continuation finished on **20 November 2026 at 05:03:24 Moscow**
(finalized file timestamp02:03:24UTC). All94 new captures passed independent raw
and execution validation, and the original86 validated reports were reused.
The resulting full matrix has **180 VALID, 0 INVALID, 0 MISSING** reports.
All three owner phases (authorization, collection, suffix) exited0 and were reaped.
The root result is success=true with errors[], and the native executor completed
without quarantine. Native, CPU/isolation/maintenance and guard restoration passed;
independent StopPost recovery also passed without errors or required signals.

The startup was01:42:00Moscow, giving about3h21m total. Collection took
10,633.336seconds (2h57m13s); suffix admission, validation and composition took
1,385.772seconds (23m6s), within its original3,600-second limit. The existing
signed day and31,460-second continuation ceiling were preserved. There was no
new qualification, repeated completed measurement, repeated raw validation or
automatic retry. Q16a708 and Q16b120 remain unchanged.

At06:34Moscow the service is inactive/dead, MainPID0, no control group or native
worker remains, all94 native checkpoints are complete with0 failed, and the
guard reads its prior value1. Root and independent recovery retain exact full
MSR0x1a4 matches on CPUs0/1/8 and verified isolation/maintenance restoration.

## Independent final metadata check

A separate read-only check as actual UID1000 verified all180 original report
hashes, all94 VALID/reaped suffix process receipts, removed canonical scratch
claims, the completed supervisor’s signed-lifecycle terminal binding, exact completion/plan bindings, original phase
deadlines and both recovery results. It recomputed the whole composition from
the already validated report bytes and compared canonical bytes with the saved
composition exactly. The script also compared its composer source bytes with
the qualified candidate's copy. No raw archive decoding was repeated.

The first metadata-only audit attempt reached a missing qualified-tool import
path. The audit script's import path was corrected, and the check passed at
06:36:50Moscow. This affected neither the completed experiment nor its raw
validator or qualification. The exact successful script and check history are
retained under verification/.

The final composition is retained at
[calibration-validation.json](q16c-analysis-1/calibration-validation.json),
its180-report coverage and limits at
[final-report-check.json](final-report-check.json), and the actual supervisor and
independent recovery receipts under d306-study-1/ and d306-independent-recovery-1.json.
The manifest binds every retained public file. The large raw archives remain on
the stand; only final reports and small public metadata are copied to the PC.

## Scientific outcome and limits

This is the accepted **MATRIX-FULL-DESCRIPTIVE-CONTINUED-PLATFORM-STRATA-v1**
method. The original collector-format identity is retained separately. All180
settings have one capture,5-second warmup,1-second measurement and initial scale1.
The first86 captures have platform regime UNRECORDED and the94 new captures have
VERIFIED_ZERO; the result does not claim homogeneous-platform evidence.

The separate zero-loss gates are **FAIL**:

- Measurement:3 FULL-bearing captures, original ordinals20,28,56, all in the
  retained prefix. All94 new measurement captures have zero observed FULL.
- Warmup:25 FULL-bearing captures across the two populations.

These are correctly reconciled, valid data and remain retained. They do not
authorize rerunning or dropping a capture. No D036 confidence, final-scale,
future matrix-success or confirmatory guarantee is established. Final matrix
feasibility remains NOT_EVALUATED and final_scale_selection remains null.

## Remaining work

Q16a, Q16b and Q16c data collection/validation/composition are now complete.
The separately versioned descriptive calibration freeze/handoff permitted by
D270 and operational EXT007 admission still need integration and verification.
The existing archival EXT007 verifier remains closed until those gates pass.
See [the concrete finalization requirements](../../../STAGE17_EXT007_FINALIZATION.md).
EXT007/Stage17 are therefore still incomplete. EXT008–010/pilot and Stage18
remain deferred under the active EXT007-only scope. No new experiment starts
from this report.
