# Q15-R role and custody setup plan

`config/q15/q15-r-role-custody-setup-plan-v1.json` is a no-authority planning
artifact. Nothing in it reports an account, key, path, permission, capability,
mount, quota, or negative access test as created or verified.

The four proposed principals are:

- `cpu-prefetch-q15-operator`: submit one exact phase request;
- `cpu-prefetch-q15-controller`: run only the admitted fixed controller;
- `cpu-prefetch-q15-custodian`: seal, transfer, and receipt custody artifacts;
- `cpu-prefetch-q15-auditor`: read-only prestate/readback and independent
  verification.

They must become four distinct effective credentials. Reusing the root SSH
identity, a shared key, or labels over one credential does not satisfy D-058.
The proposed primary domain is `XEON-CPU-FETCH-MD3-Q15-CUSTODY` under
`/var/lib/cpu-prefetch/q15-r`; the secondary domain is
`DEVELOPMENT-REPOSITORY-Q15-CUSTODY` on a separate machine. Their actual
devices, mounts, hosts, paths, owners, modes, quotas, and free space must be
collected later rather than inferred from this plan.

Before Q15-R issuance, a separately authorized stand-setup transaction must
produce immutable evidence for actual UID/GID/groups/capabilities, the Ed25519
signer fingerprint and allowed-signers policy, positive permitted access,
negative cross-role access, two-domain separation, append-only sealing,
synthetic-byte transfer/receipt, and independent hash verification. Failure of
any positive or negative check makes the setup ineligible; it does not invite
fallback to root or broader permissions.

This document intentionally contains no account, key, permission, mount,
capability, or filesystem mutation commands. Preparing it did not access the
stand. A later setup authorization must identify the exact commands, target,
rollback, evidence destinations, and operator before any such action.
