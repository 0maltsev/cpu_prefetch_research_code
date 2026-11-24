# D319: signed S180 request boundary

Implemented real owner-signature verification and deterministic S180 request
construction, separately from the legacy fixed-action route. The exact signed
plan, runtime, prerequisite, output-root and original-window inputs determine
the request. Its authorization digest is added only after signing, avoiding a
circular request/authorization hash dependency.

[D319 decision](../../../decisions/0319-s180-signed-request-boundary.md) describes
the exact contract and remaining operational boundaries.

The signer and allowed-signers bytes come from the caller's authenticated
EXT002/003 replay result. The original OpenSSH sealed-snapshot verifier checks
actual SSHSIG bytes and namespace. Authorization cannot choose a trust root,
key, arbitrary command, request path, retry, deadline reset or Stage18 authority.
The exact original descriptive freeze/EXT007 limitations remain mandatory.
Distinct scoped EXT008/009 contexts must match all signed bindings; admitted
reentry additionally requires the exact scoped EXT010 bytes/hash and signature.

This component consumes authenticated predecessor contexts. It does not supply
those contexts' qualified semantic producers or replay a journal itself. Tests
use explicitly synthetic replay views and real temporary test-only keys. Their
success is software evidence, never actual operational admission or qualification.
No real owner's authorization was generated or used in these tests.

## Fresh checks

- 11 new crypto/contract tests passed in the final registered CTest run, using
 actual temporary Ed25519 keys, SSHSIG signing/verification, admitted-key byte
 checks, sealed snapshots and a full D318 candidate from actual native sizing.
- 57 focused CTest entries passed, including the native S180 and existing
 archive/channel/custody/broker process regressions. The retained registered
 output records each suite, including the final11 authority cases.
- Build, format, immutable protocol integrity, schema fixtures, canonical bytes,
 queue provenance, runner and qualification schema checks passed. Protocol/schema
 validation was repeated after the last new schema grammar edit and passed.
- Python AST parsing and Git whitespace checks passed.

Negative tests reject changed signed bytes, foreign signer/namespace, changed or
unsafe signer/signature files, altered plan/runtime/ancestry, missing or legacy
scoped inputs, mismatched qualification/compatibility credit, widened permissions,
wrong boot/window/expiry, unlaunchable native IDs, noncanonical/duplicate/oversize
inputs and absent/mismatched actual EXT010 admission. Returned immutable bytes
remain unchanged after caller dictionaries are modified.

The early direct log contains8 cases; the intermediate direct log contains10.
Both passed, but the final registered11-case output supersedes them. This change
contains no C++ or measured-loop source changes. D318 sanitizer evidence is
preserved without claiming a new sanitizer run for this Python boundary.

## Plan status

Step3 advanced: native capture/source/session/archive/worker, prospective sizing
and now the actual signed-request boundary are implemented and software-verified.
Still required: qualified scoped semantic producers/journal replay, parent/profile
and durable attempt/sealed dispatch/archive orchestration, actual original source
provenance/namespaces, complete time/storage/recovery budget, scoped EXT008/009/010,
clean qualified release/codegen and actual stand qualification/compatibility.
Then execute exactly one approved180-capture family, validate retained results,
prove restoration/quiescence and scoped exit. Stage17 remains incomplete.

No stand access, schedule preparation, qualification, pilot or operational window
occurred in this step. No calibration data/validation was repeated, raw transferred
to the PC, historical evidence deleted, or Stage18 authority issued.
