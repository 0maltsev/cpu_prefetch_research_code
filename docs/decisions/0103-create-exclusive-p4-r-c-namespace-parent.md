# ADR-0103: Freeze the P4-R-C namespace-parent rule

- Status: `ACCEPTED_REPOSITORY_LOCAL_IMPLEMENTATION_ONLY_NO_ACTION_AUTHORITY`
- Date: 2026-08-26
- Decision ID: D-103
- Accepted by: owner response bound to decision-input SHA-256 `faa4c377...`
- Owners: platform, security, release, and audit owner
- Protocol version: `2.0.0-pre.2`
- Lifecycle gate: before the first P4-R-C stand mutation

## Context and options

ADR-0072 froze the transaction root but did not say what to do if namespace
parent `/root/cpu-prefetch-q15-r-p4-r` is absent. Options were to stop or allow
one exact parent create/verify rule.

## Decision and effects

Allow the namespace parent to be created once with mode `0700` if absent. If it
exists, require a root-owned, nonsymlink directory with exact mode and no
conflicting transaction root. Then create the transaction descendants
exclusively. Partial creation is retained and consumes the transaction identity;
no retry or cleanup is authorized.

Scientific effect is none. Parent path/type/owner/mode, absence/presence rule,
transaction identity, and partial-state behavior become compatibility inputs.
This ADR itself authorizes no stand mutation.

## Verification and supersession

Fake filesystem tests cover absent/valid/invalid parent, collisions, symlinks,
partial creation and retry rejection. Any path, owner, mode, reuse, retry, or
cleanup change requires a new transaction identity and prospective ADR.
