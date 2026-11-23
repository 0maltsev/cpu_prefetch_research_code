# D336: separately scoped signed Q15-R/W inputs for S180

Accepted engineering implementation within D310/D333/D335. This is the signed
input boundary for fresh qualification, not its collector, fact producer,
complete operator/profile or an actual qualification. No stand action starts.
Scientific methods, sample counts, hardware limits and original data stay fixed.

## Preserve the accepted runtime history

The legacy Q15 controller selects its worker from the authenticated EXT003
runtime record. That record predates the frozen current34247ce worker. Do not
retarget it, rewrite the original seven resolutions, or claim that it admitted
another executable. Retain the legacy controller and all its checks unchanged.

The new S180 Q15 authorization schema separately binds the exact6151832-byte
frozen worker, its34247ce source revision and a qualification operator/profile
leaf. The leaf ID is D310-S180-Q15-QUALIFIED-PROFILE-v1; its digest must come from
the qualified parent's independent package verification. Its existence or
qualification is not established merely by signing a digest. In the native v4
carrier, the historic source_resolution_id/source_resolution_sha256 fields carry
this explicitly separate profile leaf, not an original EXT003 journal record.
The separately signed source revision is retained in the new authorization;
the unchanged compiled v4 release carrier has its original six fields.

## Trust, context and phase separation

The qualified caller supplies independently derived live qualification context
and the actual authenticated original-seven replay. Never derive that expected
context from an authorization document. Check exact stand identity, original
seven identities/order, descriptive EXT007 scope and owner trust rooted in
EXT002/003. Verify the actual SSHSIG bytes with the admitted allowed-signers,
principal and namespace. Evidence cannot choose a key, command or trust root.

Owner authorizations bind the S180 plan, original24h boot/window, original clock-
qualification start/deadline, output directory identity/protection, current
runtime/profile, phase inputs and separate request/attempt identities. Require
the qualification stage already started and still live, at most1800 seconds
within the original window. Require UTC authority conservatively cover that
original deadline. No reset, retry, pilot, calibration replacement or Stage18
permission follows from these Q15-only authorizations.

Q15-R binds its qualification/session/attempt and independently observed CPU0,
node0,4096-byte base pages and positive whole-page local LLC geometry. There is
no guessed/default LLC value. Q15-W requires a separate signature over its
actual R attempt/result hashes, the same live session and all original full MSR
values in CPU0/1/8 order. Retain unrelated MSR bits; original H0 disable bits
must be clear. An R signature cannot authorize W. Actual persistent-process and
same-buffer evidence still must be independently checked by the parent.

The fixed Q15 root is a root-owned0700 directory under the original S180
namespace. Bind device, inode, owner and mode in signed inputs. This module
checks their shape/scope; the parent must verify the actual current filesystem
state before dispatch. Requested and independently observed facts remain
separate. No directory, worker or hardware state is created here.

## Exact compiled carrier and proof limits

Derive native request/4 only after verification, then derive context/4 from
those immutable bytes. Preserve the original v4 JSON-plus-LF serializer: the
existing result validator hashes that exact request encoding. The new signed
authorization remains JCS-I64 without LF. Hash each actual byte sequence;
do not introduce a request/authorization hash cycle or alter legacy serializers.
The native context binds both actual hashes, current runtime/release, original
predecessors, authority epochs and unchanged180-second per-run limit.

The returned dataclass and fresh dictionaries prevent input mutation from
changing verified bytes. It is a signature result, not an unforgeable execution
capability. Its proof explicitly has qualified_parent_replay_performed=false,
attempt_consumed=false, full_qualification=false and execution_authority=false.
No standalone CLI, signer invocation, worker dispatch or new semantic admission
is present. The future qualified parent must reverify immediately before use,
consume durable attempts and enforce the original monotonic deadline itself.

## Verification and remaining integration

Use real temporary SSHSIG keys/verification with explicitly synthetic source,
platform, root-inode and journal contexts. Cover both separately signed phases,
wrong keys/namespaces, changed signed bytes and context, broadened permissions,
original runtime selection, immutable output, prestate/session/platform geometry,
boot/window/expiry and rejected extra command/backend fields. Independently
validate new authorizations and both requests/contexts against their versioned
and unchanged compiled-entry schemas. Preserve reproduced missing root metadata,
missing schema reference and native LF-serialization failures with corrections.
Run related authority/journal regressions and Python debug allocation.

No production C++ or immutable protocol changes; existing native sanitizer and
codegen evidence is not rerun or relabeled for this Python/schema-only change.
Persistent Q15 collection, actual live fact derivation, qualified package/profile,
EXT008 admission and independent pilot validation remain pending. This closes
their signed-input prerequisite only. Stage17 remains incomplete; Stage18 is
deferred. Present the complete ETA before any actual operational start.
