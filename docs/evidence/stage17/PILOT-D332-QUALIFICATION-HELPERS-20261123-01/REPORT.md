# Qualification helper software checkpoint

The resource mechanism is preserved at6375b30. Building the missing auxiliary
qualification executables exposed an independent prerequisite defect: the
evidence tool's self-test expects /2 while its accepted builder already emits /3.
The unchanged frozen34247ce helper reproduces the failure. Only that diagnostic
comparison is corrected; no real raw/evidence behavior, sampling, clock/Q15
limits or measurement-worker bytes change. [D332](../../../decisions/0332-q15-evidence-helper-v3-self-test.md).

The corrected development helper passes its new registered CTest and actual
GCC ASan/UBSan synthetic JSON/builder round trip. All six helper software
diagnostics pass; their exact binaries, scopes and logs are retained as metadata.
The clock helper SHAcb6422db0be2c3ff3b20897bc58ff4b892ba04e34e9f16f93a8b6d5a04caad69
matches the earlier v32 software image. This proves byte identity, not a new or
reused qualification. The generic fixed tool declares06_55H/CPUs0,1,26 and is
excluded from this stand's hardware route; actual Q15 uses the frozen runner's
model-aware persistent session.

The corrected development/sanitized images are software verification only.
The corrected helper now has a clean Release build from3266ed3a425da3345743c3a462a75ab1e71cc589;
its registered regression passes. The700568-byte image has SHA
`6b8898238157e4d589615cbc6c57ced54aa143b403ef66bd337cab4960f3a918`.
Actual generated metadata records source_dirty=false. Its source/image remain
bound separately from unchanged native34247ce. No frozen source
tree was edited. Format, protocol/schema, canonical/provenance and whitespace
checks pass. The native SHA7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc
remains unchanged.

**No stand qualification, S180 source generation, pilot or operational window
started.** Qualified outer operator/profile, actual EXT008 facts, final live
admission and independent scientific validation remain pending. Stage17 is
incomplete; completed EXT007 is preserved and Stage18 remains deferred.
