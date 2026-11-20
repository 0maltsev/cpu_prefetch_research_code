# EXT007 canonical publication and final metadata replay

Status: canonical resolution007 and journal000010 published; final recovery/replay pending.

Policy65 installation added9 files and independently verified all984 inherited
bound files unchanged. The actual scoped preview passed. Ordinary candidate
validation passed and the CLI appended canonical resolution007/journal000010.
The final replay then correctly detected the saved noncanonical preview as
a second JSON snapshot in the live journal directory. The failed job, all
eleven actual canonical snapshots, preview, receipt and console are preserved
under pre-recovery/. No original canonical bytes have been changed.

D309 preserves only the exact preview outside the live directory with an
explicit old/new locator receipt, then replays the existing policy65/journal62
chain. The actual-snapshot regression reproduces the fork, passes after
relocation with all canonical bytes unchanged, rejects altered preview hashes
and occupied destinations, and still rejects a genuine second branch. All3
focused recovery tests pass; the complete descriptive suite is also checked.
No new resolution, measurement, raw decoding, qualification, pilot or Stage18
action is authorized. Full Stage17 completion remains outside this result.
