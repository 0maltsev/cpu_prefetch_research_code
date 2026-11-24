# D288 metadata constant width correction

Targeted clang-tidy found three implicit-widening diagnostics in the cold formal
family parser: two new2MiB checks and the existing1MiB source-metadata check.
Use explicit uint64 initial operands. The values remain2097152 and1048576;
no size, time, count, scientific gate, observation or experiment changes.
The exact reviewed cold-source hash and policy63 bindings are updated.

All48 affected native tests and16 policy/Q16a-compatibility tests pass after the
correction. Targeted static analysis passes the family and scheduled-source
files; the fixed-action file and broad analysis are still running and are not
credited at this checkpoint. A fresh clean candidate and release checks follow.

The486f7b7 software preview passed all eight generated-code gates, all139 release
runner tests, nine measured-library hash comparisons and extracted-bundle
verification locally and on the stand. It is explicitly blocked from qualification
pending the verified successor. No native calibration, raw prefix validation or
new24h window started. Original raw archives, failed evidence and completed
Q16a/Q16b reports remain unchanged. This is software preparation under D288's
existing approval, with no new execution or retry authority.
