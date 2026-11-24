# Q15-R-P4-K offline signer and custody decision/input bundle

Status: **`PROPOSED_D076_D079_OWNER_INPUTS_REQUIRED_NO_KEY_OR_EXECUTION_AUTHORITY`**

Disposition: **`ACCEPTED_BY_Q15_R_P4_K_D_REPOSITORY_LOCAL_POLICY_AND_UNISSUED_TEMPLATES_ONLY`**.
The immutable proposal remains unchanged at the hash below. Acceptance record
SHA-256 is
`11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`;
ADR-0076 through ADR-0079 record the selections. P4-K-A and P4-K-R remain
unissued at SHA-256 `7669a2f693a7ffca3fa583ec3ed7a45e1ea130a51ee009ac33a77b936409ccb5`
and `ae71ce73cf0636294995c0ca3311d4ccf6f857916c07fe9df67bb9682d20efcf`.
No operational authority follows.

This is the next safe repository-local gate after Q15-R-P4-F. It prepares the
owner decisions required before any P4-K key or public-artifact action can be
specified. The machine-readable record is
[`q15-r-p4-k-decision-input-v1.json`](../config/q15/q15-r-p4-k-decision-input-v1.json),
SHA-256
`cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5`.

The bundle does not read, generate, import, copy, fingerprint, or use a key. It
does not construct an allowed-signers artifact, select an actual public-artifact
path, sign or issue an authorization, access the stand, or authorize P4-R-I,
P4-R-C, P4-K-A, P4-K-R, setup, Q15-R, Q15-W, calibration, pilot, measurement,
or confirmatory work. Do not send private-key bytes, a passphrase, a seed, or
any other secret in an approval response.

## Immutable lineage and accepted constraints

- P4-K preparation SHA-256:
  `c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f`.
- Q15-R-P4-D acceptance SHA-256:
  `1645c2a7fb356272afbf9377b99784e307f54f8a7df5fbb09f46d70edae3c521`.
- Q15-R-P4-F acceptance SHA-256:
  `ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`.
- ADR-0066 permits only an owner-selected existing offline Ed25519 key or a
  separately authorized new offline ceremony. The private key never enters the
  stand or repository.
- ADR-0070 requires canonical allowed-signers bytes, independent SHA-256 and
  fingerprint verification, and later installed-byte equality.
- The fixed destination remains `/etc/cpu-prefetch/q15/allowed_signers`, owned
  by `root:cpu-prefetch-q15-auditor` with mode `0640`. This bundle does not
  create or install it.

## Proposed material decisions

| ID | Subject | Options | Recommendation | Scientific effect | Compatibility effect | Owner and gate | Supersession |
|---|---|---|---|---|---|---|---|
| D-076 | Offline Ed25519 key source mode | Existing qualifying owner-controlled offline key; separately authorized new offline ceremony; remain blocked | Prefer an existing key only if complete provenance/custody/rotation/public-key evidence exists; otherwise use a later separately authorized new offline ceremony | None | Public bytes, fingerprint, source/custody lineage, and rotation identity become authorization identity | Security/custody owners; before any key action | New key/source/custody/rotation requires new evidence, acceptance, and signatures |
| D-077 | Custody domain, custodian, and public-artifact path boundary | Owner-supplied non-stand domain/distinct custodian/create-exclusive future public path; repository/stand private-key custody or inferred path; remain blocked | Supply literal domain and custodian identifiers now; select the absolute public allowed-signers source path only after its construction is separately authorized | None | Domain, custodian, public path, access and receipt policy become evidence identity | Security/custody/audit owners; before P4-K-A | Domain/custodian/path/policy changes require a new unused artifact identity |
| D-078 | Acquisition, construction, review, and installation graph | One P4-K-A action then stop for distinct P4-K-R review; omnibus action; retry/repair; remain blocked | Split one source-mode-specific acquisition/construction attempt from independent review; installation and signing stay later gates | None | Gate split, commands/tools, one-attempt rule, public bytes, hashes, fingerprint, artifact IDs, and review receipt become transaction identity | Security/custody/audit owners; before P4-K-A/P4-K-R templates | Graph/tool/retry/canonicalization/review changes require prospective supersession |
| D-079 | Named authority and validity | Existing operator/1,800-second/JCS/SSHSIG/distinct-auditor profile; a different explicit owner policy; root/SSH as authority; unsigned/renewable/self-review; remain blocked | Extend the accepted Q15-R governance profile to P4-K without filling actual UTC instants or hashes | None | Principal, duration, canonicalization, signature, issued/expiry instants, authorization/signature/review hashes become identity | Protocol/security/custody/audit owners; before P4-K issuance | Any principal/duration/scheme/review change requires new unsigned bytes and acceptance |

