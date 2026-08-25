# Q15-R operational-prerequisite and role/custody decision bundle

Status: **`ACCEPTED_Q15_R_P2_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`**

Prepared: 2026-08-25

Protocol: `2.0.0-pre.2`

Machine-readable record:
[`config/q15/q15-r-operational-prerequisite-decision-input-v1.json`](../config/q15/q15-r-operational-prerequisite-decision-input-v1.json)

Record SHA-256:
`6e27f16c8c4280b96cb0e6c58a02247e87f595399743218612325e037f8b85e7`

Schema:
[`config/schemas/q15-r-operational-prerequisite-decision-input-v1.schema.json`](../config/schemas/q15-r-operational-prerequisite-decision-input-v1.schema.json)

The machine-readable proposal remains byte-preserved at the hash above. Q15-R-
P2 accepted D-061 through D-064 in the separate
[`Q15-R-P2 acceptance record`](../config/q15/q15-r-p2-acceptance-v1.json),
whose SHA-256 is
`2c280b46c8cf196f52f9446089c1749b2b0fe754033049b5cac0e472353245eb`.
Acceptance authorized repository-local adapter implementation, no-authority
record synchronization, and stand-setup authorization preparation only. It did
not authorize stand access, account/key or filesystem changes, transfer or
installation, access tests, Q15-R, Q15-W, PMU/MSR/affinity/NUMA operation,
calibration, pilot, measurement, or confirmatory execution.

## Release evidence now closed

The proposal binds the exact clean controller-bearing base release:

| Field | Exact value |
|---|---|
| Source commit | `a75bcdd0367d79f8ee0496c55edda74311c9ef7d` |
| Bundle profile | `Q15-QUALIFICATION-TOOL-BUNDLE-v2` |
| Archive | `cpu-prefetch-q15-qualification-tool-2.0.0-a75bcdd-clean-b4438745f3ca.tar.gz` |
| Archive bytes | `4247166` |
| Archive SHA-256 | `48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035` |
| Sidecar SHA-256 | `9c7dee2e07c49e51af8b3e922e8295ecce959dfe53deed4d3604e59722655505` |
| Source archive SHA-256 | `b4438745f3ca5a461a456ea7200970b41893572869866bf40a5d58da4c18d2c7` |
| Manifest SHA-256 | `90f01cd1be57d844f532d0b9f5612179aa9436a44ba353e3aeda724d10704030` |
| SBOM SHA-256 | `c1b915f082ce3b6a1c916c7bef1d17e008d0dede623ec8aa927dbe868dd3f537` |
| Controller SHA-256 | `36607f03669d194b22d37bc6652e92fe8486ab0ef4964ef5217ad73d18d15cf1` |
| Q15 tool SHA-256 | `ba93d6384eb536654ccdfa94dc4b52c0cfde9408b9d79ef902ea6e3749548d15` |
| Controller-codegen report SHA-256 | `7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca` |
| Internal inventory | `118` files, all verified |
| Authority | `NONE` |

This release is prerequisite evidence, not the future operational execution
release. Its CLI still refuses before opening Q15-R inputs. Enabling the fixed
core now has an accepted, fake-tested repository-local adapter. Q15-R-P3 accepts
D-065 and selects the verified clean adapter-bearing release as evidence only.
Actual trust-anchor and role/custody evidence and a later separately approved
signed Q15-R record remain required.

## D-061 — clean v2 base-release identity

- Classification: build, release, and authority identity.
- Options: continue using Q15-S3 v1; bind v2 as prerequisite evidence only;
  treat possession of v2 as authority; rebuild or relabel v2.
- Selected option: bind the exact table above as immutable prerequisite
  evidence only. Do not grant it dynamic authority.
- Evidence: clean Git identity, archive/sidecar, 118-file internal inventory,
  manifest/SBOM/source/binary/report hashes, five clean-extraction self-tests,
  and strict GNU/LLVM reports.
- Scientific effect: none.
- Compatibility effect: every listed byte identity becomes a prerequisite;
  an operational adapter requires a new clean release identity.
- Owners: build, controller, security, and audit.
- Gate: before operational-adapter implementation or stand setup authority.
- Supersession: any byte, build, dependency, profile, manifest, or authority
  change requires a new release and full verification.

## D-062 — operational adapter and trust anchor

- Classification: security and qualification-controller engineering.
- Options: ambient root CLI; ad-hoc shell wrapper; fixed non-setuid inherited-
  descriptor adapter; declare the stand ineligible.
