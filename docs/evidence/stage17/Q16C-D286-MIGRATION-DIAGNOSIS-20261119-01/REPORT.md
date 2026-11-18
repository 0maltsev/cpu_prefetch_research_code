Q16c diagnosis is complete to the retained-observation boundary; the proposed
compaction mitigation is implemented and its control/restoration verified.
**The historical migration trigger remains unproven. Research is stopped.**
Recorded 19 November Moscow / 18 November UTC. This supersedes the previous
report's statement that the individual failed probe was unidentified; it does
not supersede or rewrite that original evidence.

The failed capture's control archive was decoded only on the stand, with
complete byte/hash reconstruction verification. Canonical control: 28,701,396
bytes, SHA256 `9c480a44a9fa03fa73a6bc725ecc3f2342432abd108be3a685e8bdd37f3b3a4d`.
Physical archive: 1,384,464 bytes, SHA256
`c041d5539f755d47ef2f3889e51bfea7e4cac1468d1dd92f958235302b9114ba`.
Release ledger 72909 SHA256
`f21cfb45dc113b72000a1344fda171e077aa54b022ec138e679b4a9efaa43c7d`.
Only small summaries/proofs were copied to this PC. The original archive,
decoded control and every failed raw artifact remain on the stand.

The exact first rejected observation is WARMUP/BEFORE, region 0 (shared
records/schedules), expected node 0. `move_pages` returned 0/errno0; page
statuses were node0 x15,834 and `-ENOENT` x1. The latter was page1916, byte
offset7,847,936, address125183811260416. It lies in the copied warmup schedule
(schedule offset4,718,592), not queue or node-order scratch. Node-order scratch
is in a separate producer mapping. Mapping, write-prefault, mlock and read-only
protection had succeeded. No phase release/event or environment/control
sampling occurred. The generic native observation stop therefore did not come
from a FULL outcome or an archive failure. `wrong_node` is the observer's broad
gate classification; no page was positively observed on a different node.

The bounded ten-second diagnostic explicitly migrated one page of its own
64MiB private, prefaulted, mlocked, read-only mapping between nodes0/1. It did
not invoke Q15/Q16, alter global controls, change scientific inputs or touch raw
archives. It reproduced 5,111 query statuses `-ENOENT`. After its migration
thread joined, all16,384 pages queried on node0 and every checked page retained
its original content. Unit exited0, MainPID0. This confirms the possible query
race on actual kernel7.0.0-38-generic, **not the historical migration trigger**.
The diagnostic performs explicit migration, not compaction; it does not prove
that the proposed compaction guard prevents all forms of migration.

Linux's query implementation reports `-ENOENT` when no present folio is found;
the primary [kernel source](https://raw.githubusercontent.com/torvalds/linux/master/mm/migrate.c)
supports that mechanism but is upstream, not an exact binary/source identity
proof for the installed Ubuntu kernel. The kernel
[sysctl documentation](https://docs.kernel.org/admin-guide/sysctl/vm.html#compact-unevictable-allowed)
states that the proposed control prevents compaction from moving mlocked pages.
These sources explain the mechanism and proposed mitigation; neither proves
the historical cause. The native observer remains unchanged and fail-closed.

The new guard records actual prestate before any mutation, verifies the
requested0 separately, holds one exclusive lease and restores exact prestate
with actual readback and durable receipt before releasing ownership. Failed
entry, write/publication errors, stale leases, owner death, expired deadlines,
control drift, foreign boots and concurrent owners are covered by tests.
The standalone component has no measurement/qualification/continuation entry.
A future supervisor integration and systemd stop-post recovery are required
before research use; the smoke check already used such stop-post recovery.

Fresh verification:

- `python3 -B -m unittest discover -s tests -p test_stage17_locked_compaction_guard_v1.py -v`:
  14/14 passed locally. Same14 tests passed on the stand.
- `python3 -B tests/test_stage17_q16c_d285_continuation_v1.py`: 6/6 passed.
- `python3 -B tests/test_stage17_q16c_empty_reuse_v1.py`: 15/15 passed.
- Actual root control smoke check: requested0/observed0; restored requested1/
  observed1; ordinary and independent systemd stop-post recovery succeeded;
  unit exited0 with MainPID0 and no stderr. Original lease is empty.
- Native worker/source, C++ behavior and measured code are unchanged. No native
  rebuild, generated-code qualification or sanitizer rerun was necessary for
  this isolated Python control component. These are software checks only.

All86 native-complete captures remain preserved and NOT_ASSESSED, with ordinal86
failed and93 later settings unattempted (94 incomplete total). All87 original
evidence sets retain eight-artifact custody. Q16a708/Q16b120 remain preserved.
There was no validation/measurement retry or new window. The original D282
deadline remains19November09:16:07UTC. All research and diagnostic services have
MainPID0; CPU partition is absent and compaction control has returned to1.

Next steps: obtain the scientific platform decision in
[D286](../../../decisions/0286-q16c-locked-page-compaction-proposal.md), assess
qualification/platform compatibility and prepare a separately authorized
continuation preserving the86-capture prefix, then validate and finish the
matrix/freeze/admission. No run ETA is promised before that continuation's
resource/time/authorization checks. EXT007/Stage17 remain incomplete;
Stage18 remains prohibited.
