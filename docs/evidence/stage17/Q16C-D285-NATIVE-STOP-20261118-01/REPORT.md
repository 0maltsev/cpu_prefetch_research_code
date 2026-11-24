The D285 Q16c family **STOPPED AND RESTORED** on18November2026 at14:09UTC
(17:09Moscow). No automatic retry occurred and no experiment was started by this
status check. The previous completion forecast is withdrawn.

Progress preserved:86native-complete captures, ordinals0–85. Capture ordinal86
(the87th) failed. All87evidence sets, including the failed capture, have
ARCHIVED_AND_RELEASED custody with eight artifacts each. The complete captured
prefix remains on the stand. There are94incomplete positions: one failed and93
not attempted. Do not label the failed checkpoint a successful87th measurement.
Scientific validity remains NOT_ASSESSED: the post-collection independent analysis
was not started after failure. Completed Q16a708/Q16b120 remain preserved.

The top-level failure category ARCHIVE_WORKER_FAILURE is generic. The actual
executor trace says NATIVE_FAILURE: the archived native failure stops the family.
Archiving itself completed for the failed capture. Its checkpoint reports native
stop10, NativeCaptureStop::capture_failed; lifecycle stop16 maps to
ServiceSessionStop::observation_failure. Source:
include/cpu_prefetch/calibration/native_formal_ring_capture.hpp and
include/cpu_prefetch/calibration/service_session.hpp. In the scheduled lifecycle,
observer.before_phase(warmup) returns false before before_observed is set.

Both schedules were prepared and validated, but neither phase was released or
observed-before. No event was attempted, accepted or consumed in either phase;
the four producer/consumer stream artifacts are empty. Node order, both schedules
and control metadata were published. This is a failure of the mandatory initial
observation gate, before any warmup/measurement for this setting. It is unrelated
to a FULL outcome during execution. The exact individual failed observation probe
is not identified by the checkpoint; diagnosis requires inspection of its retained
control observation metadata. No software/hardware cause is inferred here.

Failed setting: L1 linked queue, FAR placement, capacity65536, LLC_RESIDENT,
loadL075; producerCPU0/node0 and consumerCPU8/node1. Warmup5s and measurement1s
were planned. The control artifact is28701396bytes and remains archived on the
stand; no raw streams or control payload were transferred to this PC.

Actual native cleanup was successful: leader_reaped=true, process_group_gone=true,
quarantine not performed, restoration_verified=true. Complete0x1a4 readbacks on
CPU8,1,0 each matched the original0000000000000000 value. Isolation/maintenance
restoration was independently verified at14:09:01UTC. Current services both have
MainPID0; reserved cgroup is absent; root CPUs0–31 and empty isolated list restored.
All observations and failure evidence remain retained. Stage17/EXT007 remain
incomplete; Stage18 remains prohibited. The signed D282 end19November09:16UTC
(12:16Moscow) remains unchanged and grants no automatic continuation.