Every decision retains its options, evidence, owner, deadline, scientific and
compatibility effects, and supersession rule in the machine record. No ADR is
created until the owner answers the minimum questions and accepts the choices.

## Eight inputs remain null

The immutable P4-K preparation and this proposal both retain:

1. source mode;
2. private-key custody domain and custodian identity;
3. Ed25519 public-key artifact ID, bytes, and SHA-256;
4. Ed25519 SHA-256 fingerprint;
5. canonical allowed-signers artifact ID, bytes, and SHA-256;
6. absolute public allowed-signers source path for later setup;
7. independent-review artifact ID and SHA-256; and
8. named authority, issue instant, and expiry instant.

The first two require owner input. Items 3 through 7 require later authorized
artifact work and evidence. Item 8 requires accepted policy plus later literal
UTC instants. None may be inferred from the repository, the stand, SSH access,
or the current date.

## Proposed split gate graph

1. `Q15-R-P4-K-D` selects D-076 through D-079 and may authorize only a
   repository-local acceptance record, one ADR per accepted material decision,
   and still-unissued successor templates.
2. `Q15-R-P4-K-A` is a later source-mode-specific, exact, signed authorization
   for one offline acquisition/construction attempt. It is not prepared or
   issued by this bundle.
3. `Q15-R-P4-K-R` is a later distinct independent review of the exact public
   bytes, hashes, fingerprint, custody evidence, and canonical allowed-signers
   artifact. It cannot be collapsed into P4-K-A.
4. `Q15-R-P5` remains the separate later stand-setup/installation gate. P4-K
   acceptance or review never installs an artifact.

Failure stops and preserves append-only public evidence. Retry, repair,
overwrite, key rotation, cleanup, installation, signing, or continuation into
another gate requires separate prospective authority.

## Historical minimum owner response (resolved by Q15-R-P4-K-D)

The proposal requested the following three items. The accepted disposition
selects the new-ceremony token, logical domain
`OWNER-OFFLINE-Q15-KEY-CUSTODY`, custodian
`cpu-prefetch-q15-custodian`, and the D-078/D-079 recommendations. No secret or
key material was supplied.

- `P4K-Q1`: choose exactly one:
  `EXISTING_OWNER_CONTROLLED_OFFLINE_ED25519_WITH_COMPLETE_CUSTODY_EVIDENCE`
  or
  `NEW_OFFLINE_ED25519_KEY_CEREMONY_UNDER_LATER_SEPARATE_EXACT_AUTHORIZATION`.
- `P4K-Q2`: provide `custody_domain_id` and `custodian_principal_id`. They must
  identify a non-stand custody domain and its custodian. Do not provide the
  private-key path or bytes.
- `P4K-Q3`: answer `ACCEPT_D078_D079_RECOMMENDATIONS` or describe the requested
  revision.

The historical safe response form was:

```text
Q15-R-P4-K-D — P4K-Q1=<one exact source-mode token>;
P4K-Q2 custody_domain_id=<non-secret ID>,
custodian_principal_id=<non-secret ID>;
P4K-Q3=ACCEPT_D078_D079_RECOMMENDATIONS.
Accept D-076 through D-079 for repository-local acceptance/ADR and
still-unissued P4-K-A/P4-K-R template preparation only. Do not read, generate,
import, copy, fingerprint, or use keys; create public-key or allowed-signers
artifacts; access or modify the stand; create paths; sign or issue any gate;
perform P4-R-I/P4-R-C/P4-K-A/P4-K-R/P5/Q15-R/Q15-W; use platform controls;
calibrate, pilot, measure, or perform confirmatory work. Every key, artifact,
signature, stand, and execution action requires later separate exact approval.
```

## Repository-local verification

```sh
cmake --build --preset dev-gcc --target q15-r-p4-k-decision-input-check
ctest --preset dev-gcc \
  -R '^q15\.r_p4_k_decision_input$' \
  --output-on-failure
```

The checker validates Draft 2020-12 structure, immutable P4-K/P4-D/P4-F/ADR
lineage, exact ordered decisions and inputs, fixed accepted policy, split
future gates, unanswered owner questions, unchanged P4-R authority, and twelve
negative mutations. It performs no network, stand, filesystem, key, signature,
or platform action.
