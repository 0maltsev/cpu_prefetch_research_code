# Q16b stopped after16 archived captures

Checked16 November2026, approximately00:42–00:45 Moscow time. The service
cpu-prefetch-daycap-v26-resume-2.service is failed with MainPID0 and exit1.
Its native failure receipt completed15 November20:49:27 UTC, and the service
exited20:49:30 UTC (23:49 Moscow). It had started native collection19:41:08 UTC.

The stand retains16 archive-custody receipts (captures0–15) and17 final
checkpoints (captures0–16). Capture16, the17th capture, has no completed archive
custody receipt. Required total remains120. Offline analysis did not start, so
these are custody/progress counts, not independent scientific-validation claims.
Original Q16a708 and all prior qualification remain retained.

The final supervisor report's primary error is
`ProcessLookupError(3, 'No such process')`. The archive broker separately
reported lost native quiescence: worker exited or pidfd is invalid. The native
failure category is ARCHIVE_WORKER_FAILURE. These records do not establish a
spontaneous native crash, a timeout or exhausted storage. A process-monitoring
race is a plausible lead: the supervisor's descendants/observe reads catch
FileNotFoundError but not ProcessLookupError. The exact triggering call and
causal order remain unconfirmed; no reproduction or software fix was attempted
as part of this status check.

The final native failure receipt verifies leader reaped, process group gone,
MSR restoration readback for CPUs0/1/8 matching the original zero values, and
partial evidence retained. The fresh isolation restoration verifies the CPU
partition removed, root CPU state restored, maintenance services/timers
restored, and no restoration errors. The final supervisor cleanup confirms
leader reaped and no forced cleanup. The earlier collection phase snapshot's
null exit code is superseded by this final cleanup record.

The run remains stopped under the owner's no-automatic-retry instruction.
No experiments were started, repeated or extended by this check. Only bounded
public failure/custody/restoration metadata was retained on the PC. Scientific
raw data and failed evidence remain on the stand. Stage17/EXT007 are incomplete;
the previous completion estimate no longer describes an active run.
