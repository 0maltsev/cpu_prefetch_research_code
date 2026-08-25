# Q15-R-P4 external-input acquisition decision bundle

Status: `PROPOSED_OPEN_BEFORE_Q15_R_P4_NO_AUTHORITY`

This bundle is the next repository-local step after Q15-R-P3. It proposes how
to obtain and verify the five external inputs still null in
[`q15-r-stand-setup-authorization.preparation-v2.json`](../config/q15/q15-r-stand-setup-authorization.preparation-v2.json).
It does not choose a key, invent a path, access the stand, implement or run a
collector, install the release, or authorize Q15-R/Q15-W.

The machine-readable proposal is
[`q15-r-external-input-acquisition-decision-input-v1.json`](../config/q15/q15-r-external-input-acquisition-decision-input-v1.json).
Its schema and semantic checker require all five values to remain null and
reject any widened authority.

## Proposed decisions

| ID | Subject | Recommended option | Still required after acceptance |
|---|---|---|---|
| D-066 | Allowed-signers source and signer custody | Use an owner-selected offline Ed25519 public key; never create or store its private key on the stand | Actual public-key artifact/hash, custody domain, independent review, and later separate key/custody action authority |
| D-067 | Operational release root | Select an absolute content-addressed stand path only after fresh read-only prestate verifies the parent, filesystem, permissions, and collision state | Literal path and evidence; later transfer/install authority |
| D-068 | Secondary custody root | Select an absolute non-stand root controlled independently from the primary stand custody domain | Literal path, controlling principal, append-only policy, receipts, and access evidence |
| D-069 | Stand prestate | Implement a fixed argv-only no-mutation collector locally, then authorize one exact read-only stand execution separately | Accepted collector bytes, clean release, exact Q15-R-P4-R authorization, fresh artifact/hash, independent review |
| D-070 | Actual allowed-signers identity | Construct canonical bytes off-stand, hash them, derive the Ed25519 fingerprint independently, and require byte equality after installation | Actual artifact ID/hash/fingerprint, SSHSIG principal/namespace binding, independent verification |

Each record includes classification, options, evidence, scientific and
compatibility effects, owners, deadline gate, and supersession rule. These are
engineering/security/custody decisions. They do not reinterpret a scientific
decision or fill platform-dependent values.

## Fail-closed acquisition sequence

1. `Q15-R-P4-D`: accept or revise D-066 through D-070. Acceptance may authorize
   repository-local collector/validator implementation only.
2. Build, test, sanitize, audit, commit, and clean-package that no-authority
   collector. This produces bytes but no right to run them.
3. `Q15-R-P4-R`: separately approve one exact read-only stand-prestate
   collection, binding stand, bundle, collector, argv, time window, output
   custody, and stop conditions.
4. `Q15-R-P4-K`: separately approve the owner-selected offline signer/custody
   action. No private key may enter the stand.
5. Review the fresh prestate and signer artifacts, then make the literal D-067
   and D-068 choices. Create a versioned successor setup preparation with all
   five inputs and their evidence, not guessed defaults.
6. `Q15-R-P5`: separately approve the exact 20-command setup, 24 access tests,
   18 expected denials, and 10 quarantine/rollback commands.
7. Only after setup evidence passes may an exact signed read-only `Q15-R` be
   prepared for another approval. `Q15-W`, calibration, pilot, and
   confirmatory work remain later gates.

Steps 3 through 7 are not authorized by this decision bundle.

## Proposed prestate-collector boundary

The proposed collector is not implemented. Its contract requires canonical
JSON plus a SHA-256 sidecar, exact ordered argv, per-command UTC boundaries,
stdout, stderr, and exit status. It observes host/kernel identity, the four
accepted roles and group, accepted path metadata without following symlinks,
mount/filesystem identity, executable presence, free space, and collision
state.

It forbids shell interpretation, network access, package installation,
account/key/path mutation, ownership or permission changes, bundle transfer,
access probes, PMU/MSR access, affinity/NUMA control, service/boot changes,
calibration, pilot, measurement, and confirmation. A missing object is recorded
as evidence; it is never created or repaired by the collector.

## Exact approval statement offered

To accept the recommendations and authorize only the next repository-local
implementation slice, use exactly:

> Q15-R-P4-D — accept the recommended acquisition contracts in D-066 through
> D-070: owner-selected offline Ed25519 signer custody with no stand private
> key; a fresh-prestate-selected absolute content-addressed operational release
> root; an independently controlled non-stand secondary custody root; a fixed
> argv-only read-only stand-prestate collector; and an independently verified
> canonical allowed-signers artifact/hash/fingerprint binding. Authorize
> repository-local implementation, schema/fake/negative tests, sanitizers, and
> clean no-authority packaging of that collector plus preparation of exact
> Q15-R-P4-R and Q15-R-P4-K authorization records only. Keep all five literal
> values unresolved until their required owner choices and evidence exist. Do
> not access or modify the stand, create/import/generate/copy keys, select or
> create literal paths, transfer/install artifacts, execute the collector or
> access probes, issue/sign/execute Q15-R or Q15-W, use real PMU/MSR/affinity/
> NUMA operations, calibrate, pilot, measure, or perform confirmatory work.

Acceptance does not itself create an ADR or implementation in the current
working tree. After explicit acceptance, repository records must add one ADR
per decision and preserve this proposal unchanged.

## Verification command

```sh
cmake --build --preset dev-gcc --target q15-r-external-input-acquisition-check
```

The checker validates Draft 2020-12 structure, P3 lineage hashes, exact
one-to-one decision/input mapping, null values, separate unopened future gates,
and nine negative authority/default/drift mutations. It performs no network,
stand, key, or platform operation.
