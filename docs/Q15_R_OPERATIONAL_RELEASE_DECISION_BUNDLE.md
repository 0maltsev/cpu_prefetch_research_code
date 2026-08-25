# Q15-R-P3 operational-release decision/input bundle

Status: **`ACCEPTED_Q15_R_P3_NO_STAND_OR_EXECUTION_AUTHORITY`**

The clean no-authority Q15 qualification-tool v2 archive now contains the
accepted Q15-R trust-anchor adapter. The machine-readable
[`q15-r-operational-release-decision-input-v1.json`](../config/q15/q15-r-operational-release-decision-input-v1.json)
binds its complete release identity and preserves the proposed D-065 input.
Q15-R-P3 separately accepts that exact release identity without granting stand
or execution authority. The immutable decision-input record SHA-256 is
`c7f7401f99ac25f2e56ceac889a6e64174efa047d2e06f71e74c2065aa2faa58`.
The acceptance record SHA-256 is
`8b90ed2e6bf865b7df2b05aef7e18a8c7aeacac953b79baa7fb2ed7ea03dd167`.

## D-065 — no-authority operational-release identity

- **Classification:** Q15-R no-authority operational-release identity.
- **Options:** select the exact clean `c8b69ab` release; retain the ineligible
  adapter-free base release; build a different clean release; or stop.
- **Recommendation:** select only the exact release below as the software input
  to a later separately authorized stand-setup transaction.
- **Scientific effect:** none; no scientific schedule, run, outcome, estimator,
  or measurement is selected or accessed.
- **Compatibility effect:** every listed byte/hash/profile becomes immutable
  setup-input identity.
- **Owners:** repository, build, controller, security, and audit owners.
- **Deadline/gate:** before operational-release-root resolution, stand setup,
  and Q15-R issuance.
- **Supersession:** any byte, profile, authority, adapter/controller, build, or
  report change needs a new clean release and prospective approval.

## Exact release evidence

- Source commit:
  `c8b69abf0c6aec7b740efe78d998a93545302a94`.
- Archive:
  `cpu-prefetch-q15-qualification-tool-2.0.0-c8b69ab-clean-8d27197443f2.tar.gz`.
- Archive size: `4356358` bytes.
- Archive SHA-256:
  `8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01`.
- Sidecar SHA-256:
  `b251133526412f620ec3c5d9685b201a4b0280bb4fabc2382636c2c4b04343f1`.
- Source archive SHA-256:
  `8d27197443f2ed016e6ac7e3788a0660fadab84ffc78e31934f4092bbc143df7`.
- Manifest SHA-256:
  `e5636a34c5dc083cfa01daa00091ee0baafa840174dda6ac2bbd1903115b7ebf`.
- SBOM SHA-256:
  `77a4fd2f44fa4d6c8d214d4bfa5eb7231ed3a5597f83437b7fe84d9de42b65df`.
- Controller binary SHA-256:
  `9bdda2b7eab5b4c50f82fc478f6c936a7a2bafffd85b05c68262360f3b04650d`.
- Q15 tool binary SHA-256:
  `0b7afb5c0501c108c8ff17c3dbb319525d531b68e8a9b8d767f2ed0eab0a37d5`.
- Adapter-bearing library SHA-256:
  `c9eae879c66cda471b8bc2043bc6b61da21c64f008006ae969ab94faa44a27f0`.
- Probe/runtime/controller code-generation reports:
  `cb3368f851c5c5ac8e2c5ef5747ecf53f27e586b4b756798daa8386a1266f4aa`,
  `e3c09d4fcbb759b0008c728d563f984d38bdb93e269ac70f3ebd6a1d99ab7014`,
  and `7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca`.
- Clean extraction: `133` declared files and all five non-authorizing
  self-tests passed.
- Authority: `NONE`.

The predecessor setup preparation remains immutable at SHA-256
`a671fad5b45823a617140d9ee1f684235812daede0048fb67e1255ce74ecb057`.
It remains readable as the six-input pre-release state. The accepted versioned
successor
[`q15-r-stand-setup-authorization.preparation-v2.json`](../config/q15/q15-r-stand-setup-authorization.preparation-v2.json)
has SHA-256
`25ab86661f2a0ea1c92237aea06585e585bea9303f9309678e110978c7bd5338`.
It treats only the exact release-hash group as supplied while leaving these
five groups unresolved:

1. literal allowed-signers source;
2. literal operational-release root;
3. literal secondary-custody root;
4. fresh stand-prestate artifact ID and SHA-256; and
5. actual allowed-signers artifact ID, SHA-256, and Ed25519 fingerprint.

## Accepted statement

> Q15-R-P3 — accept D-065 and select clean commit
> c8b69abf0c6aec7b740efe78d998a93545302a94 with no-authority archive
> SHA-256 8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01
> as the exact Q15-R operational-release evidence input. Authorize
> repository-local creation and verification of a versioned successor
> stand-setup preparation that resolves only the clean-release evidence group
> and leaves all five external input groups unresolved. Do not access or modify
> the stand, create accounts or keys, transfer or install artifacts, execute
> access probes, issue/sign/execute Q15-R or Q15-W, use real PMU/MSR/affinity/
> NUMA operations, calibrate, pilot, measure, or perform confirmatory work.
> Stand setup and every later phase require separate explicit approval.

The statement was accepted as Q15-R-P3. It authorizes no commit, stand setup,
stand access, transfer, installation, access probe, or Q15 phase.

Repository-local checks:

```sh
cmake --build --preset dev-gcc --target q15-r-operational-release-decision-check
cmake --build --preset dev-gcc --target q15-r-p3-acceptance-check
cmake --build --preset dev-gcc --target q15-r-stand-setup-preparation-v2-check
python3 tools/check_q15_r_operational_release_decision.py \
  --archive-dir build/release-gcc/q15-qualification-tool-bundle \
  --extracted-root /path/to/clean/extraction
```
