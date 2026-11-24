# D321: reserve the S180 directory before resource admission

Accepted engineering fix under D310 S180. The signed plan/resource/authorization
route must obtain a real output inode without inventing an EXT009 digest or
bypassing archive admission. No scientific setting, capture, protocol, storage
quota, independent-copy claim or operational deadline changes. Native revision
34247ce and its D320 generated-code evidence remain unchanged.

## Confirmed circular dependency

D319 requires EXT008 and EXT009 to bind the exact output path/device/inode.
The original D316 S180 store requires EXT009's resolution digest before creating
that output directory and publishing its FAMILY record. Thus the parent cannot
prepare those signed inputs in their required order. The original81c4838 store
rejects an explicit unknown EXT009 with `invalid SHA256`; bypassing its orphan
directory rule or supplying a placeholder hash would not solve admission.

Separate directory identity from resource/capture permission. A prospective
directory reservation is metadata preparation and grants no measurement or
archive authority. The later admitted EXT009 must be bound independently before
the S180 store can prepare any capture.

## Explicit two-phase route

`ProgramStore(..., ext009_resolution_sha256=None).reserve_family()` creates one
exclusive S180 directory using the existing D233 FAMILY transition. The new
storage-extension/2 document binds the exact D310 approval/blueprint, program
scope/family/domain and unchanged shared6TB quota,512GiB workspace,256GiB scratch
and16GiB reserve. It explicitly requires admission before capture, records no
independent backup and grants no execution/Stage18 permission. There is no
invented or zero-filled EXT009 value.

A durable immutable directory-reservation/1 receipt binds that extension, the
actual FAMILY record, path/device/inode and historical `admission_bound=false`.
This is an observation of the reserved directory, not fresh hardware state or
a later readiness flag. It stays byte-identical after subsequent admission.
It lets the scoped semantic producer bind real output identity in EXT008/009.

After the qualified parent has authenticated the actual EXT009 record, it
reopens the store with that exact digest and calls `bind_admission()`. A separate
exclusive storage-admission-binding/1 receipt binds EXT009 to the original
reservation. It is a binding supplied by the qualified caller, not independent
semantic validation or execution authority. The directory must still be the
original owned FAMILY directory without group/world write access and empty
of attempt/capture data.

Only after this receipt exists may `prepare_family` enter the reserved route.
The store checks its exact canonical bytes against the caller's actual EXT009
digest and original reservation. It repeats those checks at the family scope
boundary used by capture/custody verification. Missing, partial, changed or
foreign admission evidence cannot authorize capture or another ACK. Native
request, context, wire protocol, producer/consumer output and codec are unchanged.

Both publication steps are durable/exclusive/quota-accounted using the original
metadata/FAMILY primitives. They never adopt orphan paths, overwrite partial
metadata, reset the program quota, register another S180 family or retry. An
interrupted reservation/admission remains evidence and needs explicit recovery.
The private directory-creation guard is confined to that one cold method and
cleared in `finally`; it is not an input/backend/CLI permission selector.

## Compatibility and verification

The extension/1 one-phase path remains supported with its original known EXT009
binding. Original D233 ledger kinds, base store, scope and historical records
are unchanged. Base readers can still replay the shared program and use a
historical family; they cannot adopt the S180 extension as an ordinary family.
All new metadata is charged to the same program physical quota.

Eight real filesystem tests cover inode identity before admission, capture
rejection, durable one-time binding, legacy replay, one-family/no-adoption rules,
partial/wrong/missing admission, pre-admission data, replaced directories and
unsafe directory permissions. The initial software fixture used the small /tmp
tmpfs and correctly failed D233's16GiB reserve before exercising the change.
The corrected fixture uses the real workspace filesystem; capacity is not mocked
and no production reserve was weakened. Initial errors remain recorded.

All18 actual sealed broker/codec/native-channel tests pass across both the
original one-phase and new reserved-directory paths, including complete inverse
byte/hash readback, failed/partial/discrepant evidence and stop/no-ACK outcomes.
An additional targeted actual-broker test prepares a valid admitted scope, then
changes the admission receipt after successful archival and verifies that the
registry rejects it specifically for mismatched EXT009 before continuation.
Twelve actual SSHSIG authority tests pass, including a new integration that
reserves a real inode, binds EXT009 and then signs/verifies the unchanged D319
request contract. Admission views in those tests remain explicitly synthetic;
filesystem, ledger, crypto, broker and codec operations are actual local tests.

No C++ source, worker binary or measured-loop behavior changes. Native codegen
and sanitizers are preserved without rerunning qualification or measurement.
This Python change still requires a new qualified administrative source closure
before real use; it does not update or reuse a sealed closure silently.

The scoped semantic/journal producer, executable parent/profile and actual
source/resource/time inputs remain required. No stand access, schedule
preparation, qualification or operational window occurred in this step. Completed
calibration remains preserved. Stage17 is incomplete; Stage18 remains deferred.
