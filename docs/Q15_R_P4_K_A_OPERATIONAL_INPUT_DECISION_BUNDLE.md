# Q15-R-P4-K-A operational-input and ceremony decision bundle

Status: **`ACCEPTED_POLICY_BLOCKED_NO_QUALIFYING_BOOTSTRAP_SIGNER_NO_OPERATIONAL_AUTHORITY`**

This is the next safe repository-local gate after Q15-R-P4-K-D. It does not
execute or authorize the offline ceremony. The machine-readable proposal is
[`q15-r-p4-k-a-operational-input-decision-v1.json`](../config/q15/q15-r-p4-k-a-operational-input-decision-v1.json),
SHA-256
`8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.

The proposal does not access or inventory an offline environment, discover or
use a bootstrap signer, read/generate/import/copy/fingerprint a key, collect a
private path/passphrase/seed, create a public artifact or path, sign or issue
an authorization, access the stand, or authorize P4-K-A, P4-K-R, P4-R, P5,
Q15, calibration, pilot, measurement, or confirmatory work.

Q15-R-P4-K-A-D accepted the recommendations on 2026-08-25. The separate
machine-readable acceptance is
[`q15-r-p4-k-a-d-acceptance-v1.json`](../config/q15/q15-r-p4-k-a-d-acceptance-v1.json),
SHA-256
`c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
ADR-0080 through ADR-0085 record the policies. The owner explicitly selected
`NO_QUALIFYING_BOOTSTRAP_SIGNER_REMAIN_BLOCKED`; P4-K-A therefore remains
blocked pending a separately governed bootstrap root. The response did not
authorize controller implementation or any external action.

## Immutable predecessor boundary

- Q15-R-P4-K-D acceptance SHA-256:
  `11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`.
- Still-unissued P4-K-A template SHA-256:
  `7669a2f693a7ffca3fa583ec3ed7a45e1ea130a51ee009ac33a77b936409ccb5`.
- Still-unissued P4-K-R template SHA-256:
  `ae71ce73cf0636294995c0ca3311d4ccf6f857916c07fe9df67bb9682d20efcf`.
- ADR-0076 through ADR-0079 SHA-256 values are hash-bound in the machine
  proposal.

The target key does not exist and cannot authorize its own creation. Chat
approval, SSH reachability, root access, or the later target public key cannot
substitute for an independently established bootstrap signer and trust record.

## Accepted material decisions

| ID | Subject | Options | Recommendation | Scientific effect | Compatibility effect | Owner and gate | Supersession |
|---|---|---|---|---|---|---|---|
| D-080 | Offline environment and toolchain | Dedicated owner-controlled offline Linux/OpenSSH environment; exact alternative compatible toolchain; uninventoried online/stand tool; remain blocked | Dedicated offline Linux plus pre-provisioned OpenSSH-compatible Ed25519 tooling; exact environment, OS, executable/library hashes, versions, and network-unavailable evidence before authorization | None | Environment/tool bytes, versions, dependencies, network state, and output format become ceremony identity | Security/custody/release/audit; before controller specialization and P4-K-A | Any environment/tool/network/output change requires new inventory and prospective review |
| D-081 | Private-key protection and custody evidence | Encrypted OpenSSH Ed25519 plus uncaptured interactive secret; compatible nonexporting alternative; unencrypted/recorded secret; remain blocked | Encrypted OpenSSH private key, later exact KDF-work value, uncaptured interactive passphrase, and non-secret custody/control/recovery receipt without private path or bytes | None | Key encoding/KDF, secret boundary, controls, recovery/retention policy, and receipt become identity | Security/custody/audit; before controller freeze and P4-K-A | Any protection/secret/custody/recovery change requires new evidence and acceptance |
| D-082 | Public export identity and paths | Unique create-exclusive off-repository/off-stand public root; equivalent independent domain; repository/stand/temp/reused root; remain blocked | One unused action ID and absolute create-exclusive public export root; freeze public basenames and receipts while never serializing the private path | None | IDs, public paths, owner/mode/access, collision, basenames, sidecars, and receipts become identity | Custody/security/audit; before specialization or artifact creation | Any path/ID/access/retention change requires a new unused transaction identity |
| D-083 | Bootstrap signer/trust | Existing distinct reviewed governance signer; separately establish a bootstrap root first; target self-sign/root/SSH/chat; remain blocked | Require an already established distinct offline Ed25519 governance signer with public fingerprint, canonical trust bytes/hash, custody, principal/namespace compatibility, and independent review; otherwise stop before P4-K-A | None | Bootstrap key/fingerprint/trust bytes, custody, signature profile, and review become authorization identity | Security/protocol/custody/audit; blocks signing/issuance | Any signer/trust/custody/profile/reviewer change requires new unsigned bytes and acceptance |
| D-084 | Fixed controller/action graph | Hash-bound no-shell fixed controller; equivalent reviewed fixed argv; ad hoc shell/retry/unbounded environment; remain blocked | After separate acceptance, implement a no-authority fixed controller with exact absolute tool/argv/environment and secret TTY/FD boundary, create-exclusive public output, bounded evidence, one attempt, zero retry, and mandatory stop | None | Controller bytes, tool/argv/env/FD contract, bounds, order, and receipt become transaction identity | Security/repository/custody/audit; acceptance before local implementation | Any byte/command/FD/order/bound/retry change requires a clean release and prospective decision |
| D-085 | Issuance, review, failure evidence | Distinct pre-review and exact 1,800-second SSHSIG action; stronger compatible policy; unsigned/renewable/self-review/delete/continue; remain blocked | Bind every input into canonical authorization bytes, require distinct pre-review, literal UTC instants exactly 1,800 seconds apart, SSHSIG verification, first-failure append-only receipt, no cleanup/retry, and stop for P4-K-R | None | Authorization bytes/hash, instants, signer/signature/review hashes, receipts, and stop disposition become identity | Protocol/security/custody/audit; policy before specialization, literals at issuance | Any authority/time/signature/review/failure/retention change requires new bytes and acceptance |

