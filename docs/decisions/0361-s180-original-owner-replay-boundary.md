# D361: preserve original-owner replay in the root S180 operator

Accepted engineering integration; no scientific method, observation, source,
calibration, permission scope, hardware control or operational limit changes.

The S180 hardware controller requires root. The original accepted journal's
transport snapshot requires the original UID1000 identity and unchanged private
key ownership. Actual read-only stand verification rejected root at this guard;
changing only effective credentials also broke the original procfd SSHSIG
handoff. An independent process with full UID/GID1000 credentials passed all
seven original resolutions and three transitions. Preserve these guards and
the original key, journal, archive, signatures and reader implementation.

`stage17_s180_owner_replay_v1.verify_original` forks one fixed supervised reader
from a single-threaded root parent. Production always drops all real/effective/
saved UID/GID fields to1000 and clears supplementary groups; the parent keeps
its root credentials. The child uses CPU3,8GiB AS,256MiB per-file limit,1024 FDs,
no core dumps, ordinary owner procfs accessibility and a checked parent-death
SIGKILL guard. A READY/GO barrier permits the parent to verify actual kernel
credentials, session, birth, cgroup, affinity and resource limits before replay.
The original validator is called with the actual current UTC time and synthetic
evidence disabled. A private UID0 seam exists solely for one-ID namespace tests;
the public function exposes no credential, backend or command selector.

The original accepted89.7MB archive is snapshotted by the legacy reader. Its
temporary-file bound is separate from the32MiB returned-JSON ceiling. Console
capture remains16KiB. A256MiB temporary-file limit is an engineering ceiling,
not an observed archive size. The600-second preflight bound reserves120seconds
for cleanup. A fully sealed canonical memfd carries only verified data. The
parent requires actual exit0, reap, group disappearance, no escaped descendants,
no signal/overrun and unchanged parent credentials. It closes inherited lock
descriptors without unlocking shared open-file descriptions. Report files and
serialized dictionaries cannot construct the resulting owned view.

Do not serialize live legacy release/context objects. The fixed projection
retains every original input/resolution identity and hash, original state and
counts, EXT002 stand ID, EXT003 trust, the six EXT006 release/inventory/locator
facts used by software compatibility, and the three EXT007 descriptive-scope
facts used by S180. Paths become data strings. Missing required fields fail;
unknown objects in omitted legacy context do not acquire authority. The
original validator still independently checks the complete historical evidence.

Verify the raw original journal bytes and its directory plus all ten original
record identities before replay. Match returned resolutions to the original
record's **input_id and resolution_id**, not list position: the actual historical
admission order is001,002,003,006,004,005,007. Preserve each original record hash.
Same-process/same-boot views recheck all stamps and reject subsequent changes or
new journal publication. The original trailing newline is valid historical JSON
and remains part of its raw SHA; the historical JSON reader parses those bytes.
IPC frames use the current canonical encoding. No key bytes are returned.

The outer qualified package still authenticates the fixed source closure and
all six replay locators. This read-only bridge grants no hardware, experiment,
generic pilot-readiness or Stage18 authority. Failed software checks and their
cleanup evidence remain retained. Actual source generation and the original
24-hour window remain unstarted during this implementation and verification.

Correction to D360's packaging assessment: its registry change is outside the
archive broker's29-module closure. A clean42fc51b component rebuild has all35
payload files byte-identical to D359's877271c component, including profile
SHA23fac285def38a913d4fbb2727eebdb4cda0a18a8f9352bfa9aafa6bee3ca9f6.
Only the package manifest's source revision changes. Reuse the already verified
stand877271c archive component unchanged; bind the new parent/analysis/owner
reader sources in the outer operator profile. This corrects the earlier
assessment without rewriting the historical verification inventories.

Evidence: [verification report](../evidence/stage17/PILOT-D361-OWNER-REPLAY-20261123-01/REPORT.md).
