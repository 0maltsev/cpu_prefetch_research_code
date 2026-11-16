# D265: exact retained software-diagnostic parsing

- Status: ACCEPTED local engineering correction; not deployed or retried
- Date: 2026-11-16
- Scope: the approved D260 continuation's retained-prefix admission

The first real input check stopped before registration, signature or Q16b
execution. Its integer-only scientific JSON reader rejected floating-point
elapsed-time diagnostics in the existing completed D261 analysis manifest.
The source-bound Q16a/hardware input checks preceding that point passed.
This was a software admission failure, not an invalid raw capture.

Preserve the exact manifest: 5742 bytes, SHA256
6f95694880e143a25e27bdf39990817a0310b0a032a78781688ba8bb7701f9a3.
The separately versioned prefix-admission v2 reader authenticates its bytes
before parsing decimals exactly with Decimal. This exception selects only
that size/hash pair, rejects duplicate keys and nonfinite values, and checks
the original 17 report ordinals and finite elapsed software-analysis limits.
All other inputs, including scientific reports, hardware, plans, checkpoints
and custody receipts, retain the original integer-only reader. Never rewrite
the completed manifest or change its report bindings to avoid this error.

The private v2 admission entry clones the original admission function with
only that reader substitution. Historical v1 module/function globals and the
deployed immutable packet remain unchanged. Local tests reproduce the actual
saved-manifest failure, accept its unchanged diagnostic bytes, reject forged
or modified bytes and scientific floats, and rerun real codec/custody/report
corruption checks through the corrected reader. They establish software
behavior only; complete actual stand admission remains unverified.

The pending descriptive composition helper preserves the two actual source
populations, 17 original and 103 prospective reports. Original IDs, source
revisions, local ordinals and report bytes stay intact. Original capture
position is an additional field, never a replacement local ordinal. It uses
unchanged D254 exact rational cell minima over two observations in each of
60 settings, retaining genuine zero and separate FULL/zero-loss gates.
Missing reports remain unresolved; duplicate or relabelled reports fail.
Synthetic parity checks establish the calculation only. The helper grants
no provenance, family validity, tolerance guarantee or execution authority;
actual combined results do not exist until all required inputs are admitted.

The user required stopping on the next failure without automatic retry.
Therefore the waiting root handoff was stopped, workers reaped and isolation
and maintenance restored. The successful near/far clocks and Q15-R/W, all 708
Q16a reports and all 17 valid/custodied Q16b reports remain preserved.
No additional measurement, raw decode or qualification was repeated.

No live retry follows this correction. Further continuation must separately
wire and verify the v2 reader in a new authenticated administrative packet,
preserving the failed packet, actual qualified native release 07a93fb and
original D260 clock. The window began 09:41:23 UTC on 16 November and ends
09:41:23 UTC on 17 November; it cannot be reset by software or a new process.
The reserved-budget latest collection start is 13:55:23 UTC on 16 November.
Check remaining time and all original gates before any resumed collection.
EXT007 and Stage17 remain incomplete; Stage18 remains prohibited.

See the [failure, restoration and local verification report](../evidence/stage17/D265-DIAGNOSTIC-ADMISSION-20261116-01/REPORT.md).
