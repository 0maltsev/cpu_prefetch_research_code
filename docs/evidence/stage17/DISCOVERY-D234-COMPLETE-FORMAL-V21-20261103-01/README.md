# D234 discovery completion and v21 formal-release qualification

This checkpoint closes discovery validation (Step 4), not EXT007 or Stage 17.
The original D234 report validates all 36 retained D207 captures. All three
candidate durations are eligible; the accepted count-only selector chooses
**1,000,000,000 ns (1 s)** for prospective formal planning. Formal runs
contributed remain zero. No new discovery run or raw mutation occurred.

The [original full report](d234/full-study-validation-parallel-v2.json) is
54,710 bytes, SHA256
`3e129bca9fda358de857a813beecddbcc2c96ab3d0a9613ba93eac3ef06a8967`.
The [supervisor result](d234/analysis-process-result.json) is 477 bytes, SHA256
`91657ef540d8c3c28ee6dec79ad666de7b98c354c95dfb65b77abb0bc3730d10`:
exit 0 at 2026-11-03T19:32:20.088875+00:00, all owned children reaped,
raw mutation false. The rejected original validator and failed D224 analyses
remain historical evidence; successful reanalysis does not erase them.

Clean release `d45258f187ae33dbfcb7cda9459134509eb7cc78` has a passing
[full extracted-package verification](release/package-verification-1.json).
Its archive SHA is `3ee3dfbc3a7a613383960db9feb3855e6ee66110941053822a72c8f7101145a4`;
worker SHA is `03407683627caa719b66f943b15db799b2d6465d83789db35ab5ce13fe43f4ad`.
The versioned profile binds the actual selected stand Python at runtime root `/`.

The [actual stand archive fixture](runtime/archive-runtime-check-2/result.json)
passed for all nine canonical artifacts in 18,654,879,599 ns. Original hashes,
independent retained readback and parked-worker cleanup are retained. This is
cold software compatibility evidence, explicitly not experiment readiness or
scientific credit. The earlier fixture failure and both launcher records are
preserved alongside the passing result. The package record's earlier
`stand_runtime_qualification=PENDING` field is historical; its bytes are unchanged
and the later stand fixture supplies separate evidence.

The [bound serial-stop result](v21-prerequisites/serial-stop-result.json) retains
SIGINT at 19:37:29 UTC only after checking the full-success report hashes.
The redundant serial child exited; its original supervisor terminal result is
preserved with exit -2. This is cancellation of a superseded reader, not a
failed discovery capture or mutation of raw evidence.

The [v21 journal 000006](v21-prerequisites/journal-000006.json) and original
admission logs retain EXT001/002/003/006 admission (four resolutions and two
transitions). The clock family was launched as PID 39581; intent and PID/start
identity are retained. The [original clock completion](q15-preparation-failure/clock-qualification-v21-1/complete.json)
records **both pairs passed** at 19:42:54 UTC on source `d45258f`.
The [Q15 preparation failure log](q15-preparation-failure/prepare-q15r-v21.log)
records a missing controller26 `_runtime_from_context` callback. The adjacent
legacy `_validate_action_inputs` callback was also absent. Failure occurred
before publishing a Q15 request, authorizing/signing it or invoking the worker;
Q15-W did not start. [Restoration](q15-preparation-failure/clock-qualification-v21-1/restoration.json)
was verified at **19:44:55 UTC**, with the partition absent and root cpuset restored.

The minimal correction exposes the two unchanged predecessor callbacks in
controller26. This is cold routing repair, with no scientific method change.
A fresh clean successor release and source-bound qualification are required;
prior package, runtime and clock passes remain historical evidence for `d45258f`,
and cannot be relabeled as passes for the successor.

Step 5 remains in progress: clean-successor qualification, Q15, exact formal plans and
phase authority precede actual Q16a/Q16b/Q16c collection. Step 6 remains pending:
independent formal validation, scoped calibration freeze and EXT007 admission.
One-second discovery selection does not itself qualify another producer release,
supply an exact formal plan, establish d2/mu_ref or grant execution authority.

[Inventory](inventory.json) binds every copied original byte. Near/far clock
completion and restoration records are included; Q15 completion remains pending. No second raw-data
copy or new discovery capture is implied.
