# D329: fixed S180 stand environment and native placement

Accepted engineering implementation within D310. The180 settings, original
sources, fixed windows, calibration, archive policy, one-attempt rule and24h
operational cap are unchanged. This decision supplies no execution authority.

## Actual platform and owned preparation

The accepted native platform is Intel family6/model62 (06_3EH), MSR0x1a4,
disable mask15 and CPUs0/1/8. The old hardware recovery helper targets06_55H
and CPU26 and cannot be reused. The new fixed adapter verifies actual CPU
identity, character devices and complete64-bit prestate independently before
preparation; requested hardware values are never readbacks. Pin device identity
and refuse restoration if unrelated bits changed. Read back every restored CPU
independently, skip unnecessary writes and attempt the other CPUs and owned
infrastructure even after a device failure.

Preserve the original23863-byte isolation core, SHA256
`49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a`,
as a tracked file. A read-only stand observation confirms the same bytes in the
root-owned v32 qualification helper. Load only that adjacent root-owned,
non-writable source into a private module; there is no input-selected module,
command, CPU, register or restoration backend. Its existing owned systemd unit,
keeper, delegated isolated partition, daemon-reload readbacks, process/inode
checks and apt timer/runtime-mask restoration remain intact. Do not adopt the
old v23 cgroup or any occupied namespace. The eventual qualified package must
bind and provision the new operator and the unchanged core separately.

Use only `cpu-prefetch-recovery-s180-1.service` and its `reserved` leaf. The
D326 prospective placeholder path does not describe that systemd hierarchy.
The corrected v2 ceiling packet changes the requested monitoring paths and
their resulting byte/hash bounds; the original packet remains preserved.
Its archive upper bound is584757218120 bytes and declared stage caps remain
85681 seconds. Ceilings and old hardware observations are not actual sources,
resource admission, elapsed-time estimates or verified current hardware state.

Preparation requires a complete exact session plan, original boot-bound24h
window and finite keeper configuration. Budget120s for isolation preparation
inside the existing600s public-preflight cap, without adding another stage.
Reserve actual native, qualification, independent validation and restoration
time before accepting keeper lifetime. No preparation may begin before the
complete ETA and exact budget have been presented. A fresh actual stand
qualification remains mandatory; copying an old helper does not qualify it.

## Placement before native execution

The public launcher now requires the process-owned prepared-environment handle,
not a callback or serialized success report. After independent isolation and
remaining-lifetime checks, open the actual owned `cgroup.procs` once. In the
single-threaded child before exec, write only its own PID, close its copy and
independently read its kernel membership and controllerCPU2 affinity. Verify
the original partition inode before handoff. Check actual OS thread count as
well as Python threads before pre-exec work. Parent affinity stays owned and is
restored on exit; close its placement FD before removing the group.

The unified hierarchy must have exactly one matching `0::` entry. Unrelated
legacy entries can coexist: this PC has a separate `net_cls` entry. The initial
software test exposed an incorrect whole-file equality check. Preserve that
failure, correct the parser and reject missing, wrong or duplicate unified
entries before native execution. There is no production fixture switch.

## Failure restoration and deadlines

Restore only after held-leader/descendant cleanup and independent kernel
quiescence of the owned partition. A replaced/live group prevents MSR writes;
infrastructure cleanup still runs and its failures remain visible. An expired
window cannot start preparation or dispatch. Context exit also restores an
environment when signature, semantic replay or other admission fails early.
Partial preparation invokes the frozen core's existing owned cleanup. A small
adapter gives that internal cleanup its own120s allowance if the preparation
deadline expired, so a timeout does not itself prohibit restoring timers.
The old core's bytes and ownership checks remain unchanged.

If the original operational deadline has already expired, allow only a bounded
120s emergency unwind. Retain the original window verbatim, record the deadline
failure and `collection_authority_extended=false`. This is mandatory safety
restoration after a failed cap, never a new collection window or successful
exit. A failure, uncertain cleanup or restoration error remains quarantined;
there is no automatic retry. Retain independent CPU, root partition,
maintenance, affinity and deadline facts; no boolean substitute establishes
restoration or scientific validity.

## Verification and remaining gates

Software fixtures exercise actual temporary fixed-offset MSR I/O and actual
child processes, descriptors and kernel membership reads. CPU/device identity
and systemd/cgroup changes are explicit test doubles; no test changes host or
stand hardware. Cover wrong platform/path/prestate, unrelated-bit changes,
per-device failure, live partition, wrong plan/window, incomplete native
cleanup, one-use ownership, FD lifetime, expired-window unwind and expired
preparation internal cleanup. Python development/debug checks and the affected
registered suites verify the integrated code. Preserve the initial placement
failures as software evidence, without classifying them as failed experiments.

The fixed qualified operator/profile, actual EXT008/009 semantic fact producers,
full exact resource admission, actual source/namespace preparation, fresh
qualification and independent pilot scientific validator remain required.
No actual S180 preparation, qualification, measurement, admission or operational
window occurred in this step. Existing EXT007 remains complete; Stage17 remains
incomplete and Stage18 remains deferred.
