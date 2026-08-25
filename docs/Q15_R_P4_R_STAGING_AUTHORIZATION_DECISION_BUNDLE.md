# Q15-R-P4-R staging and stand-prestate authorization decision bundle

Status: **`D072_D075_ACCEPTED_REPOSITORY_LOCAL_TEMPLATES_ONLY_NO_STAND_OR_EXECUTION_AUTHORITY`**

This is the exact repository-local decision/input bundle requested after
Q15-R-P4-E. It is bound to governance commit
`f30036e31acc8ae036f2f31086d493eeb30db9d7` and immutable no-authority v3
archive SHA-256
`f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`.
The machine-readable proposal is
[`q15-r-p4-r-staging-authorization-decision-input-v1.json`](../config/q15/q15-r-p4-r-staging-authorization-decision-input-v1.json).

The proposal bytes remain immutable and retain their historical `PROPOSED`
state. Q15-R-P4-F separately accepts D-072 through D-075 at acceptance-record
SHA-256
`ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`.
ADR-0072 through ADR-0075 record the accepted template choices. The exact
literals are frozen, but no authorization is issued and they are not
operational. No stand was contacted; no path, key, signature, account, or
evidence artifact was created. The existing P4-R v2 preparation retains seven
unresolved inputs, and P4-K retains all eight unresolved inputs.

## Why the future operation is split

The latest stand inventory was collected on 2026-08-22. It is useful lineage
but is not fresh execution authority. The accepted P4-R contract also requires
a detached signature and independent review, while P4-K still has no selected
key, fingerprint, allowed-signers bytes, or custody evidence. An omnibus
approval would therefore either use stale identity or fabricate a signature
dependency.

The recommended graph has two non-collapsible future authorizations:

1. `Q15-R-P4-R-I` may collect four fixed read-only identity observations and
   the pinned SSH host-key fingerprint. It authorizes no transfer, directory
   creation, self-test, or collector execution. It stops for independent
   review.
2. `Q15-R-P4-R-C` may later bind the accepted fresh identity artifact and its
   review hash, create one unique staging tree, transfer and verify the exact
   v3 bytes, run the two non-collecting self-tests, and invoke `--collect`
   exactly once. It requires another exact signed authorization and approval.

Acceptance of this decision bundle authorizes neither gate. The generated
P4-R-I and P4-R-C successor templates are both explicitly still unissued.

## Accepted material decisions

| ID | Subject | Recommended selection | Scientific effect | Compatibility effect | Owner | Gate and supersession |
|---|---|---|---|---|---|---|
| D-072 | Literal staging and release paths | One create-exclusive root-owned transaction tree under `/root/cpu-prefetch-q15-r-p4-r/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01`; no `latest` link, reuse, or activation | None | Endpoint, archive/extraction/collector paths, owner/mode, collision policy, and absence of activation become transaction identity | Platform, release, security, audit | Before transfer or stand path creation; any path/layout/byte/mode change requires a new prospective bundle |
| D-073 | Capture and custody paths | Reserve `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01` once; capture complete stdout/stderr into the exact development-repository custody paths; add sidecar, transfer receipt, and independent review without rewriting source bytes | None | Capture ID, absolute paths, basenames, byte-handling, receipt, and review identity freeze | Custody, audit, repository, platform | Before creating any capture artifact; any path/ID/domain change requires a new unused identity |
| D-074 | Authority, validity, signature, review | `cpu-prefetch-q15-operator`; one nonrenewable 1,800-second UTC window; accepted Ed25519/SHA-512 SSHSIG principal/namespace; distinct `cpu-prefetch-q15-auditor` review; private key off-stand | None | Principal, scheme, canonicalization, window, fingerprint, authorization/signature/review hashes become identity | Protocol, platform, security, custody, audit | Before either future authorization; any policy/key/principal change requires prospective supersession and new bytes |
| D-075 | Execution graph, verification, rollback, stop | Fresh read-only identity and stop, then separately approved create-exclusive staging plus one collector attempt; zero retry; stop and retain partial bytes without delete/reuse/cleanup | None | Split predecessors, action order, limits, stop conditions, partial preservation, and rollback semantics freeze | Protocol, platform, security, release, custody, audit | Before any stand command; graph/limit/retry/rollback drift requires new prospective authorization |

Options considered, evidence, full owner lists, deadlines, and supersession
rules are retained in the machine record. None changes the imported protocol or
scientific semantics.

## Exact proposed literals

### Endpoint and release source

- Stand: `root@185.184.131.153`, bound to stand ID `XEON-CPU-FETCH`.
- Bootstrap account role: transport only; root/SSH access is not authority or
  custody.
