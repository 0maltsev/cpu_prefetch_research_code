# D322: signed S180 input journal with mandatory semantic replay

Accepted engineering implementation under the approved D310 S180 design. This
adds the bounded persistence/replay mechanism for scoped EXT008–010. It does not
change the scientific matrix, calibration lineage, native release, raw custody,
operational window or experiment authority. Actual semantic fact producers and
the qualified parent/profile remain required before this mechanism can admit
real pilot inputs.

## Requirement and trust boundary

The existing policy65 journal accepts the original seven inputs with EXT007's
descriptive-only scope and deliberately rejects legacy pilot EXT008–010. D319
requires separately authenticated S180 contexts. Reusing the legacy ready flag,
changing the original resolutions or treating hashes/signatures as semantic
proof would bypass that distinction.

`stage17_s180_journal_v1` anchors a separate journal to the authenticated original
seven resolution identities/digests, original journal digest, exact prospective
plan, frozen D310 blueprint/approval and qualified semantic-policy fingerprint.
The original mappings are copied, never rewritten. The required EXT007 context
retains `STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY`, accepted data provenance and an
unsatisfied legacy statistical freeze. Neither this journal nor its views grants
generic pilot readiness, execution permission or Stage18 authority.

The qualified caller must supply a fixed, authenticated semantic replay function
for EXT008/009. It must independently validate the actual plan, sources,
namespaces, platform, qualification/compatibility, resources and recovery/time
budget, returning the exact D319 context or raising. It receives only the
preceding replay view and bounded input payload, with an explicit historical or
current-check contract. A boolean or self-asserted context is insufficient.
The journal's context-shape checks supplement that verifier; they do not replace
it. The fingerprint binds the caller's implementation identity, not its
qualification. Input data cannot choose a verifier, plugin, key or command.

`from_authenticated_base` invokes the original policy65 replay using actual UTC
and `allow_synthetic_test_evidence=False`. Its closed argument set contains only
the six original repository/evidence/journal/candidate locators. It does not
expose caller-selected time, policy or fixture promotion through those inputs.
The operational caller must still authenticate its source closure and semantic
function; the supplied production fact producers are not implemented here.

## Ordered, durable records

A fresh owned directory contains an exclusive lock and immutable anchor. Signed
records must append EXT008, then EXT009, then EXT010, with no other order, extra
record or new family. Each canonical record binds its anchor, predecessor,
timestamp, payload, independently derived context digest and fixture/authority
classification. The actual admitted EXT002/003 principal and allowed-signers
trust verify each SSHSIG in the existing Stage17 namespace. Journal snapshots
bind every original record/signature byte count/hash and preceding snapshot.

EXT008 binds the exact plan, clean runtime/release, qualification, compatibility,
runtime profile, original boot/window and actual reserved output identity.
EXT009 binds the same plan/window/inode and separately verified resource
admission. EXT010 additionally verifies D319's complete original owner
authorization and signature against the actual preceding scoped record hashes.
No signature can substitute for missing EXT008/009 semantic checks.

Before owner signing, `prepare_record` replays preceding inputs and derives
semantics without publishing a journal record. `append` rechecks the exact
external record/signature bindings and current semantics before publishing
exclusive record, signature and snapshot files with file/directory fsyncs.
Partial objects remain evidence and block subsequent replay, retry or adoption;
they are never erased or silently completed.

The held directory and lock inode, owned regular files, canonical bytes, bounded
inventory, per-file and aggregate reads, chronology and before/after metadata
stamps are checked. A final inventory/stamp check detects mutation while replay
is in progress. Limits are 16MiB per object, 64KiB per SSHSIG, 1MiB per semantic
context, 256MiB aggregate reads and a 120-second metadata transaction lease.
Separate transactions may reopen this metadata; doing so never restarts the
original 24-hour operational window. The production parent must not hold this
metadata lease across the hours-long pilot.

## Historical proof is separate from current permission

Historical replay must remain possible after expiry or reboot. The separate
`verify_historical_authorization` API retains cryptographic, static shape and
lineage checks, but returns only a proof with `current_window_checked=false`
and all launch/execution authority false. It exposes no native request bytes.
The existing public `verify_authorization` still always checks actual boot,
monotonic/epoch time and conservative coverage through the original window.
There is no historical-mode field in signed authorization or launch input data.
Preparing/appending records requires current replay. Read-only inspection is
historical by default; current inspection explicitly checks the current window
and asks the qualified semantic provider to recheck current facts.

`scoped_inputs_complete` means exactly three correctly ordered scoped records.
It does not mean the parent/profile is qualified or an attempt is consumed.

## Verification and remaining work

The evidence report records real temporary SSH keys, actual signature
verification and filesystem/locking/fault tests. Independent semantic facts and
base replay views in these tests are explicitly synthetic; the base adapter's
argument contract is tested with a mocked original replay. The existing legacy
verifier is also exercised directly to preserve its descriptive EXT007 guard.

This completes the journal mechanism only. Qualified actual EXT008/009 fact
producers, a source-bound parent with one durable attempt and sealed worker/
archive lifecycle, and the qualified S180 administrative profile/package remain
pending. No actual EXT008–010 resolution, stand source preparation,
qualification, capture, restoration claim or operational window is issued here.
The frozen clean native34247ce image and all completed calibration data remain
unchanged.