- Selected option: `Q15-R-TRUST-ANCHOR-ADAPTER-v1`, with no shell, setuid,
  arbitrary selector, ambient root, or network operation. The private Ed25519
  key remains off-stand. The auditor alone reads the allowed-signers file and
  produces an independently hash-bound verification receipt. The controller
  consumes bounded inherited descriptors and cannot read the trust-anchor
  file.
- Evidence: ADR-0057's fixed graph, ADR-0060's SSHSIG boundary, and the
  implemented core's exact authorization/signature/receipt binding.
- Scientific effect: none; no scientific input is accessible.
- Compatibility effect: adapter profile, descriptor numbers/contracts,
  allowed-signers bytes/path, signer fingerprint, receipt bytes, exact argv,
  and executable hash become Q15-R authorization identity.
- Owners: controller, security, platform, and audit.
- Gate: accept before adapter implementation; resolve actual key evidence
  before Q15-R issuance.
- Supersession: any adapter, descriptor, signer, key, namespace, receipt,
  privilege, path, or binary change requires a new decision and clean release.

Accepted trust-anchor contract:

| Field | Proposed value or state |
|---|---|
| Scheme | `OPENSSH-SSHSIG-ED25519-SHA512-v1` |
| Namespace/principal | `cpu-prefetch-q15-authorization` |
| Canonical authorization | `JCS-I64-v1` |
| Allowed signers | `/etc/cpu-prefetch/q15/allowed_signers` |
| Owner/group/mode | `root:cpu-prefetch-q15-auditor`, `0640` |
| Controller read access | denied |
| Private key on stand | prohibited |
| Signer fingerprint | unresolved; cannot be invented |
| Independent receipt | mandatory and hash-bound |
| Inherited descriptors | authorization core `3`/1 MiB; signature `4`/128 KiB; receipt `5`/128 KiB |
| Operational adapter | repository-local fakeable seam implemented; no OS backend or operational release |

The proposed verifier argv is literal except for the typed signature-artifact
token:

```text
/usr/bin/ssh-keygen -Y verify -f /etc/cpu-prefetch/q15/allowed_signers -I cpu-prefetch-q15-authorization -n cpu-prefetch-q15-authorization -s @DETACHED_SIGNATURE_PATH@
```

Its standard input is exactly the canonical `JCS-I64-v1` authorization-core
bytes. A later authorization must replace the token with a literal absolute
regular-file path and bind both artifacts by SHA-256.

## D-063 — four-role and two-domain setup transaction

- Classification: least-privilege OS and custody engineering.
- Options: root/shared identity; labels over one identity; four system users
  with private groups plus one traversal group; stand ineligibility.
- Selected option: retain the accepted four principal IDs, give each a private
  group and `nologin`, exclude the operator from the common traversal group,
  and give controller, custodian, and auditor separate `0700` directories.
- Evidence: ADR-0058, the no-authority setup plan, historical `/dev/md3`
  inventory, and the imported sealing rules.
- Scientific effect: none.
- Compatibility effect: actual UID/GID/groups, paths, modes, device/mount,
  quota, key, and access-test evidence become authorization identity.
- Owners: security, platform, custody, and audit.
- Gate: before any stand account, group, path, permission, key, bundle, or
  trust-anchor mutation.
- Supersession: any role, group, permission, path, domain, credential, or
  access change requires a new prospective transaction.

The primary domain remains `XEON-CPU-FETCH-MD3-Q15-CUSTODY`, proposed under
`/var/lib/cpu-prefetch/q15-r`. The 2026-08-22 observation of `/dev/md3` is not
current-state, permission, quota, or custody proof. The secondary domain
remains `DEVELOPMENT-REPOSITORY-Q15-CUSTODY`; its actual host/root/device,
owner, mode, quota, reserve, and endpoint remain unresolved.

### Literal proposed setup argv

These lines are inert documentation. They were not run. They use no shell,
glob, environment expansion, package installation, network access, privilege
fallback, deletion, PMU/MSR access, or Q15 command. A later setup authorization
must replace every `@...@` token with a literal hash-bound argument and approve
the resulting complete argv list.

