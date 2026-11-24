# ADR-0082: Freeze P4-K-A public export identity and path policy

- Status: `ACCEPTED_POLICY_LITERAL_PUBLIC_PATH_AND_IDENTITY_REQUIRED`
- Date: 2026-08-25
- Decision ID: D-082
- Accepted by: Q15-R-P4-K-A-D, `P4KA-Q3=ACCEPT_D082_RECOMMENDATION`
- Decision owners: custody, security, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0077 and ADR-0078
- Lifecycle gate: before controller specialization, artifact construction, or issuance

## Context and options

Public key and trust artifacts require durable identity without exposing the
private-key path. Options were a unique create-exclusive public export root
outside the repository and stand, an independently evidenced equivalent, a
repository/stand/temporary/reused path, or remaining blocked.

## Decision

Require one unused action ID and an absolute create-exclusive public export
root in the owner-controlled offline custody domain. A later input gate must
freeze public-key, allowed-signers, receipt, inventory, and SHA-256 sidecar
artifact IDs and basenames, ownership/mode/access controls, collision handling,
and retention. Only public artifacts may enter the export root; the private-key
path is never serialized.

No literal path, action ID, directory, or artifact is selected or created by
this ADR.

## Evidence and effects

- D-082 proposal SHA-256: `8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.
- Acceptance SHA-256: `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- Every public-path and artifact input remains null.

Scientific effect is none. Action ID, public root, basenames, owner/mode/access
policy, collision disposition, receipts, and sidecars become evidence identity.

## Verification and supersession

Checks must reject repository, stand, temporary, reused, inferred, or non-null
paths and any private-path field. Any root, path, artifact ID, basename,
owner/mode/access, collision, or retention change requires a new unused action
identity and prospective decision.

No protocol amendment is required.
