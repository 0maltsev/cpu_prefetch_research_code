# D309: preserve the preview outside the live journal and replay existing EXT007

Accepted engineering recovery within the authorized EXT007 metadata finalization.
The D308 preview and ordinary candidate validation succeeded. The ordinary CLI
published resolution007 and journal000010, then the final replay correctly
rejected a fork: the saved noncanonical preview was also a JSON snapshot in the
live journal directory. `latest_journal` uses canonical names, but the separate
fork detector intentionally inspects every JSON snapshot. Keep that detector.

Preserve the exact preview bytes by an exclusive durable hard link into the new
recovery output directory, record the old/new locators and hash, then remove only
its live journal locator. The old preview-verification binding is a historical
locator; the relocation record provides its current custody location. Preserve
the failed job, preview proof, receipt and canonical record/journal unchanged.
The source-bound recovery script pins the observed preview, journal000009,
journal000010 and resolution007 hashes. It requires the writer to be reaped and
the exact failure. It performs no append, changes no verifier/policy, then uses
the same policy65/journal62 full replay and records its actual result.

An isolated copy of all eleven actual canonical snapshots and the preview must
reproduce the fork, pass the unchanged lineage checker after relocation, retain
identical preview bytes and reject another genuine branch. A changed preview
hash or existing custody destination must fail before removing the live locator.
No native source, qualification, raw data, estimator, scientific claim, run,
retry, pilot or Stage18 authority changes. Completed measurements are reused.
