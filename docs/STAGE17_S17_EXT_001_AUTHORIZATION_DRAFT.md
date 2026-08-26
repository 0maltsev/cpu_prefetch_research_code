# S17-EXT-001 read-only preflight authorization draft

The current machine-readable draft is
[`STAGE17-S17-EXT-001-READ-ONLY-PREFLIGHT-AUTHORIZATION-DRAFT-v5`](../config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v5.json).
The v1 through v4 drafts remain immutable predecessors. None is authority or
evidence. The v5 record is deliberately unissuable: every owner-controlled
value is `null`, status is `DRAFT_NOT_ISSUED_OWNER_INPUT_REQUIRED`, and its
authority boundary denies stand access, preflight, mutation, calibration,
pilot, and Stage 18 work.

## Owner-controlled fields

The owner must prospectively provide all of the following in one exact action:

- unique authorization ID, actor, issue UTC, expiry UTC, and target-scope ID;
- exact stand ID, SSH target, known-hosts host, structurally valid pinned-key
  evidence, exact single-line known-hosts file, and transport identity
  locator/byte-count/SHA-256 binding;
- exact pilot-candidate archive, sidecar, and extracted bundle-root locators;
- capture ID and UTC plus one normalized pre-existing nonsymlink local
  evidence root outside the repository and forbidden system roots; and
- exact execution paths for the policy-bound production executor and collector;
  production must load and execute those same files, not equivalent copies at
  dead prospective paths.

The owner supplies no command, argv, stdin, shell, per-observation output path,
timeout, retry, or permission value. Those values exist only in the immutable
repository-owned fixed action plan.

The supporting contract must be written first and validated against
`cpu-prefetch-stage17-read-only-preflight-supporting-contract/5`. The
authorization then binds its repository-relative path, exact byte count,
SHA-256, and schema identity. Both files are finally bound by one
`cpu-prefetch-stage17-operational-evidence-envelope/5`, together with policy
v5, fixed plan v3, all v5 schemas, and the complete verifier/executor/
collector/journal/helper runtime closure. A v1/v2/v3
or v4 authorization, or an unbound contract, cannot resolve `S17-EXT-001`.

The six observation IDs are fixed, ordered, and unique:

1. `S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY`
2. `S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION`
3. `S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION`
4. `S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS`
5. `S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES`
6. `S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY`

The fixed limits and policies are six commands, 30 seconds and 1 MiB per
observation, 180 seconds and 6 MiB total, one attempt per observation, zero
retries, stop on first mismatch/nonzero exit/timeout/output overflow,
create-exclusive outputs, and retention of all success/failure/partial
evidence. The exact permission
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
disk, recompute every size/hash, and apply the registered S17-EXT-001 semantic
verifier. Prospective `action_ready=true` additionally requires adjacent
transition 1, computed state `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, a live
explicit evaluation UTC, the actual loaded runtime paths/bytes, repeated byte
checks, and no prior attempt marker or output. Production execution accepts no
caller time. It completes all long semantic/schema/runtime checks, repeated
hashing, six-program render/compile, and OpenSSH-input pinning before taking
the final actual system-UTC sample. Future or expired authority cannot create
a marker. After durable marker creation, it samples actual UTC again
immediately before the first transport; expiry, future authority, or rollback
creates a typed failure and opens no transport. Verified known-hosts and
transport-identity bytes live in sealed `memfd` snapshots inherited by the
child and addressed as `/proc/self/fd/N`; the mutable owner pathname is never
reopened after marker. Literal effective paths are checked locally with
`/usr/bin/ssh -G`, without a connection. The executor otherwise uses exact SSH
argv and directory-FD create-exclusive storage.
The marker file and parent directory are fsynced before transport; one
180-second monotonic deadline covers the whole action, and every post-marker
failure retains the marker and attempts a typed failure record without retry.
This repository currently contains no resolution, transition, authorization,
evidence, or attempt.
