# D224 parallel retained-study analysis preparation

Offline validation of the existing D207 R3 family only. All 36 captures remain
mandatory; the unchanged D213 capture validator and count-only selector are pinned.
No raw data was copied to this PC and no new experiment is authorized.

Verification: 13 independent adapter tests (including complete serial/parallel
parity, actual worker failures, deadlines and reaping); 14 supervisor tests
(including escaped descendants, unlinked scratch files, exclusive starts and
last-worker completion race); 13 original binding/wrapper tests. All passed.
The launcher uses eight workers with 8 GiB address-space limits, 8 GiB parent
and supervisor allowances, 80 GiB available-memory admission, and a 24-hour
whole-analysis limit. Scratch is monitored at one-second intervals with an
explicit 16 GiB allowance and 16 GiB free-space reserve; it is not a hard quota.
The sixfold control-expansion estimate is recorded as an estimate, not a proof.

The install manifest binds the exact six analysis files and original input
arguments. Only the wrapper, scratch and report paths change from the serial
invocation. Installation is exclusive and the original serial analysis is
preserved. This packet records preparation; stand launch and results require
separate fresh receipts. Local verified source commits are not experiment release
qualification.

Every retained file is listed with its SHA256 in `manifest.json`.
