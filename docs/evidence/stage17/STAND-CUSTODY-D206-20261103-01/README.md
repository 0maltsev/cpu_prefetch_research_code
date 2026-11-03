# D206 custody change, PC cleanup and stand-side failure validation

The owner explicitly approved **“Approve stand-only raw storage and PC cleanup”**.
The original proposal and exact acceptance are retained here. Accepted policy
`EXT007-RAW-NONE-STAND-PRIMARY-v1` applies to EXT007 diagnostics and calibration,
including both failed v19 families. The stand retains one authoritative raw
copy without an independent raw backup. The PC retains reports and provenance.
Pilot and Stage 18 custody are outside this exception.

## PC cleanup completed

The PC transfer was paused, then cancelled after acceptance. Its four local
SCP groups exited, and the copy controller recorded an incomplete transfer;
no successful second-copy receipt was fabricated. Fresh stand-side size/hash
verification passed for every original corresponding to the cleanup targets.

At 11:12:37 UTC, **16 PC files totaling 7,926,030,848 bytes** were removed:
the former first-attempt copy and four incomplete R2 transfer payloads.
No stand raw file was deleted. The cleanup intent, per-file removal events,
verification result and withdrawal of the former PC copy are recorded here.
Historical two-copy receipts remain historical records, not current-custody
claims after that withdrawal. Task transfer payload directories are empty;
small cancellation logs, manifests and provenance remain.

## Failed capture 9: monitoring-window overrun

The unchanged bounded reader verified original control/hardware hashes on
the stand. During the 100 ms measurement, the region-5 observation started at
**25.005774 ms**, took **163.531831 ms**, and ended at **188.537605 ms**.
Both workers had reached their fixed deadlines by then. The observer correctly
reported workers finished during the required observation; the remaining
region observation was unattempted. Native session stop is observation failure.
The report does not isolate an individual slow file or syscall inside that
combined monitoring operation.

The existing independent phase validator then reread and reconciled the
retained raw data on the stand:

| Phase | Accepted | Consumed including drain | Producer FULL | Result |
|---|---:|---:|---:|---|
| Warmup | 9,635,880 | 9,635,880 | 4,059 | Phase integrity passes; actual reset verified |
| Measurement | 187,535 | 187,535 | 0 | Phase integrity passes |

This reconciles event identities, ordering, clock boundaries, checksums,
demand/issue vectors and drain accounting for the failed capture. It does
**not** make the capture valid: full-capture validation still rejects
`mandatory session stop`. No duration selector ran. Earlier capture validity
remains unassessed; the partial study contributes zero formal runs.

All analysis used the unchanged qualified validator. Only small diagnostic
and validation reports were downloaded. R2 remains failed, its authority
consumed, and the stand restored. A prospective duration-design correction
requires a separate decision; no retry follows from D206.
