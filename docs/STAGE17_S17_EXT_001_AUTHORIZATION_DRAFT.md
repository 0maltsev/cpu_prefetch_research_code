# S17-EXT-001 read-only preflight authorization draft

The current machine-readable draft is
[`STAGE17-S17-EXT-001-READ-ONLY-PREFLIGHT-AUTHORIZATION-DRAFT-v2`](../config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v2.json).
The v1 draft remains immutable as its predecessor. Neither draft is authority
or evidence. The v2 record is deliberately unissuable: every owner-controlled
value is `null`, status is `DRAFT_NOT_ISSUED_OWNER_INPUT_REQUIRED`, and its
authority boundary denies stand access, preflight, mutation, calibration,
pilot, and Stage 18 work.

## Owner-controlled fields

The owner must prospectively provide all of the following in one exact action:

- unique authorization ID, actor, issue UTC, expiry UTC, and target-scope ID;
- exact stand ID, SSH target, and repository evidence binding for the pinned
  host key;
- exact pilot-candidate archive and sidecar locators;
- finite wall-time and total/per-observation output bounds;
- two exact prospective local identities: launcher and collector execution
  paths plus repository source paths, byte counts, and SHA-256 values;
- for every one of the six fixed observations, the local action identity,
  complete argv bytes, stdin bytes, remote-command bytes, create-exclusive
  output locator, and output limit.

The supporting contract must be written first and validated against
`cpu-prefetch-stage17-read-only-preflight-supporting-contract/2`. The
authorization then binds its repository-relative path, exact byte count,
SHA-256, and schema identity. Both files are finally bound by one
`cpu-prefetch-stage17-operational-evidence-envelope/2`. A v1 authorization or
an unbound contract cannot resolve `S17-EXT-001`.

The six observation IDs are fixed, ordered, and unique:

1. `S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY`
2. `S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION`
3. `S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION`
4. `S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS`
5. `S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES`
6. `S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY`

The fixed limits and policies are six commands, one attempt per observation,
zero retries, stop on first mismatch/nonzero exit, create-exclusive outputs,
and retention of all success/failure/partial evidence. The exact permission
matrix allows read-only stand observation and denies mutation, privileged
controls, qualification, calibration, pilot execution, measurement, and Stage
18 authority. Pilot role collapse is disclosed; independent review is not
claimed.

## Runtime identity boundary

The local launcher and collector are prospectively known action inputs and
must be byte/hash-bound before any action. Remote runtime executable, module,
and dependency paths/hashes do not yet exist as accepted facts. They are
objects of the fifth read-only observation and can only be recorded by
`S17-EXT-002`; the S17-EXT-001 contract has
`prospective_values_present=false` and contains no invented remote identities.

After owner completion, the validator must read all referenced files from
disk, recompute every size/hash, apply the registered S17-EXT-001 semantic
verifier, and separately evaluate authorization expiry at the intended action
UTC. Only then could a new append-only resolution and adjacent journal
transition be prepared. This repository currently contains neither.
