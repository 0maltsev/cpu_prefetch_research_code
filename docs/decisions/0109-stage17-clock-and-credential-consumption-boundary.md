# ADR-0109: Stage 17 clock and credential-consumption boundary

- **Status:** Accepted for repository-local implementation by the Stage 17A.4
  task authorization; it grants no stand, transport, preflight, qualification,
  calibration, pilot, measurement, or Stage 18 authority.
- **Decision ID:** ADR-0109
- **Classification:** implementation, security, time, credential-consumption,
  durability, and operational governance; no scientific semantics change.
- **Owner:** repository and pilot owner.
- **Gate:** before any `S17-EXT-001` production action.

## Context

ADR-0108 made actual system UTC and a durable marker mandatory, but executor
v2 sampled authority time before its last full validation and preparation. An
authorization could therefore expire before marker creation while the stale
sample remained accepted. Executor v2 also passed the originally verified
known-hosts and transport-identity pathnames to OpenSSH. Atomic replacement or
in-place mutation after admission changed the bytes later consumed by the
external process.

Policy v4 binds the unversioned `stage17_state_journal.py`; changing that file
would invalidate its immutable runtime closure. The current successor must
therefore use a separately versioned journal/runtime module and retain v4
unchanged.

## Options considered

1. Re-hash mutable pathnames immediately before `Popen`. Rejected because an
   attacker or concurrent owner process can replace or mutate the file between
   the check and the child open.
2. Hold descriptors to the original files and pass `/proc/self/fd/N` paths.
   Rejected alone because an in-place write changes bytes visible through an
   ordinary descriptor.
3. Copy verified bytes into Linux anonymous memory files, seal their size and
   content, and pass only inherited descriptor paths to the child. Selected.
4. Patch policy v4, executor v2, verifier v4, or the unversioned journal in
   place. Rejected because those bytes are accepted predecessor evidence.

## Decision

Future production admission uses policy v5, fixed action plan v3,
authorization/supporting-contract/envelope v5, semantic verifier v5, executor
v3, and journal runtime v2. Collector v2 remains unchanged and is hash-bound.
Policy v5 binds policy v4, ADR-0108, this ADR, every successor schema, the
action plan, and the complete actually loaded runtime/helper closure.

All potentially long semantic validation, byte/hash rechecks, schema loading,
evidence-root opening, fixed SSH argv construction, and render/compile of all
six programs finish before the final authority sample. The executor then reads
full-precision actual system UTC and requires
`issued_at <= actual_before_marker < expires_at`. A clock rollback relative to
the earlier prospective sample is rejected before marker.

After the marker file and parent directory are fsynced, the executor reads
actual system UTC again immediately before the first transport. Expiry,
not-yet-valid authority, or rollback at that boundary opens no transport,
retains the marker, creates one typed failure record when storage remains
available, and permanently forbids retry. One monotonic 180-second deadline
still begins at the marker boundary and covers every post-marker operation.

Authorization issue/expiry and contract capture timestamps are exact
second-only UTC strings. Actual clock observations retain fractional precision
and are separately typed in action records.

Before the final authority sample, executor v3 opens the exact bound
known-hosts and transport-identity inputs with `O_NOFOLLOW`, reads and verifies
their complete byte count and SHA-256, copies them into separate Linux
`memfd_create(MFD_ALLOW_SEALING|MFD_CLOEXEC)` objects, sets mode `0600`, and
applies `F_SEAL_WRITE|F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL`. It verifies the
applied seals. OpenSSH receives only `/proc/self/fd/N` snapshot paths and those
descriptors through `pass_fds` with local `shell=False`. The source pathnames
are never read after marker. Atomic replacement and in-place mutation of the
source therefore cannot change consumed bytes. Failure to create, populate,
seal, or verify both snapshots stops before marker.

Private-key bytes are never serialized, logged, or placed in evidence. Typed
records retain only the already accepted binding hash, byte count, sealed
snapshot mechanism/seals, and `private_bytes_recorded=false`. Known-hosts
records retain the consumed SHA-256. All record schemas and validators needed
after marker are loaded and hash-checked before marker, so later schema-path
drift cannot change the active action outcome.

The immutable executor v2 remains readable but is not the production entry
under policy v5. Journal runtime v2 admits only v5 envelopes/verifier identity;
executor v2, which is hard-wired to policy v4, rejects a v5 resolution before
marker and cannot obtain v5 action readiness.

## Scientific effect

None. The six read-only observations, queue/measurement behavior, protocol data
model, and Stage 18 chronology are unchanged.

## Compatibility effect

Protocol snapshots, graph/catalog/genesis, journal snapshots, ADR-0104 through
ADR-0108, policies/plans/schemas v1 through v4, collector v2, executor v2,
verifier v4, and the unversioned journal remain byte-identical. New actions
require the v5/v3/v2 successor closure; predecessor evidence remains readable
but cannot silently authorize the successor.

## Risks and mitigations

- Linux `memfd` sealing and `/proc/self/fd` are platform-specific. Linux is the
  accepted platform; missing support is a pre-marker fail-closed blocker.
- System-clock steps can reject an otherwise intended action. Rejection and a
  new prospective authorization are safer than reuse or retry.
- A process crash after durable marker can leave no typed failure record. The
  marker alone still permanently consumes the one-shot authority.

## Supersession rule

Any change to clock sampling, exact-second authority format, snapshot
mechanism, seals, `pass_fds`, OpenSSH argv, record schemas, runtime closure,
retry policy, or global deadline requires a new ADR/policy/plan/runtime version.
ADR-0109 never authorizes stand access or a later lifecycle phase.