Every row's full classification, options, evidence, owner, deadline,
compatibility effect, and supersession rule is retained in the machine record.
ADR-0080 through ADR-0085 retain these decisions and the acceptance boundary.

## Seven P4-K-A inputs remain null

The proposal maps but does not fill:

1. exact ceremony/public-extraction tools, versions, hashes, and fixed argv;
2. create-exclusive public artifact IDs and absolute public source paths;
3. offline custody-control and ceremony-environment evidence;
4. bootstrap signer fingerprint and trust-evidence hash;
5. literal issue and expiry UTC instants;
6. canonical authorization and detached-signature hashes; and
7. distinct auditor pre-execution review artifact and hash.

Items 1 through 4 require external owner/security/custody evidence. Items 5
through 7 can exist only at a later issuance/review gate. None may be inferred.
Never submit private-key bytes, a seed, a passphrase, a private-key path, or a
credential.

## Recorded owner response

- `P4KA-Q1=ACCEPT_D080_RECOMMENDATION`
- `P4KA-Q2=ACCEPT_D081_RECOMMENDATION`
- `P4KA-Q3=ACCEPT_D082_RECOMMENDATION`
- `P4KA-Q4=NO_QUALIFYING_BOOTSTRAP_SIGNER_REMAIN_BLOCKED`
- `P4KA-Q5=ACCEPT_D084_D085_RECOMMENDATIONS`

The response accepts policy and permits its repository-local acceptance/ADR
recording. It does not include the broader controller implementation scope
that the proposal recommended asking for. That implementation and every
external-input, key, trust, signature, stand, and execution action remain
separate gates.

## Repository-local verification

```sh
cmake --build --preset dev-gcc \
  --target q15-r-p4-k-a-operational-input-decision-check \
           q15-r-p4-k-a-d-acceptance-check
ctest --preset dev-gcc \
  -R '^q15\.r_p4_k_a_(operational_input_decision|d_acceptance)$' \
  --output-on-failure
```

The checker validates Draft 2020-12 structure, immutable acceptance/template/
ADR hashes, exact D-080 through D-085 ordering, seven null inputs, five
unanswered owner questions, non-self-authorization, one-attempt/zero-retry and
mandatory-stop rules, and fifteen negative mutations. It performs no external,
key, trust, filesystem, network, stand, signing, or execution action.

The acceptance checker separately binds the exact six selected policies, five
owner responses, immutable proposal/templates, ADR hashes, seven null inputs,
and Q4's blocked bootstrap disposition. Nineteen negative mutations reject
controller implementation authority, external evidence, signer/trust claims,
self-authorization, premature unblocking, and every operational scope.
