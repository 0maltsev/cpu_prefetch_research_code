# D260 admission stop and preserved progress

The first input check failed before any new Q16b measurement. All 17 original
captures remain independently VALID with complete archive custody. All 708
completed Q16a reports and the new release's successful near/far clocks and
Q15-R/W remain preserved. No completed measurement or raw validation was repeated.

The actual cause was a software JSON type mismatch: the prefix gate applied
the integer-only scientific reader to elapsed-time diagnostics in the exact
completed analysis manifest. The failure log records
`ContractError: continuation: floating-point input is forbidden`.
No raw report was rejected at this boundary.

The prepared 103-entry plan has SHA256
d980ed9417ddf76e88931d849a62573971522b10604975c51f5fa709335698f4
and 1784078 bytes. Its family was not registered, no action was signed and
its archive working directory does not exist. The source-bound native release
is still clean 07a93fb; the scientific matrix and measurement controls are unchanged.

Following the user's stop-on-failure rule, the root handoff was explicitly
terminated and cleanup completed at 11:29:40 UTC on 16 November (14:29 Moscow).
Fresh read-only checks confirm the root supervisor and input checker have
MainPID0 and empty control groups. The isolation service is inactive, its
reserved partition is absent, CPU and maintenance restoration are verified,
and the restoration error list is empty. The root supervisor's exit1 retains
the deliberate signal-15 stop; it does not mean Q15 failed.
The [stand stop evidence](stand-stop-evidence.json) binds these exact public
receipts and the original unchanged absolute window. Only small metadata was
copied to the PC; raw archives and failed evidence remain on the stand.

[D265](../../../decisions/0265-d260-software-diagnostic-reader.md) adds a local,
separately versioned reader for only the exact hash-authenticated diagnostic.
Scientific inputs remain integer-only. The deployed v1 packet was not edited,
and the correction has not been deployed or retried. Actual complete admission
is therefore still unverified. The two-source descriptive composition helper
is prepared locally and tested with synthetic reports; no actual combined
120-capture result is claimed.

The approved deadline remains 17 November 09:41:23 UTC (12:41 Moscow).
The reserved-budget latest collection start is 16 November 13:55:23 UTC
(16:55 Moscow), accounting for collection, validation and cleanup. The clock
continues while stopped. No automatic retry or extension is authorized.

Remaining steps, in order:

1. On further continuation, integrate the corrected reader into a separately
   authenticated packet and verify remaining time, current qualification
   compatibility, prefix, namespace, signatures, resources and isolation.
2. Collect only the remaining 103 original positions, preserving the 17
   completed captures. Give an updated whole-family time estimate first.
3. Independently validate the new captures and compose their descriptive
   results with the 17 original reports, preserving both source populations.
4. Complete Q16c, calibration freeze and EXT007/Stage17 exit requirements.
   Stage18 remains prohibited until those requirements pass.

Local verification: [11 parser/custody tests](diagnostic-tests.log) and
[5 composition tests](composition-tests.log) passed. Python syntax and diff
whitespace checks passed; local links in all five changed Markdown documents
resolve. The repository-wide document check still reports 14 broken
relative links in historical copied approval documents; each affected file
is byte-identical to the parent commit. Those historical documents were not
changed. See [verification and exact source hashes](verification.json) and the
[repository document-check log](repository-document-check.log).
These checks provide software evidence and do not establish empirical
performance or successful live admission. No native or measured code changed;
native sanitizers are not applicable to this Python-only correction.
