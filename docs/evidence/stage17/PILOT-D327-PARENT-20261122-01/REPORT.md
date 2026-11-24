# S180 parent attempt and archive/ACK bridge

Implemented quota-accounted one-attempt consumption and the parent checkpoint
sequence in stage17_s180_parent_v1.py. A normal native ACK follows actual broker
completion, child cleanup, independent ledger/archive verification and durable
parent receipt publication. Failed/partial native data is retained and receives
only a stop ACK. Exceptions latch the parent and channel stopped; no retry or
success ACK is allowed.

The component checks the original request/plan/session/window/output, exact
programme path, consumed attempt, pinned actual worker image and admitted
archive profile. It binds all cold work to the original checkpoint deadline.
Attempt and parent records live in existing programme metadata so quota/reserve
accounting includes them. No new ledger kind or archive quota is introduced.

Verification uses a separately linked native channel fixture with synthetic
data, the real encoder, sealed broker/decoder, original ledger and kernel
supervision. Twelve parent cases cover normal ACK, failure/partial stop ACK,
one-attempt retention, partial markers, changed attempts, wrong boot/output/
programme/image/profile, broker input exhaustion and corruption detected only
by the independent registry. Admission is an explicit caller fixture; these
tests do not claim real semantic admission, fresh signature verification or
source provenance. D319/D322 remain required upstream.

Final affected registered verification passes seven suites,76 cases: parent12,
broker19, journal15, authority12, reservation8, channel5 and checkpoint5. The
final12 parent cases also pass Python development mode/debug allocation with
no warnings. Repository format/protocol/schema/canonical/provenance checks pass.
C++ and the frozen34247ce worker are unchanged; no additional native sanitizer,
codegen, empirical performance or stand qualification claim is made.

Initial managed/host diagnostics are retained. A direct host run failed the
mandatory /proc/1/ns/pid permission check. The established isolated user/PID
namespace with mounted procfs and real IPC passes without host sudo or weakened
supervisor checks. The test now acquires its supervisor lease inside its cleanup
guard. The initial interrupted run is not represented as a successful test.

**No stand access, schedule preparation, qualification, pilot capture or new24h
window occurred.** Completed Q16a708/Q16b120/Q16c180 remains preserved. The outer
executable launcher still needs qualified semantic/profile replay, verified
source/resource preparation, native dispatch and console/process ownership,
hardware/isolation restoration and independent pilot scientific validation.
Before stand preparation it must present the complete ETA and enforce the
original24h budget. Stage17 exit and Stage18 remain pending.