- Local archive:
  `/home/omaltsev/research/cpu_prefetch_research_code/build/release-gcc/q15-qualification-tool-bundle/cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1.tar.gz`.
- Local sidecar: the same path with `.sha256` appended.
- Expected archive size: `4642298` bytes.
- Expected archive SHA-256:
  `f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`.

### Stand staging paths

- Transaction root:
  `/root/cpu-prefetch-q15-r-p4-r/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01`.
- Incoming root: transaction root plus `/incoming`.
- Extraction parent: transaction root plus `/release`.
- Collector release root: extraction parent plus
  `/cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1`.
- Collector executable: collector release root plus
  `/release/bin/cpu_prefetch_q15_prestate_collector`.

Every component is create-exclusive and must be absent and nonsymlinked. The
future operational root `/var/lib/cpu-prefetch/q15-r` is not selected, created,
or modified. No activation path or mutable alias is permitted.

### Capture and custody paths

The proposed custody root is:

`/home/omaltsev/research/cpu_prefetch_research_code/docs/evidence/stage17/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01`

It would contain:

- `Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json` and `.sha256`;
- `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01.json` for exact collector stdout;
- `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01.stderr.bin` for exact stderr bytes;
- `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01.json.sha256`;
- `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01.transfer-receipt.json`; and
- `Q15-R-P4-R-XEON-CPU-FETCH-20260825-01.independent-review.json`.

All destinations must be absent. No command may overwrite, append to, rename,
or reuse an existing artifact. This proposed P4-R custody location does not
claim that the future Stage A two-domain storage gate has passed.

## Principal, UTC, signature, and review contract

| Field | Proposed value or rule |
|---|---|
| Named authority | `cpu-prefetch-q15-operator` |
| Bootstrap transport | `root`; never treated as authority, signer, custodian, or reviewer |
| Custodian | `cpu-prefetch-q15-custodian` |
| Independent reviewer | `cpu-prefetch-q15-auditor` |
| Authorization canonicalization | `JCS-I64-v1` |
| Signature | `OPENSSH-SSHSIG-ED25519-SHA512-v1` |
| SSHSIG principal and namespace | `cpu-prefetch-q15-authorization` |
| Private key | Off-stand only |
| Validity | Exact issue/expiry instants set before signing; expiry is issue plus `1800` seconds |
| Reuse/renewal | Forbidden |
| Collector watchdog | `900` seconds inside the authorization window |
| Expiry | Stop, preserve partial bytes, and do not retry |

The actual issue/expiry instants, authorization SHA-256, signer fingerprint,
detached-signature SHA-256, and independent-review SHA-256 remain null. P4-K
must first supply accepted signer/custody evidence. A distinct reviewer must
recompute the authorization hash, verify SSHSIG, check every lineage hash and
literal path, verify role separation, and emit a canonical review receipt
before any stand access.

## Fresh identity gate

The proposed `Q15-R-P4-R-I` record contains exactly four read-only observation
vectors:

```text
/usr/bin/hostname
/usr/bin/uname --kernel-name --kernel-release --machine
/usr/bin/stat --format=%n|%F|%a|%u|%g|%s|%d|%i -- / /root /dev/md3
/usr/bin/findmnt --json --target / --output TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION
```

It must also bind the pinned SSH host-key fingerprint. Its output and review
hashes are unknown until separately authorized acquisition and therefore stay
null. Collection stops after this artifact. No automatic continuation to
staging is permitted.

## Transfer and verification contract

Only a later signed `Q15-R-P4-R-C` may perform the following exact ordered
actions:

1. Validate the unexpired signed authorization and its independent review
   before opening the transport.
2. Verify the pinned SSH host key and accepted fresh identity predecessor.
3. Reject every existing or symlinked transaction, staging, extraction,
   custody, or artifact path.
4. Create only the exact transaction, incoming, and extraction-parent
   directories with mode `0700`.
5. Transfer the archive and sidecar once to the exact incoming paths.
6. Recompute the remote size and SHA-256 and compare the literal sidecar line.
7. Reject archive members outside the single accepted top-level directory and
   any absolute, `..`, device, FIFO, hard-link, or symbolic-link member.
8. Extract once into the empty exact parent without archive owner/permission
   preservation.
9. Verify the complete internal `SHA256SUMS` and all bound collector, contract,
   validator, manifest, SBOM, and code-generation hashes.
10. Run `--self-test` and `--describe-contract` only and compare their exact
    accepted identities.
11. Prove a direct fixed-argv, no-shell, fixed-environment launch path, then
    invoke `--collect` once and capture complete stdout and stderr off-stand.
