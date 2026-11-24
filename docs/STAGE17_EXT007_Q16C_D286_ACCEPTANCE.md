# D286 accepted locked-page compaction amendment

The owner answered **“approve”** to the pending question accepting the exact
[D286 proposal](decisions/0286-q16c-locked-page-compaction-proposal.md), SHA256
`a81997651d5697355f138908ccb0a101ee5b02644607f719d9bfb212645b3142`.
The [acceptance record](evidence/stage17/Q16C-D286-ACCEPTED-20261119-01/owner-acceptance.json)
preserves that scope. The original proposal and its existing evidence manifest
remain byte-identical; this file records its subsequent acceptance.

This accepts `AMEND-2.0.0-pre.3-Q16C-LOCKED-COMPACTION-v1`: prevent compaction
from moving locked pages during a future Q16c family, retain every existing
residency gate, bind actual prestate/readbacks and restore the exact original
value through the owned supervisor and independent stop-post recovery.
Preserve all86 native-complete captures, failed ordinal86, Q16a708/Q16b120 and
their actual platform histories. The original migration trigger remains
unproven. The new control regime cannot be assigned retrospectively to old data.

Approval does not restart the stopped family, authorize qualification or
prefix validation, approve a continuation, or grant another time window.
The original D282 absolute deadline remains19November09:16:07UTC.
The stand check at18November22:32:09UTC observed the original boot,
compaction control1, empty lease and both research services at MainPID0.
No research action or persistent control change accompanied this acceptance.

Next engineering work is supervisor integration, per-capture platform receipts
and qualification/platform dependency assessment. The existing Python executor
starts the native process and receives each final checkpoint over a synchronous
archive channel; the native worker waits for a verified custody acknowledgement
before advancing. Candidate integration seams are the authority check before
the initial process launch, the quiescent checkpoint receipt after a capture,
and the acknowledgement before the next capture. See
`tools/stage17_fixed_action_executor_v12.py:139` and
`tools/stage17_archive_channel_v1.py:136`. These are inspected seams, not a
completed integration or a new native-release qualification claim.

An integration must preserve custody of a failed capture before denying its
continuation acknowledgement. A platform failure must not bypass archival,
reaping or exact restoration. Before a separately authorized continuation,
finish the read-only guard-witness/receipt design, verify failure and supervisor
death handling, assess existing qualification and prefix compatibility, and
provide the complete remaining-work bound and launch ETA. Reuse only evidence
whose dependencies remain established. No completed measurement is to be rerun.
