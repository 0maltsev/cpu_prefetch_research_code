# ADR-0050: Stage 17 qualification authority and custody prerequisites

- Status: `ACCEPTED_POLICY_IMPLEMENTED_LOCALLY`
- Date: 2026-08-24
- Decision ID: D-050
- Classification: security, privilege, and artifact-custody boundary
- Decision owners: security, platform, controller, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: none; specializes ADR-0045 for Q15 preparation
- Lifecycle gate: exact identities and negative evidence before Q15

## Context and options

The candidate currently exposes only a root SSH principal. Root access cannot
simultaneously serve as operator, controller, custodian, and independent
auditor. The stand's `/dev/md3` filesystem is one durable domain, while the
development repository is a separate machine/custody domain. Options were one
root principal, informal human role labels, or four distinct least-privilege
principals with an explicit access matrix and two-domain transfer.

## Decision

Select the four-role model:

- operator: may invoke only hash-bound privileged qualification commands;
- controller: may invoke authorized nonprivileged collectors and validate
  exact command/limit bindings, but cannot mutate the platform;
- custodian: may seal/transfer append-only outputs, but cannot run controls or
  analysis;
- auditor: may independently read hashes, readbacks, logs, and negative-access
  evidence, but cannot control or alter artifacts.

All four identities must be distinct in the authorization record and in the
effective credential/capability mapping. Negative tests must prove each
forbidden role/action pair. The candidate stand `/dev/md3` filesystem is the
proposed primary qualification-output domain; the development repository is
the proposed secondary transfer/custody domain. Exact paths, accounts, keys,
groups, capabilities, expiry, quotas, append-only mechanism, and transfer
receipt remain future evidence and cannot be filled by defaults.

`cpu-prefetch-stage17-authorization/2` binds the v3 runner and preserves exact
four-role, command, inverse/readback/probe, two-domain, limit, prohibition, and
signature fields. Its validator rejects overlapping roles and same-domain
custody. The schema validates a prospective record; it never grants authority.

## Evidence and effects

Evidence is Q15-P0 owner acceptance, the prior read-only stand discovery (one
root account and one `/dev/md3` mounted domain), and the authorization
negative-test suite. Scientific effect: none; it separates control and custody
and prevents self-verification. Compatibility effect: principal, credential,
command, tool hash, domain, path, limit, and signature changes require a new
authorization. Owner: security/custody. Deadline: before Q15 issuance.

Q15-P0 authorizes this repository-local policy and setup proposal only. It does
not authorize account creation, key installation, stand access, privilege,
qualification, calibration, pilot, or confirmation.
