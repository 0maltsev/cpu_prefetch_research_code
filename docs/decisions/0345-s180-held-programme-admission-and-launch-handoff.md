# D345: one held programme replay across short admission

Accepted engineering implementation under D310/D321/D331/D344. Native343 bytes,
scientific design, original seven inputs, all completed calibration/raw evidence,
archive format/quota, sampling/durations and original24-hour cap are unchanged.
This fixes custody-admission construction cost; no operational start is issued.

## Evidence and scope

D326's actual79869-record locked read-only replay/accounting took30.42seconds.
D344/D331 opened that programme repeatedly during short signed metadata work.
Repeating its full replay for preparation, append, replay and authorization could
exhaust the original120-second admission lease before native execution. Keep one
real custody lease across admission; do not enlarge or reset that short lease,
skip initial replay, trust a serialized report or drop historical evidence.

`own_programme` opens the existing S180-aware store once under its actual broker
lock, performs the unchanged full chain/transition replay and independent physical
accounting, and inspects the original reserved FAMILY. It requires empty native
output, no pending capture, no unreleased source/reservation and the exact
programme/plan/scope. It creates/adopts no root or FAMILY and writes no ledger.

Record protected complete filesystem stamps for every programme file/directory,
including normally quota-exempt working/raw/spool objects, without reading raw
payload bytes. The read hook captures stamps around each byte-verified historical
metadata read, and the final snapshot must match those originals. Inode, device,
size, mtime, ctime, link count, type/mode and actual UID are retained. The initial
read/snapshot boundary is checked before the owner is usable.

Later checks keep the original lock FD/inode and process, verify the same root,
and stat every original object. Parent-directory ctime/mtime/inode changes catch
new/deleted/renamed objects; original file stamps catch in-place alterations even
when size is unchanged. No full historical JSON reparsing is needed while the
same actual lock and snapshot remain held. Resource admission still recomputes
live filesystem/memory capacity and original physical quota accounting. Failure
latches ownership; restoring changed bytes cannot revive it.

Preserve existing programme ownership. The stand's accepted programme root and
broker lock actually belong to UID1000; the new controller is root. Do not
invent root ownership or chown/chmod historical evidence. The protected actual
UIDs/modes are observed and continuously checked as part of the snapshot.
An initial read-only probe caught the overly strict root-owner assumption before
any real preparation; the corrected/final probes preserve every original byte,
owner, permission and ledger entry.

## Distinct preparation deadline, lifetime and single publication

Require an explicit remaining public-preflight preparation deadline, at most600s,
inside the original ownership lifetime/window. Check it during actual metadata
reads and snapshot preparation. The qualified outer must account for this work
and namespace/history work within its existing aggregate public-preflight budget.
It is not a second600-second allocation. No qualification or source work is
hidden outside the original operational window.

After timely preparation, retain the lease for its separately declared lifetime,
at most the original day/custody deadline, so it can span qualification and then
short admission. This is the same distinction as a source bank lifetime versus
its loading/preparation deadline: it does not renew a preparation, admission or
operational budget. D344/D331 still enforce their original at-most120-second
metadata leases independently.

The admission store refuses ordinary writes. After the actual signed EXT009
view exists, allow exactly D321's original immutable resource-binding metadata
publication through the charged original store operation. Match actual scoped
EXT008/009, plan, output inode and original window first. Confirm that only the
expected new metadata file and its directory changed, update that snapshot and
retain the exact EXT009 binding. No ledger, raw byte, original receipt or other
object is changed. A second publication, orphan, incorrect view or unexpected
mutation fails; it cannot be adopted or repaired automatically.

## Actual launch handoff

Both scoped semantic owners must share this same programme owner, source bank,
family and environment. After full live journal replay and actual admitted
authorization verification, the public launcher independently queries the exact
sealed native image's clean identity. Only then does the fixed scoped router
release the original programme lock once against that exact EXT010/EXT009/window
lineage. A closed owner can support no further live admission.

The original launcher next opens its normal writable programme store, performs
its own fresh custody replay, verifies the immutable resource binding and consumes
the one durable family attempt before exec. This avoids an inherited-lock
deadlock and retains the original replay adjacent to attempt consumption.
Historical signed-journal inspection remains possible without claiming a live
lease. There is no alternate callback/backend selected by input data.

Close only the held descriptor with the original file identity. If an unexpected
external close reused that FD, quarantine its Python stream too, so garbage
collection cannot close the foreign replacement. Context failure never clears
partial evidence or an occupied namespace. Service-level failure/stop-post,
restoration, source lifetime and final scientific validation remain the qualified
outer operator's responsibility.

Declare2MiB/16 additional inodes for this ownership/report/handoff metadata in
the authenticated outer commitments, within existing limits. In-memory complete
stamps are bounded by the finite inventory limit. No new archive quota or
second raw-domain claim exists.

## Read-only stand timing and software checks

Final23November14:43:54UTC probe:79869 original records and the same ledger tip;
100295 complete filesystem objects,79870 original verified metadata files.
One full replay took30.054s, initial complete snapshot2.200s, three held stamp
checks0.599/0.596/0.597s and fresh physical accounting1.309s. Original quota charge
is unchanged579599806464 bytes over100265 policy-accounted objects. These are
metadata engineering timings, not empirical queue performance or whole-run ETA.
No payload, namespace/source preparation, qualification, ledger write, actual
admission or operational window occurred. The probe exercises the same loaded
component's read/snapshot core without calling its actual admission factory.

Tests cover one-time replay/real competing lock, every original stamp, same-size
tamper and unknown objects, ordinary-write rejection, exact single EXT009 update,
original owner preservation, distinct finite preparation budget, closed/expired
and forged owners, root/FD replacement, one-time release, signed EXT008 and
actual frozen-image identity before lock reacquisition. Tiny disjoint source and
hardware/qualification boundary fixtures remain explicit; no unit result
qualifies the stand. No production C++ changes or new native sanitizer path.

Evidence: [verification report](../evidence/stage17/PILOT-D345-ADMISSION-CUSTODY-20261123-01/REPORT.md).
