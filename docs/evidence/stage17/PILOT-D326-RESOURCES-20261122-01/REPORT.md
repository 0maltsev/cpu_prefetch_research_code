# S180 prospective resource packet and deadline repair

The unchanged native34247ce worker accepts the complete180-setting ceiling
packet and its bounded replacement. No original source is generated and no
represented array is allocated. The original Q16a708/Q16b120/Q16c180 results
are unchanged. Stage17 remains incomplete; no pilot or operational window started.

| Planning quantity | Result |
|---|---:|
| Original full control-plan metadata |3321611 bytes, SHA25636c15f402c7f20240da6b36472b9d0c56bcade8c1024604d0b1bd3deaef19a44|
| Bounded sizing packet SHA256 |f7d1f971f49fd1efbda1a4a83eab88fa85c5377d00c194a3242c4bedcdf3088f|
| Native image SHA256 |7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc|
| Canonical family output ceiling |582166200820 bytes|
| Archive family upper bound, no ratio credit |584757180200 bytes|
| Largest canonical capture workspace |4815262901 bytes|
| Largest symbolic cold heap envelope |6586440992 bytes|
| Necessary native minimum plus cold heap |18061482165 bytes|
| Requested native ceiling |68719476736 bytes (64GiB)|
| All requested process caps plus sealed pages, conservatively summed |164652228608 bytes|
| Declared native family watchdog |47281s|
| All declared stage caps |85681s (23h48m1s)|
| Margin within original24h cap |719s|

The count basis is twice the expected fixed-window arrivals, rounded upward.
It is an engineering capacity ceiling, not a statistical bound. Sources remain
null; the existing planner rejects converting this packet to a collection plan.
Actual counts must fit without clipping/reseeding/retry. All resource admission,
execution, measured-ETA and Stage18 flags remain false. Profile references and
60s recovery are prospective declarations pending actual qualification.

The initial local cold query rejected an extra legacy monitoring hardware field.
The corrected builder whitelists the exact seven monitor fields and checks
hardware separately. The regression deliberately reproduces rejection at the
actual native boundary. An initial synthetic-control test could not cross the
worker's immutable blueprint gate; tests now use the exact original metadata
fixture, avoiding a patched native contract. A later test incorrectly asserted
all environment paths were cpuset paths; its corrected assertion checks exactly
the five relocated paths, preserving other observations. Initial diagnostics
are retained; none was a stand qualification or experiment failure.

D324's owner lifetime was incorrectly reused as native setup deadline. The
frozen worker requires its source loading deadline within plan.setup_ns.
The repaired Python API requires a separate explicit deadline within both the
existing owner lifetime and setup budget. A24h-lived bank accepts only a short
loading interval, with no lifetime renewal. Fifteen source-owner tests pass,
including real child/sealed-FD and signed-journal integration. No C++ or frozen
native byte changed, so no new native sanitizer/codegen claim is made.

Eight new resource tests pass against the actual frozen worker. Six registered
affected suites pass,67 cases total: planning3, authority12, journal15,
provenance14, owner15 and resource8. Required repository checks pass. Commands,
complete outputs, exact metadata and read-only observations are retained here.

## Stand observations

Read-only hardware observation records4096-byte pages,64-byte cache lines,
GenuineIntel family6/model62, CPU0/1 on node0 and CPU8 on node1. All three
observed MSR1a4 values are0. This is not qualification.

A separate root child raised only its own RLIMIT_MEMLOCK from8MiB to64GiB,
verified it, restored8MiB and exited. It allocated/locked no mapping and changed
no global configuration or hardware state. Future actual worker limits remain
unverified.

Original custody code transported over SSH stdin replayed79869 records under
the existing exclusive broker lock, with no ledger writes. Ten original
families, no pending captures, no unreleased artifacts and no outstanding
reservations were found. Its physical-accounting charge is579599806464 bytes
over100265 objects; free space6276437209088 bytes. Q+W+S+R remaining policy
requires6262213783552 bytes, leaving14223425536 before unrelated reservations.
Adding the new archive bound would bring programme usage to1164356986664 bytes,
below6TB. This selected read-only replay is not current qualified admission or
proof that unrelated reservations do not exist. It did not read/revalidate raw
payloads, register the pilot family, prepare sources or start a24h window.

Remaining: enforceable whole-tree resource/time/recovery controls, qualified
semantic producers and parent/profile, actual sources/registration, scoped
EXT008–010, conditional qualification, one pilot, independent scientific
validation and restoration/exit. The stage caps above are not an elapsed-time
prediction; the complete ETA must be presented before actual stand preparation.
