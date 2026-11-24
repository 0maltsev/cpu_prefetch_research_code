# E22 formal Q16a preparation failure

Clean source `c962fd757f0b215088e6a91e760af0616ab9636b` completed actual E22
qualification: both clock pairs and Q15-R/W passed, Q15 hardware restoration
and process reaping passed, and EXT001–006 reached journal 000009 (six
resolutions and three transitions). Formal request preparation subsequently
failed before request publication, authorization/signature or native execution.
The registered family is empty; there are no formal observations or calibration
results. Steps 1–4 remain complete, Step 5 is reopened for the cold controller
repair, and Step 6 has not started.

The [original operator log](originals/formal-q16a-preparation-1.log) records
family registration at 20:34:58 UTC and request authoring at 20:35:16 UTC.
The [failure record](originals/formal-q16a-preparation-failure-1.json) records
`author_request` failure and `native_formal_execution_started=false` at
`2026-11-03T20:36:08Z`. The [original restoration
record](originals/clock-qualification-v22-1/restoration.json) has that same
exact timestamp, `verified=true`, `partition_absent=true`, no isolated CPUs,
root effective CPUs `0-31`, and root memory nodes `0-1`.

The [public EXT002 runtime-release receipt](originals/ext002-runtime-release-provenance.json)
binds profile `b9e12215cfcb37e8af765107e895fc12fec3345ecc253b6701788fa5c3d86e06`
using the relative bundle member
`config/stage17/formal-archive-implementation-profile-v1.json`, with an explicit
absolute `archive_bundle_root` and `archive_runtime_root=/`. The cold
controller compared that member directly with an absolute path and rejected it.
Its earlier fixture supplied an absolute profile locator and did not exercise
the production receipt representation. This is an engineering boundary defect,
not a new scientific decision or an experiment failure.

The [registration receipt](originals/admission-root/evidence/formal-q16a-1/family-registration.json)
binds original Q16a plan SHA256
`59898ca78f6b79c14e845859052027241c54298c9f65dcb1042b05b18be6af2e`
and program scope SHA256
`c1a28eadb302ac3b311b32d67f3ebd9b3aebfbdb810968da7fd84c24d0987a8b`.
The 708-capture plan, fixed 5 s warmup, D234-selected 1 s measurement,
minimum 100,000 observations per sequence and F21 phase identities remain
historical originals. Registration granted no execution authority. No large
plan, action-input document, binary or raw stream is copied into this record.

[The inventory](inventory.json) binds exactly five copied originals: the four
files in the operator's original failure inventory plus the public release
receipt. All original bytes were preserved. The complete qualification
metadata remains in the local bounded snapshot
`build/stage17-step5-prep/formal-v22-qualification/qualification-snapshot-1`
and its original stand E22 custody; this small failure record does not replace
that source-bound qualification evidence.

The correction is now verified. The [verification inventory](verification/inventory.json)
binds the original failing regression, all seven passing targeted tests (37.413 s),
an independent integration repeat (20.314 s), and fresh policy verification
(26.356 s). The [actual stand diagnostic](verification/stand-diagnostic-1.json)
passed against all six original qualified resolutions and the entire 708-capture
plan, using the corrected controller outside the immutable E22 release. It
records 229 original imported source files. This diagnostic validates input
admission only: it creates no request, signature, authority or workers and
provides no empirical calibration credit. The new integration regression covers
actual receipt production, CLI authoring/signature and executor preparation with
software fixtures; it does not claim live native execution.

A subsequent clean release still needs source-bound qualification before formal
execution. Unchanged native/sanitizer and codec evidence can be reused only where
its byte bindings remain applicable; no broad repeat was needed for this cold
Python path correction. No counts, thresholds or scientific methods are reduced.
The [earlier d452 package/runtime/clock successes and Q15 preparation
failure](../DISCOVERY-D234-COMPLETE-FORMAL-V21-20261103-01/README.md) remain
preserved under their original source identity. Stage 17 remains incomplete.
