# S180 environment and placement checkpoint

The fixed stand-environment adapter and native cgroup placement are implemented
and software-verified. **Stage17 is still incomplete. No S180 operational window,
actual preparation, qualification, pilot or scoped admission started.** EXT007
and the frozen34247ce native image remain unchanged.

The adapter binds the actual accepted Intel06_3EH CPU0/1/8 mapping and the
original root-owned isolation core. It owns finite managed isolation, checks
actual MSR/device prestate, supplies a single-use partition control FD and
independently restores hardware, CPU isolation, maintenance and parent affinity.
The public launcher now requires this live owned handle. The child writes only
its own PID before exec, reads its actual unified membership and verifies
controllerCPU2 affinity. Wrong/duplicate membership fails before execution.

Initial software placement checks rejected this PC's hybrid cgroup layout:
an unrelated legacy net_cls entry precedes the unified entry. The failure and
diagnostic are retained; exact matching now applies to the single unified entry.
This was a software-fixture failure, not a failed stand run. Preparation-timeout
cleanup and expired-window emergency unwind are covered separately. Emergency
unwind retains the original deadline failure and cannot extend collection or
produce a successful exit. See [D329](../../../decisions/0329-s180-fixed-stand-environment-and-native-placement.md).

All **125 cases in10 affected registered suites pass** in73.66s. All16 environment
cases and18 launcher cases pass Python development/debug allocation. Temporary
files exercise real fixed-offset I/O; real child processes, descriptors, channel,
archive and kernel membership reads are used. Device/CPU identity and systemd/
cgroup changes are explicit platform doubles: this is not stand qualification.
No production C++ changed, so the frozen native/codegen and D328 endpoint's
existing sanitizer proof are preserved. AST, whitespace, format, protocol,
schema, canonical and provenance checks pass.

A read-only SSH survey at22November21:17UTC confirms the original v32 journal
SHA9a7766e806b872133dbd0f6a746d75ae315dae69bc8c5e7b9bad9f95c9c003e0,
the original23863-byte isolation source SHA49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a,
unchanged boot, CPUs0–31, no root isolation and inactive package services with
their timers active. These selected observations do not establish full current
restoration, qualification or resource admission. No hardware or maintenance
write was performed on the stand.

The prospective v2 packet corrects D326's requested placeholder monitoring path
to the actual managed unit. Cold native description passes for all180 settings.
Archive ceiling584757218120 bytes, requested process/page caps164652228608 bytes
and85681s declared stage caps remain prospective bounds. No source was generated,
and old hardware values remain explicitly unqualified references. These limits
are not an elapsed-time estimate. The original D326 packet is preserved.

Verified duplicate packet metadata totaling3298478 bytes was removed from the
build directory after evidence publication; no raw moved to the PC and no stand
raw was deleted. The fixed qualified operator/profile, actual semantic fact
producers, independent pilot scientific validator and exact live admission are
still required. Present the complete ETA before actual preparation/qualification;
retain the single24h window and stop-on-failure rule. Stage18 remains deferred.
