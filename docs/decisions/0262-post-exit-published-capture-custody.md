# D262: Explicit post-exit closure of the interrupted D260 custody handoff

- Status: ACCEPTED engineering implementation of the approved D260 recovery
- Date: 2026-11-16
- Actual scope: E26 Q16b original53ef4b, completed capture16 and failure332662f only

D260 requires the interrupted final custody handoff to complete after all17
retained captures pass independent scientific validation. All six capture16
archives are already published; only the control source remains PUBLISHED.
There is no missing measurement, partial encoding or reason to restart a worker.

Use a separately signed, prospective storage-recovery authority binding the
actual original plan/failure/checkpoint, all17 validated reports and their
operator/reader provenance, original restoration, current worker absence,
ledger tip, exact recovery source/decoder profile and finite time/resources.
Use the already trusted owner principal/key; never invent a new owner identity.
The qualified signed request and all earlier evidence remain unchanged.

The new explicit post-exit primitive can only close sources already in
PUBLISHED/RELEASED states. Require one pending checkpoint, original family
device/inode, exact retained/native checkpoint, actual original source and
physical archive bytes, no unrelated pending custody, retained exact proof
bytes and a raising current post-exit verifier. Reject SOURCE_BOUND, RESERVED,
VERIFIED, RELEASE_INTENT, missing/changed source, absent proof or returning a
boolean as a substitute for verification. No encoder/retry is supplied.

Adopt only that authenticated original checkpoint/source context. Record an
explicit RECOVERY ledger entry binding the retained proofs and honest
POST_EXIT_ALREADY_PUBLISHED_ONLY mode. Reuse the original guarded working-copy
release, actual independent inverse, source hashing, durable intent, no-overwrite
hold and unlink checks. Publish the ordinary custody receipt only after all
sources reach RELEASED. Original failure and the entire preceding ledger stay
retained. Any new failure stops and leaves incomplete state for separate review.

This post-exit condition is distinct from the original parked-live-worker
handshake. Do not instantiate a fake PinnedWorker, report a live acknowledgement,
reset the program, replay an encoder or manufacture family success. Custody
closure still reports scientific_validity=NOT_ASSESSED; the independent17-report
validation remains its own authenticated evidence. It grants no new measurement
authority and does not start D260's24-hour experimental window.