```text
/usr/bin/getent group cpu-prefetch-q15                         # expect 2
/usr/sbin/groupadd --system cpu-prefetch-q15
/usr/bin/getent passwd cpu-prefetch-q15-operator              # expect 2
/usr/sbin/useradd --system --user-group --no-create-home --shell /usr/sbin/nologin cpu-prefetch-q15-operator
/usr/bin/getent passwd cpu-prefetch-q15-controller            # expect 2
/usr/sbin/useradd --system --user-group --no-create-home --shell /usr/sbin/nologin cpu-prefetch-q15-controller
/usr/bin/getent passwd cpu-prefetch-q15-custodian             # expect 2
/usr/sbin/useradd --system --user-group --no-create-home --shell /usr/sbin/nologin cpu-prefetch-q15-custodian
/usr/bin/getent passwd cpu-prefetch-q15-auditor               # expect 2
/usr/sbin/useradd --system --user-group --no-create-home --shell /usr/sbin/nologin cpu-prefetch-q15-auditor
/usr/sbin/usermod --append --groups cpu-prefetch-q15 cpu-prefetch-q15-controller
/usr/sbin/usermod --append --groups cpu-prefetch-q15 cpu-prefetch-q15-custodian
/usr/sbin/usermod --append --groups cpu-prefetch-q15 cpu-prefetch-q15-auditor
/usr/bin/install -d -o root -g cpu-prefetch-q15 -m 0750 /var/lib/cpu-prefetch/q15-r
/usr/bin/install -d -o cpu-prefetch-q15-controller -g cpu-prefetch-q15-controller -m 0700 /var/lib/cpu-prefetch/q15-r/controller-staging
/usr/bin/install -d -o cpu-prefetch-q15-custodian -g cpu-prefetch-q15-custodian -m 0700 /var/lib/cpu-prefetch/q15-r/sealed
/usr/bin/install -d -o cpu-prefetch-q15-custodian -g cpu-prefetch-q15-custodian -m 0700 /var/lib/cpu-prefetch/q15-r/receipts
/usr/bin/install -d -o cpu-prefetch-q15-auditor -g cpu-prefetch-q15-auditor -m 0700 /var/lib/cpu-prefetch/q15-r/audit
/usr/bin/install -d -o root -g cpu-prefetch-q15-auditor -m 0750 /etc/cpu-prefetch/q15
/usr/bin/install -o root -g cpu-prefetch-q15-auditor -m 0640 @ALLOWED_SIGNERS_SOURCE@ /etc/cpu-prefetch/q15/allowed_signers
```

The absence checks deliberately expect exit status 2. Any pre-existing name,
missing executable, different prestate, or nonzero apply result stops the
transaction. Package installation is not an implicit fallback.

## D-064 — access tests, rollback, and authority boundary

- Classification: security validation, recovery, and governance.
- Options: destructive deletion; continue after mismatch; first-failure
  quarantine with evidence retention; treat setup success as Q15-R approval.
- Selected option: require the complete access matrix, stop on the first
  mismatch, preserve the exact completed prefix, apply only quarantine commands
  applicable to that prefix, delete nothing, and require a new authorization.
- Scientific effect: none.
- Compatibility effect: matrix, expected results, evidence IDs, rollback
  argv, and stop disposition become transaction identity.
- Owners: security, platform, custody, audit, and protocol.
- Gate: before setup execution and again before Q15-R issuance.
- Supersession: any expectation, rollback, retry, deletion, or authority
  change requires a new prospective decision.

### Complete effective-access matrix

Every cell is an exact `/usr/sbin/runuser --user ROLE -- /usr/bin/test FLAG
TARGET` probe. `ALLOW` expects exit 0; `DENY` expects exit 1. The machine record
contains all 24 literal argv arrays and stable IDs `NA-001` through `NA-024`.

| Target / probe | Operator | Controller | Custodian | Auditor |
|---|---:|---:|---:|---:|
| `-x @OPERATIONAL_RELEASE_ROOT@/bin/cpu_prefetch_q15_controller` | DENY | ALLOW | DENY | DENY |
| `-r /etc/cpu-prefetch/q15/allowed_signers` | DENY | DENY | DENY | ALLOW |
| `-w /var/lib/cpu-prefetch/q15-r/controller-staging` | DENY | ALLOW | DENY | DENY |
| `-w /var/lib/cpu-prefetch/q15-r/sealed` | DENY | DENY | ALLOW | DENY |
| `-w /var/lib/cpu-prefetch/q15-r/receipts` | DENY | DENY | ALLOW | DENY |
| `-w /var/lib/cpu-prefetch/q15-r/audit` | DENY | DENY | DENY | ALLOW |

