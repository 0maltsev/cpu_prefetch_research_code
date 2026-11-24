# D260 proposal: One Q16b continuation using the 17 retained completed captures

- Status: PROPOSED; no execution or deadline-extension authority
- Date: 2026-11-16
- Proposed amendment: AMEND-2.0.0-pre.3-Q16B-RETAINED-PREFIX-CONTINUATION-v1
- Scope: the exact stopped E26 D254 family only; no general retry mechanism

## Original evidence and current boundary

Original source: aa3285f15acbd3314cae64a628c113488a8438b8. Native worker SHA256:
305cedfc5438c68ececfa6a0f954d757112a50c87f687b93ad7b013b7ed757dd.
Original canonical plan: 2,072,840 bytes, SHA256
53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486.
Original signed request: 2,076,157 bytes, SHA256
a2feeb896645779cae711735a1e7ad93bf547effba9823d2d6c97220cac6a3b5.
Original failure: 1,084 bytes, SHA256
332662f64d2f802578c0152aec69781f3b913afca43efe2714483da7e80b3269.

The original native worker was reaped, its process group was gone, all three
recorded MSRs matched the restoration target, and CPU/maintenance restoration
was verified. D258 repairs the external supervisor's disappearing-process
observation without weakening actual worker-loss or cleanup gates.

There are 17 native-complete checkpoints (ordinals 0–16). Captures 0–15 have
complete custody receipts whose physical archive hashes passed original
signed-plan preparation and read-only inspection. Capture 16 has five RELEASED
sources and one PUBLISHED control archive; its original control remains.
Independent scientific validation of all 17 is running under D259. Native
completion and physical archive checks alone do not establish reuse eligibility.

## Proposed continuation

1. Require independent raw reconstruction, hashes and the unchanged scientific
   validator to pass for **every** retained ordinal 0–16. Keep FULL, zero and
   low-observation outcomes under their existing validity rules. Do not select
   a shorter prefix, replace a failing capture or inspect throughput to choose
   which captures to reuse. An invalid required capture stops this proposal.
2. Complete only capture 16's interrupted custody bookkeeping through a
   separately tested, explicit post-exit recovery. Require original signed
   lineage, checkpoint, published archives, fresh original-byte readback,
   verified worker absence and restoration. Keep all failure history. Never
   simulate a live parked worker or reset the shared program/ledger.
3. Introduce a versioned **service-plan/4** execution family containing exactly
   **103** entries. Local ordinal 0–102 maps to original ordinal 17–119; its first
   capture is the original second repetition of cell ordinal 8. The retained
   first repetition of that cell stays bound to its original source and report.
   Preserve the original numeric seeds, settings, science, per-capture limits
   and shared D233 storage bounds. Use fresh run/seed/namespace identities with
   the same encoded run-ID widths. Permit only authenticated qualified-release/
   profile substitutions and complete five-file cpuset-path relocation.
4. The current executable accepts only the full 120-entry /3 family. Make the
   necessary cold native admission change, verify a clean release and qualify
   that actual executable once (near/far clocks, then Q15-R/W). Prove the entire
   measured-source closure and physical platform are unchanged across sources.
   Never assign the old qualification to the changed executable. Retain all
   708 completed Q16a reports through their existing compatibility handoff;
   do not recollect or independently revalidate them again.
5. Independently validate all 103 new captures, then explicitly compose their
   reports with the 17 original reports. Keep original report bytes, run IDs and
   source qualification in both histories. The combined planned coverage is
   the original 60 cells × 2 repetitions. Apply D254's unchanged exact minimum
   arithmetic and report DESCRIPTIVE with no 59-run tolerance guarantee. Do not
   manufacture a completed 120-capture execution receipt for either family.
6. Stop on the next Q15/Q16 failure or any validity, custody, time or resource
   failure; retain evidence, reap workers and restore hardware/isolation.
   No further automatic retry, extension, top-up or replacement is authorized.

## Required time decision

The original absolute monotonic deadline remains 1286361844786205, approximately
**2026-11-16 17:23:47 UTC / 20:23:47 Moscow**. At 07:24:47 UTC, 9h59m remained.
Do not reset that historical deadline or represent the stopped study as having
finished within its original cap.

Actual retained capture-start intervals span 173.52–284.96 seconds, mean 238.80
seconds (16 intervals). At that early-cell mean alone, 103 remaining captures
would take **6h50m**. This excludes fresh qualification/admission, later settings
not covered by these intervals, independent validation and restoration. The
previous retained 5.13 GB validation benchmark took 5m44s; the running prefix
validation will provide actual eight-worker timing for this family.

The prospective whole continuation estimate is **approximately 11–15 hours
after experimental launch**, subject to updating from prefix validation and the
actual prepared release before launch. Its finite conservative envelope must
still be checked against every requested bound. The original full-family
watchdog is 18h04m; preserving that ceiling, a 3h45m analysis reservation,
one-hour qualification allowance and 30-minute reporting/restoration reserve
totals 23h19m. If actual admission cannot satisfy the chosen envelope, do not
launch or silently lower controls.

Request explicit approval of **one new absolute 24-hour continuation window**,
anchored to its first actual qualification/admission action, covering that
qualification, only the remaining 103 captures, archival, independent validation,
composition/reporting and restoration. This is an explicit exception to D254's
original single-window/no-extension restriction. Preparation and retained-data
analysis confer no approval. Present the updated approximate duration before
any new experimental launch. No Stage18 authority follows from this proposal.
