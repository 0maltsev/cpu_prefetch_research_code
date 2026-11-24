# D324: keep verified original sources alive through scoped replay and handoff

Accepted engineering implementation under approved D310. This is a source-owner
component for the qualified parent, not a new experiment, authority, namespace
reservation or resource-admission route. The frozen native34247ce image and
D322/D323 code remain unchanged.

## Gap and required continuity

D323 verifies accepted generation for all36 original sources, which may take
substantial preparation time on the stand. D322's metadata transaction lease is
120seconds. Repeating full generation inside every journal callback would both
exhaust that lease and waste preparation time. Conversely, accepting a serialized
report with a success flag would lose the independent source proof.

Run actual D323 verification once in the qualified parent's process, before
opening a short journal transaction. Then keep an owned source bank alive in
that same process. Its factory has no report-import or skip-verification input.
A persisted JSON report cannot create or revive the owner. Reopening after
process exit requires fresh source verification, not another measurement or an
automatic experimental retry.

## Verified bytes, actual seals and finite ownership

`verified_sources` first validates the complete prospective plan/records and
source/vector budgets. Snapshot all108 original binary/envelope/derivation paths
and check the actual FD limit can retain36 sources, three transient descriptors
and eight control descriptors. This is a necessary source-component check, not
complete EXT009 admission or a whole-parent FD/memory bound.

Invoke the unchanged D323 verifier. Then stream each exact verified binary into
a memfd, checking its original path/inode/mode/owner/size/time stamps and full
hash again during the copy. Complete short writes and check the caller's fixed
verification deadline throughout. Apply WRITE/GROW/SHRINK/SEAL seals, reopen
read-only and close the writer. Final original-bank checks detect changes across
verification and sealing. No original is rewritten or deleted.

The owner holds immutable proof bytes,36 read-only sealed descriptors and the
original108-file snapshot. Its native context has the exact existing C++ fields:
S180 source-context version, source bindings, native vector limit and fixed
deadline. Payload limits distinguish all sealed bytes from the native vector
and temporary-vector requirement in first-use order. They are not estimates of
total resident memory, page rounding, allocator overhead or whole-job resources;
those remain part of the complete prospective resource gate.

Proof/context getters verify plan identity, original files, actual descriptor
identity/access/seals, owner PID, boot and fixed expiry without regenerating
deadlines. They return independent data/immutable bytes. No API refreshes the
expiry. For live preparation/execution the caller must bind this source lifetime
to its original operational window; a successful getter does not prove or extend
that window. A separate historical audit may independently reverify originals
under a finite read-only audit lifetime, never revive old execution authority.
The native worker's independent authority and window guards remain mandatory.

On ordinary exit, parent exception or partial pin/seal failure, close every
owned descriptor. If a descriptor was externally replaced, close the remaining
owned descriptors, preserve the unrelated replacement and raise a cleanup
failure. Never silently accept descriptor loss or close a foreign descriptor.

## Scoped replay and qualification limits

A qualified semantic provider may use this live owner as its source-generation/
sealed-input fact, matching the original source report digest and plan identity.
It still must independently validate namespaces, release/qualification/
compatibility, platform, recovery, resources, custody and original authority.
Proofs retain namespace freshness, resource admission, execution and Stage18
flags false. Input data cannot select a verifier or construct an owned source
bank from asserted facts.

The journal integration test uses real accepted generation, kernel seals,
original-file guards, SSHSIG and EXT008 record publication. Its blueprint,
original replay, qualified-runtime/resource facts and semantic callback are
explicit software fixtures. It demonstrates the live source connection and
one generation-verification invocation across repeated short journal reads; it
does not qualify the complete production callback or issue actual EXT008.
An actual child checks every inherited source's native-context bindings/seals
and bytes; it is a Python reader, not execution of a pilot native worker.

The qualified full semantic provider, durable one-attempt parent/archive loop,
restoration and source-bound S180 administrative profile/package remain pending.
Actual preparation and qualification cannot start before the total estimate and
budget are presented and pass the approved single24-hour envelope. No actual
pilot source, stand operation, new admission or operational window is created
by this software-verification step.