12. Validate the canonical artifact, zero-self SHA-256, command prefix, limits,
    completion/partial state, and sidecar.
13. Emit the transfer receipt and independent review without promotion into an
    operational release root.

The collector invocation remains a template until a signed authorization
exists. Its authorization-hash argument is
`@AUTHORIZATION_SHA256_FROM_ISSUED_Q15_R_P4_R_C@`; all other argv are literal.
Direct fixed-argv transport evidence is itself unresolved and blocks
execution. A shell command string, interpolation, glob, inherited environment,
retry, or alternate collector path is ineligible.

## Rollback and stop behavior

Before mutation, any failure stops with no stand change. After staging starts,
failure stops and preserves all exact partial staging and custody bytes. It
does not delete, overwrite, rename, reuse, automatically clean up, or claim
restoration. The staging tree has no activation path and does not touch an
existing operational installation; any future cleanup requires its own exact
authorization.

The machine record freezes eleven stop-condition groups covering authority,
P4-K, host/identity, role separation, paths, every release hash, self-tests,
direct argv transport, time/resource/network failures, artifact/custody/review
failures, and any request to widen scope. A `FULL` outcome, queue behavior,
latency, calibration, or scientific result is not part of this action.

## Inputs that remain unresolved

Q15-R-P4-F resolves only the first proposal prerequisite: explicit D-072
through D-075 acceptance. The still-unissued P4-R-I template retains six null
groups for pinned host evidence, bootstrap transport evidence, P4-K evidence,
literal UTC instants, canonical authorization/signature hashes, and fixed-argv
transport/distinct-review evidence. The P4-R-C template separately retains six
null groups for host/transport evidence, P4-K, UTC instants,
authorization/signature hashes, accepted fresh P4-R-I artifact/review hashes,
and fixed-argv transport/distinct-review evidence.

These are blockers, not defaults. Q15-R-P4-F cannot fill or authorize them.

## Exact accepted statement

Q15-R-P4-F was accepted exactly as follows:

> Q15-R-P4-F — accept D-072 through D-075 in the exact Q15-R-P4-R staging and
> read-only stand-prestate authorization decision bundle, bound to governance
> commit f30036e31acc8ae036f2f31086d493eeb30db9d7 and immutable v3 archive
> SHA-256 f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a.
> Accept the exact create-exclusive stand staging tree, fixed capture and
> development-custody paths, cpu-prefetch-q15-operator named authority,
> nonrenewable 1800-second UTC policy, accepted OpenSSH SSHSIG profile with
> distinct auditor review, and split P4-R-I identity then P4-R-C one-shot
> staging/collection graph with stop-retain-no-delete rollback. Authorize
> repository-local creation and verification of acceptance, ADR, and
> still-unissued successor authorization templates only. Do not access or
> modify the stand, create paths, transfer or extract artifacts,
> execute self-tests or the collector on the stand, create/import/copy/use
> keys, sign or issue P4-R-I/P4-R-C/P4-K/Q15-R/Q15-W, perform platform
> controls, calibrate, pilot, measure, or perform confirmatory work. Every
> external-input, signature, and execution phase requires a later separate
> exact approval.

That acceptance grants no stand or execution authority. P4-R-I,
P4-K, and P4-R-C each require a later separate exact authorization.

## Repository-local verification

```sh
cmake --build --preset dev-gcc \
  --target q15-r-p4-r-staging-authorization-decision-check \
           q15-r-p4-f-acceptance-check \
           q15-r-p4-r-successor-templates-check
ctest --preset dev-gcc \
  -R '^q15\.r_p4_(r_staging_authorization_decision|f_acceptance|r_successor_templates)$' \
  --output-on-failure
```

An optional read-only local archive check is:

```sh
/tmp/cpu-prefetch-stage16-deps/python/bin/python \
  tools/check_q15_r_p4_r_staging_authorization_decision.py \
  --archive-path \
  build/release-gcc/q15-qualification-tool-bundle/cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1.tar.gz
```

The proposal checker validates Draft 2020-12 structure, immutable lineage,
exact paths, principal/validity/signature boundaries, split unissued gates,
one-shot limits, rollback/stop policy, all seven proposal inputs, and fifteen
negative mutations. The acceptance checker adds seven authority/lineage/value
negatives. The successor checker validates two Draft schemas, exact ADR and
predecessor hashes, six null inputs per template, and twelve split/authority/
retry/rollback mutations. Optional archive mode also checks size, SHA-256,
sidecar, single top-level layout, and unsafe member absence. No check contacts
the stand or executes the collector.
