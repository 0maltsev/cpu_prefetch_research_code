# D327: S180 parent attempt and custody acknowledgement

Accepted engineering implementation under the existing D310 scope. Connect the
already verified request, native channel, broker, ledger and inverse-custody
machinery in one parent component. No experiment setting, scientific counting
rule, observation, seed, run count, source algorithm, recovery or operational
window changes. This is not a new readiness state or stand execution authority.

## Caller and attempt boundary

The qualified launcher must obtain a D319 VerifiedRequest by checking the owner
signature and exact EXT010 against fresh D322 replay with independently derived
semantics. The new library consumes that immutable value; it does not replace
the signature verifier, construct missing semantic facts or accept a caller
report asserting readiness. In-process Python callers remain qualified code,
not an untrusted configuration or plugin boundary. Test admission values are
explicit fixtures and grant no real permission.

Consume one fixed-name family attempt before dispatch. Require the original
already registered/admitted S180 FAMILY and EXT009, original output path/device/
inode, owner/mode, current boot, original24h window and epoch coverage. Never
create/adopt a family in this operation. Existing native entry/result or existing
complete/partial attempt prevents reuse. The existing exclusive broker lock
serializes consumption and durable create-exclusive metadata publication
prevents overwrite. Marker records the exact request, authorization, plan,
runtime, prerequisites and original window, one attempt and zero retries.

Keep this marker and all parent custody receipts in programme metadata, charged
by the unchanged physical quota accounting and reserve checks. Do not put new
unaccounted retained records in the raw working directory. Parent record size
is at most64KiB. One marker plus180 records fits the existing2MiB per-capture
metadata/checkpoint allowance with room for the other bounded custody records;
the prospective complete resource admission still has to include actual totals.

## Original worker and archive sequence

The component requires the fixed S180 credential-bearing channel, exact original
request/session/plan/programme and initial ordinal, immutable runtime profile,
finite limits and actual supervisor identity model. Re-read the durable consumed
attempt. Open the kernel-owned /proc/<pid>/exe through the held PIDFD/start-time
identity and hash its actual bounded bytes. Require the exact admitted image,
then recheck liveness. Constructor failures latch the channel stopped too.

For each checkpoint, preserve the received native deadline and cap all broker,
custody and decoder work by that deadline and the original authority/window.
Check its specific capture archive allowance, not only the channel maximum.
Run the real fixed broker while the exact native worker is parked. Require
normal broker exit, reaped leader, vanished process group, no escaped children,
no timeout/cleanup overrun and the fixed encode/reconstruction/readback child
count. No JSON cleanup assertion supplied by an input replaces actual supervision.

After the broker closes, independently reopen the exact programme ledger under
its lock. Require the existing family/admission/output path. Reconcile the
original checkpoint, current released states, complete canonical/physical
bindings, header identities, archive hashes, storage extension and actual
CUSTODY_RECEIPT registration. Compare the broker's returned registration to the
actual ledger record; independently derive continuation status. The parent
metadata check does not itself perform another inverse reconstruction: the
broker already completed that work before durable release.

Publish the bounded parent receipt durably inside the quota, release the broker
lock, check the original deadline and only then send the matching native ACK.
Normal complete custody permits continuation. Retained failed/partial data
receives only the existing failure ACK, which stops native execution. Any
exception, including changed attempt, wrong image/profile, insufficient broker
input limit, custody/hash/registration failure or metadata publication error,
latches parent/channel stopped and sends no success ACK. No automatic retry.

## Verification scope and remaining integration

Tests use the actual separately linked channel endpoint, accepted native encoder,
sealed Python broker/decoder, filesystem, shared quota, original ledger and
kernel supervision. Admission is explicitly synthetic; no production measurement
entry, research source generation, stand access or hardware action is used.
Success, failed/partial evidence, independent archive corruption, changed attempt,
wrong native image/profile, expired/foreign identities and one-attempt retention
are exercised. Python development/debug-allocation execution supplements the
ordinary run. C++ and the clean34247ce native image remain unchanged; their
existing native sanitizer and generated-code evidence is not relabeled as new.

The first managed test attempt was interrupted after an early supervision/setup
error; its diagnostic remains. Running directly on the host also demonstrated
the mandatory /proc/1/ns/pid permission failure. Use the established isolated
user/PID namespace with mounted procfs and real IPC, without host sudo. Test
lease acquisition is now inside its cleanup guard; failed setup cannot leave
that test owning the lease. No supervisor check is weakened or skipped.

The executable outer launcher still must pin the full qualified source/profile,
perform fresh semantic replay, prepare verified sources, enforce whole-tree
limits and the original window, own native dispatch/console/process cleanup,
and independently verify hardware/isolation restoration. Pilot scientific
validation and scoped exit remain separate. This component supplies attempt
consumption and the archive/ACK loop, not that complete orchestration. No stand
preparation, qualification, pilot or operational window started in this step.