This gives 18 mandatory denials and six allowed cells. Passing `test -w` is
not append-only or durable-write evidence; later positive synthetic create,
seal, transfer, receipt, recovery, and hash-readback exercises remain required.
Operator endpoint access, auditor privileged read-only device access, and the
secondary custody endpoint remain blocked until their exact implementations
and authorizations exist.

### Proposed rollback argv

Rollback is quarantine, not evidence deletion. Only commands applicable to the
successfully completed setup prefix may run, in safety-first containment order.

```text
/usr/bin/chmod 0000 @OPERATIONAL_RELEASE_ROOT@/bin/cpu_prefetch_q15_controller
/usr/bin/chmod 0000 /etc/cpu-prefetch/q15/allowed_signers
/usr/sbin/usermod --lock --expiredate 1 cpu-prefetch-q15-controller
/usr/sbin/usermod --lock --expiredate 1 cpu-prefetch-q15-custodian
/usr/sbin/usermod --lock --expiredate 1 cpu-prefetch-q15-auditor
/usr/sbin/usermod --lock --expiredate 1 cpu-prefetch-q15-operator
/usr/bin/chmod 0000 /var/lib/cpu-prefetch/q15-r/controller-staging
/usr/bin/chmod 0000 /var/lib/cpu-prefetch/q15-r/sealed
/usr/bin/chmod 0000 /var/lib/cpu-prefetch/q15-r/receipts
/usr/bin/chmod 0000 /var/lib/cpu-prefetch/q15-r/audit
```

This intentionally does not claim full prestate restoration: restoring
account absence would require deletion. Q15-R-P2 accepted quarantine-only as
the prospective failure policy; executing it still needs setup authority. No `rm`, `userdel`, `groupdel`,
recursive chmod, evidence overwrite, or silent retry is proposed.

## Disposition of the original six setup-input groups

1. `CLOSED_BY_Q15_R_P3`: exact D-065 acceptance selects the verified clean
   no-authority adapter-bearing release as evidence only.
2. Exact allowed-signers bytes/hash, Ed25519 signer fingerprint, private-key
   custodian, and signature/receipt artifact contracts.
3. Exact secondary custody host/root/device/mount/owner/mode/quota/reserve and
   transfer endpoint.
4. Fresh current stand prestate for every executable, role, group, path,
   device, mount, and quota referenced by the transaction.
5. Literal replacement of all typed placeholders.
6. Named setup operator/authority, UTC issuance/expiry, output/evidence IDs,
   destination hashes, stand-hours, stop rules, and rollback acceptance.

The exact transaction graph is now bound in the blocked
[`stand-setup authorization preparation`](../config/q15/q15-r-stand-setup-authorization.preparation.json).
Only after all listed inputs exist may a separate executable authorization be
issued. Successful setup would still not authorize Q15-R.

## Verification

Repository-only checks:

```sh
cmake --build --preset dev-gcc --target q15-r-operational-prerequisite-check
cmake --build --preset dev-gcc --target q15-r-p2-acceptance-check q15-trust-anchor-adapter-profile-check q15-r-stand-setup-preparation-check
ctest --preset dev-gcc -L q15 --output-on-failure
```

Direct release-binding verification, when the already-created archive remains
locally available:

```sh
/tmp/cpu-prefetch-stage16-deps/python/bin/python tools/check_q15_r_operational_prerequisite.py --release-artifact-dir build/release-gcc/q15-qualification-tool-bundle
```

The proposal validator checks its byte-preserved four unselected inputs; the
acceptance record freezes their selected options. Together the checks cover 20 inert setup argv arrays,
the complete 24-probe/18-denial matrix, ten quarantine argv arrays, six
negative mutations, and—when requested—the exact archive, sidecar, manifest,
SBOM, source, binaries, report, internal inventory, and authority boundary.

## Accepted approval

```text
Q15-R-P2 - accept D-061 through D-064 in the Q15-R operational-prerequisite and role/custody decision bundle. Authorize repository-local implementation and verification of Q15-R-TRUST-ANCHOR-ADAPTER-v1, synchronization of no-authority release/setup records, and preparation of an exact stand-setup authorization bundle only. Do not access or modify the stand, create accounts or keys, transfer or install artifacts, execute access probes, issue/sign/execute Q15-R or Q15-W, use real PMU/MSR/affinity/NUMA operations, calibrate, pilot, measure, or perform confirmatory work. Stand setup and every later phase require separate explicit approval.
```

The next record is not implied by this acceptance. A later owner decision must
separately authorize the fully resolved stand-setup record. There remains no
approval here for the proposed setup commands, access probes, or Q15-R.
