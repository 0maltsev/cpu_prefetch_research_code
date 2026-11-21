# D319: S180 signed request boundary

Accepted engineering implementation under the existing D310 S180 acceptance.
This adds the signature/request portion of the parent route. It does not admit
scoped EXT008/009/010, qualify a parent profile, consume an attempt, construct a
worker context or execute anything. No scientific setting, immutable protocol,
completed observation or original operational deadline changes.

## Why a separate contract is necessary

The preserved fixed-action controllers accept their historical action/request
contracts. Their generic readiness and descriptive-calibration rejection must
remain intact. D317's S180 native entry accepts a distinct request whose parent
must independently authenticate signed scoped evidence. Native hashes alone
are not proof of signatures or semantic admission.

The S180 request also includes its authorization's digest among prerequisite
bindings. Signing that complete request hash inside the same authorization would
create a hash cycle. No such record was issued or used. Instead, the owner signs
all request inputs other than this derived digest: exact plan hash, session/
request/attempt/authorization/stand identities, qualified runtime/release,
all seven prior prerequisite digests, actual family directory binding and the
original boot/24h window. The request is then constructed deterministically,
adding the original authorization-byte hash as its EXT010 prerequisite.

This is a separately versioned S180 contract, not a change to earlier request
bindings or signatures. There is no caller-authored arbitrary command, argv,
request locator, trust path, signer key, retry or Stage18 permission.

## Trust and exact bindings

`stage17_s180_authority_v1` consumes a caller's authenticated journal replay
result. It requires predecessors EXT001 through EXT009; authorization bytes
cannot supply these resolutions. EXT002/003 ancestry must match the replay,
and the actor must equal EXT003's admitted principal. The existing OpenSSH
verifier pins the admitted allowed-signers and signature files in sealed
snapshots and verifies the actual SSHSIG bytes/namespace. No self-selected trust
root, key, or replacement native binary can follow from the signed document.

The signature boundary requires distinct closed semantic context projections
for scoped EXT008 (`D310-S180-PILOT-INPUT-v1`) and EXT009
(`D310-S180-RESOURCE-ADMISSION-v1`). These project exact plan/window/output
bindings, runtime/release/qualification/compatibility/profile identity and
resource admission. Their qualified semantic producers and journal successor
are still required work. A dict containing those fields is not independent
semantic evidence. Tests supply explicitly synthetic replay views; those views
are never used for real journal admission or a production launch.

The existing accepted EXT007 resolution and original freeze must match the
immutable blueprint. Descriptive provenance acceptance and the unmet legacy
statistical contract both remain explicit. S180 scope cannot turn generic
readiness into true. The new boundary never replaces or appends an EXT007 record.

The plan is copied through its bounded canonical bytes before any hash check;
the same owned value is used for request construction. Authorization and request
are returned as immutable exact bytes, not cached mutable verified dictionaries.
Unknown fields, duplicate/noncanonical JSON and inputs exceeding16MiB reject.
Native request IDs use the existing256-byte ASCII opaque-ID grammar. The release
source is an exact40-hex commit and all prerequisite/runtime hashes are explicit.

## Window and admitted reentry

Authorization must name the current boot and an already started original window
of exactly24h. Actual system epoch/monotonic readings are sampled; caller time is
not accepted. Epoch validity conservatively covers the remaining original
window using the native whole-second margin rule. A long signature lifetime
cannot enlarge the window's permissions. Nothing here creates or resets it.

The evidence root must be the exact plan-hash family under a `working` directory
and match both admitted projections. This signature step checks its declaration;
actual held-directory device/inode/ownership/path checks remain the dispatcher's
mandatory responsibility. Similarly, a qualified runtime projection is not
independent actual image pinning or clean-release/codegen qualification.

`verify_admitted_authorization` repeats all signature/binding checks and requires
the exact actual scoped EXT010 authorization bytes/hash from a fresh replay.
Its result still grants no execution by itself. Attempt consumption, sealed
source membership/provenance, namespace consumption, live resources, pinned
runtime/closure, final authority checks, archive orchestration and restoration
remain mandatory parent responsibilities before/through any launch.

## Verification and limits

Tests use actual temporary Ed25519 keys and `/usr/bin/ssh-keygen -Y sign/verify`,
the original pinned-snapshot verifier and a full candidate assembled by D318
using the actual local native sizing command. They demonstrate valid request
construction and rejection of changed bytes, foreign keys/namespaces, changed
admitted signer files, unsafe signature paths, altered plans/runtime/ancestry,
missing/legacy scoped predecessors, false qualification credit, widened
permissions, unlaunchable IDs, foreign/changed windows, inadequate expiry and
missing/mismatched EXT010 reentry. Temporary keys are test-only and removed.

The JSON schema and CTest registration are additive. This change contains no
C++ or measured-loop modification; D318's relevant sanitizer evidence remains
preserved, with no repeated sanitizer/measurement claims for this Python-only
boundary. Fresh actual crypto/file tests and related regressions are its checks.

The signed boundary is complete as software, not as a qualified operational
parent. Stage17 remains incomplete, no stand action/window starts here, and
Stage18 remains deferred.
