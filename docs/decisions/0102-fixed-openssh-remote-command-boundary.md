# ADR-0102: Accept a fixed OpenSSH remote-command boundary

- Status: `ACCEPTED_REPOSITORY_LOCAL_IMPLEMENTATION_ONLY_NO_ACTION_AUTHORITY`
- Date: 2026-08-26
- Decision ID: D-102
- Accepted by: owner response bound to decision-input SHA-256 `faa4c377...`
- Owners: security, platform, repository, and audit owner
- Protocol version: `2.0.0-pre.2`
- Lifecycle gate: executor implementation before any P4-R-C transport

## Context and options

OpenSSH executes a remote command through the account login shell. Literal
remote `execve` argv is unavailable without a preinstalled agent or subsystem.
Options were to remain blocked for such an agent or accept a constrained fixed
command-string boundary.

## Decision and effects

Accept only repository-hashed, precomputed constant remote command strings.
The local process uses argv with `shell=False`, fixed pinned host/transport
identities, no user-controlled interpolation, strict token/path validation,
one attempt, and zero retry. The remote login shell is explicitly trusted.

Scientific effect is none. Tool bytes, exact strings, quoting grammar, SSH
options, paths, and command order become compatibility identity. This does not
authorize a connection. Any dynamic/general command interface is forbidden.

The selected implementation transmits five hash-described fixed Python
programs to absolute `/usr/bin/python3 -` commands and uses absolute
`/usr/bin/dd` upload commands. D-099 did not capture the remote interpreter,
`dd`, or tar-runtime identities. Therefore the executor carries an explicit
null runtime-acceptance constant and rejects action execution until a
prospective read-only evidence decision or explicit compatibility-risk
acceptance is recorded. This is an action blocker, not a fabricated default.

## Verification and supersession

Fake transport records exact argv and rejects shell flags, unregistered text,
metacharacter/path drift, retry, or fallback. Any command, quoting, SSH option,
tool, agent, or subsystem change requires a clean prospective ADR.
