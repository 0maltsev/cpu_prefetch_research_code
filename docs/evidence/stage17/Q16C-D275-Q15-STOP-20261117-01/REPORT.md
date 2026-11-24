# Stopped at Q15 startup; bundle ownership repaired without a retry

The Q15 session launcher started17November2026 at16:48:33UTC (19:48:33Moscow)
and exited1 before publishing a Q15-R result. Its exact error was:
`bound input is not an owner regular file`. The automatic Q16c handoff observed
the qualification failure and stopped. Both units are failed/stopped, with no
automatic retry. Q16c captures remain0/180; the new family was not registered.

This was a deployment ownership error, not an empirical measurement failure.
The extracted frozen919c486 bundle's files were still root-owned. The earlier
directory-only ownership correction allowed authoring but omitted the executable
files. The immutable executor's `_read_bound_regular` correctly rejects a bound
worker whose UID differs from the actual evidence owner's UID1000. The session
controller pins that worker before writing its durable attempt marker or
spawning it. The actual Q15 output root has no Q15 attempt or terminal artifact.
No native Q15 worker or Q16c capture started. The failed controller launch and
all original evidence remain retained.

The complete new bundle membership was checked against its unchanged inventory:
4119 indexed files plus `BUNDLE_INVENTORY.json` and `SHA256SUMS`,4121 total files
and4441 total entries. Ownership of4440 entries was corrected to UID/GID1000.
Every file's size, SHA256 and mode was compared before/after and is unchanged.
The first repair check had assumed4120 files and stopped before mutation; the
actual inventory-derived membership corrected that engineering assertion.
No verifier guard, executable, protocol, scientific input or accepted limit was
changed. The same `_pin_worker` operation that failed now passes as UID1000 on
the actual5048256-byte qualified worker1baa213a, without executing its bytes.

The original qualification failure guard restored infrastructure at16:49:10UTC.
Its receipt reports no errors, root restoration and maintenance restoration
verified, and the isolated partition absent. A subsequent independent read-only
check confirmed the original CPU/cgroup state, all maintenance unit states and
MSR0x1a4 readbacks on CPUs0/1/8 against the previous signed complete prestate.
The near/far clocks both passed once and remain preserved, together with all360
sources, all180 actual layouts,708 Q16a and120 Q16b reports. No completed
measurement or raw validation was repeated. Failed/raw evidence remains on the
stand; only these small reports are copied to the PC.

The owner explicitly requested stopping after a Q15 or Q16 failure. Therefore
no qualification or collection was restarted after the repair. A reviewed
continuation must address the restored isolation, original qualification
subdeadline, remaining original global window, current signed authority and
the exhausted controller-launch allowance before another experimental action.
Neither approval nor a new24-hour window is inferred from the repair. The
original hard deadline remains18November10:39:42UTC (13:39:42Moscow).
Scoped freeze and EXT007/Stage17 exit remain incomplete; Stage18 is prohibited.
