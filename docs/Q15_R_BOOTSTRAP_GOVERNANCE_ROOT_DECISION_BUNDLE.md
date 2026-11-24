# Q15-R bootstrap governance-root decision/input bundle

Status: **`SUPERSEDED_BEFORE_ACCEPTANCE_BY_D093; IMMUTABLE_PROPOSAL_PRESERVED`**

This was the proposed external gate after Q15-R-P4-K-A-D and is retained as an
immutable predecessor. D-093's exact supersession is recorded below. The
machine-readable bundle is
[`q15-r-bootstrap-governance-root-decision-input-v1.json`](../config/q15/q15-r-bootstrap-governance-root-decision-input-v1.json),
SHA-256
`065d8a6d5f882bff84ee9bdbe27eb0e0c9e2bfea56c58cbe2b9bfc61cab3a4b7`.

The generic P4-K-A controller is implemented locally under ADR-0086, but its
admission requires a qualifying bootstrap signature. The owner explicitly
reported that no such signer exists. Software cannot truthfully create genesis
authority, a witness, an owner-controlled offline environment, or custody
evidence on the repository host or experiment stand.

This bundle creates no key, trust artifact, path, signature, authorization, or
stand action. It never requests private bytes, a private path, a passphrase, or
a seed.

## Proposed decisions

| ID | Decision | Recommendation | Required external evidence before action |
|---|---|---|---|
| D-087 | Genesis authority and non-self-authorization | Use a verifiable existing owner external identity plus distinct auditor if available; otherwise an in-person dual-control genesis ceremony with a hash-bound signed receipt | Exact identity method, attestation bytes/hash, witnesses, auditor review, unused transaction ID |
| D-088 | Roles and custody separation | Three distinct named roles, owner-offline primary custody, and independently controlled recovery custody | Literal principal/domain IDs and non-secret access, recovery, retention, destruction evidence |
| D-089 | Offline environment and toolchain | Dedicated owner-controlled offline Linux/OpenSSH environment with exact hashed inventory and network unavailable | Environment ID, OS/tool/library versions and hashes, fixed argv, output-format and network evidence |
| D-090 | Private-key protection and recovery | Encrypted Ed25519, uncaptured interactive secret, exact KDF, dual-control recovery, and lifecycle receipts | Encoding/KDF work, secret boundary, backup/recovery/rotation/destruction policy and receipts |
| D-091 | Public trust artifact | Unique create-exclusive public export containing the root public key, fingerprint, canonical single-entry allowed-signers bytes, receipts, and sidecars scoped to `cpu-prefetch-q15-authorization` | Unused public transaction/path IDs, exact public bytes/fingerprint/trust bytes and SHA-256 |
| D-092 | Lifecycle and compromise governance | Append-only versioned status ledger with separately reviewed activation, rotation, revocation, recovery, and compromise stop | Accepted authorities, status/receipt formats, recovery and dependent-authorization invalidation policy |

Full classifications, options, scientific and compatibility effects, owners,
deadlines, and supersession rules are preserved in the machine record. Every
scientific effect is none.

## Eight external inputs remain null

The bundle requires but does not invent:

1. genesis identity method and signed attestation evidence;
2. distinct genesis operator, root custodian, and auditor identities;
3. primary and recovery offline custody evidence;
4. offline environment and exact toolchain/network evidence;
5. key encoding, KDF work, secret boundary, recovery, rotation, and destruction
   policy;
6. create-exclusive public export transaction, paths, and artifact IDs;
7. root public bytes, fingerprint, canonical allowed-signers bytes, and hashes;
8. distinct auditor genesis and public-trust review evidence.

## Smallest external response needed

Policy answers alone cannot close this gate; the available real-world identity
and custody mechanism must be known first. Provide only non-secret facts:

```text
BGR-Q1=<EXISTING_VERIFIABLE_OWNER_EXTERNAL_IDENTITY or IN_PERSON_DUAL_CONTROL>;
BGR-Q2=<distinct public role IDs and custody-domain IDs>;
BGR-Q3=<offline environment evidence artifact ID and SHA-256>;
BGR-Q4=<key-protection/KDF/recovery policy artifact ID and SHA-256>;
BGR-Q5=<unused public-export transaction ID and absolute public root>;
BGR-Q6=<lifecycle/revocation policy artifact ID and SHA-256>.
```

Do not provide a private-key path, private bytes, passphrase, seed, credential,
or secret recovery material. If no verifiable owner identity plus distinct
auditor or in-person dual-control ceremony is available, this gate remains
blocked and P4-K-A cannot become issuable.

## Repository-local verification

```sh
cmake --build --preset dev-gcc \
  --target q15-r-bootstrap-governance-root-decision-check
ctest --preset dev-gcc \
  -R '^q15\.r_bootstrap_governance_root_decision$' \
  --output-on-failure
```

The checker validates immutable lineage, exact D-087 through D-092 order,
eight null inputs, six unanswered questions, and fail-closed authority. It does
not access an identity provider, offline environment, key, trust artifact,
path, stand, or experiment system.

## D-093 supersession and completed bounded action

On 2026-08-25 the owner accepted D-093, superseding this unaccepted proposal's
bootstrap-genesis recommendations while preserving its bytes. D-093 explicitly
allows one owner to hold all three roles, development-host creation, an
unencrypted OpenSSH Ed25519 private key, and no independent recovery. The owner
accepted the critical impersonation and key-loss risks.

Exactly one create-exclusive action completed under authorization SHA-256
`271584663d21718357b6fcf013ca0a83a842410cae24d9463b4723217cdb954e`.
The public fingerprint is
`SHA256:JuRM4SuWL9C1xvOes9z+CAKZV1rvel27VZ/+qiuVNs0`. The repository evidence
record contains public hashes and only private-file metadata; no repository
tool read or hashed private contents. D-093 stopped with lifecycle state
`CREATED` and no signature; D-094 below records the later activation. Every
signing/action gate still requires separate exact authorization.

```sh
cmake --build --preset dev-gcc \
  --target q15-r-bootstrap-d093-authorization-check \
           q15-r-bootstrap-d093-evidence-check
ctest --preset dev-gcc \
  -R '^q15\.r_bootstrap_d093_(authorization|evidence)$' \
  --output-on-failure
```

The create tool is intentionally absent from these commands. It must not be
run again for this transaction.

## D-094 activation result

The owner's subsequent exact-next-step delegation accepts ADR-0094. The
append-only lifecycle successor binds the verified D-093 fingerprint and
public trust hashes and transitions `CREATED` to `ACTIVE` at
`2026-08-25T20:06:42Z`. No private-key read, hash, copy, use, or signature was
performed. Active means eligible for a future separately authorized SSHSIG
action; it is not current signing or P4-K-A authority.

The versioned P4-K-A successor resolves exactly the bootstrap signer/trust
input and preserves the original target-key contract. It remains unissued with
six inputs null.

```sh
cmake --build --preset dev-gcc \
  --target q15-r-bootstrap-d094-activation-check
ctest --preset dev-gcc \
  -R '^q15\.r_bootstrap_d094_activation$' \
  --output-on-failure
```
