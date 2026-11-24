# D207 R3 collection and first validation checkpoint

Qualified source `a1ade11bc5596ad4050ba9b4ae6c4031ebd6dfde` collected the
single authorized 36-capture family from 12:29:53 to 13:55:31 UTC on
2026-11-03. Plan SHA256:
`b513b6a7592fe010bc9a4fa256a7b214252504920636b286ad1f0edb8bdb6fcf`.

The outer supervisor reports exit 0, child reaped, completion present, empty
experimental partition and verified restoration with the partition removed.
The retained output inventory totals 215,177,813,577 bytes across 259 files.
This is collection progress, not scientific validity or formal calibration.

CLI17 custody admission passed at 14:05:34 UTC. The independent v2 validation
then rejected `whole plot restore prestate: differs` at 14:15:18 UTC before
individual capture validation. No duration was selected. Native H0 correctly
records no writes, while H1 restores in reverse write order; the checker
expected populated prestate-order vectors for both. [D213](../../../decisions/0213-discovery-whole-plot-readback-validation.md)
records the narrow independent-validator correction and reanalysis boundary.

`originals/` contains byte-identical small supervisor, action, hardware,
retention, admission and first-validation records. `inventory.json` binds
their exact stand paths, sizes and SHA256 values. The 16 copied metadata
files total 607,139 bytes; no event stream or large per-capture control file
was copied. The redundant metadata transport was deleted after local hash
verification; its cleanup receipt is retained. All raw/control evidence stays
on the stand under D206. No stand evidence was deleted or rewritten.

This record does not admit EXT007, authorize another capture, or establish a
scientifically valid discovery family. Later reanalysis must retain this
original rejected result and bind the same original data.
