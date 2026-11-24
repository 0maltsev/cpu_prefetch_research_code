# Q16c stopped at cold descriptor admission; native qualification retained

The initial native Q15-R and Q15-W both passed. Q15-W verified hardware
restoration; the controller exited0 and was reaped. D278's owner-signed third
administrative edge also committed successfully. Qualification exited0 at about
20:12:51UTC17November. Both previously passed clocks remain retained.

The success-only Q16c supervisor then entered construction. It exited1 after
44.63seconds with `cold archive daycap overlay: packet source namespace differs`.
This is a cold software integration defect, not a capture or time-budget failure.
The new packet2 constructor copied the old archive-preparation descriptor's
seven `sources` bindings without relocating their packet1 paths. The archive
verifier correctly required every source to reside in the actual packet2 root.
The missing integration test was relocated archive-source admission across the
fresh packet namespace; byte custody and independent loader tests did not cover it.

No Q16c family was registered, no request/signature was published and no Q16c
native capture or warmup started. Q16c remains0/180. The first-failure rule
stopped dependent work, with no automatic retry. Original failed construction,
partial metadata and descriptor remain preserved. No source, clock, Q15,
Q16a708 or Q16b120 work was repeated or invalidated.

Restoration is verified with no errors. The reserved cgroup is absent, online
CPUs are0–31, isolated CPUs are empty, the supervisor has MainPID0 and no
cpu-prefetch unit is running. All owned construction children were reaped.
Native hardware restoration was already proved by the passed Q15-W and its
completion receipt; no later native action changed it. The exact failure and
restoration bytes/hashes are in `failure-export.json` and the individual reports.

A read-only owner process reproduced the original namespace rejection. It
verified all7 packet2 helper sizes/hashes against their original bindings,
changed only the7 paths in private memory, and the complete existing descriptor
validator accepted the corrected object. No production input, source, quota,
archive, signature, measurement or raw validation was changed or restarted.
This proves the path-only descriptor correction; the unfinished full input
construction/signing/collection is still unverified and stopped.

The next repair is to bind a versioned relocated descriptor and resume only the
unfinished administrative construction in fresh exclusive output/supervisor
namespaces. Preserve all partial/failure evidence, the exact frozen180-setting
plan and all original signed records. Reuse passed Q15/clocks only after fresh
source/boot/hardware/isolation/custody/resource checks; do not repeat them for
this metadata-only defect. Any continuation requires a new owner instruction
following the failure-stop rule and must fit the existing D277 deadline.
The one window still ends19:52:53UTC18November (22:52Moscow); it is not reset.
No continuation, new window or experimental retry was performed in this turn.

EXT007 and Stage17 remain incomplete. Calibration handoff/freeze, the pilot
plan/storage/authority and actual pilot/Stage17 exit evidence still remain.
Stage18 is prohibited. All raw data and failed evidence stay on the stand;
only small reports/manifests are stored on this PC. Verified duplicate software
transports were already removed and their stand copies remain preserved.
