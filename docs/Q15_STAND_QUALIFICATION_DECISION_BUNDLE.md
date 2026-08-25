# Q15 stand-qualification decision/input bundle

Status: **`Q15_R_V2_BASE_RELEASE_VERIFIED_NO_AUTHORITY; OPERATIONAL_PREREQUISITES_PROPOSED`**

Date prepared: 2026-08-24

Protocol: `2.0.0-pre.2`

Scope: exact stand qualification only. This document does not authorize stand
access, account or key changes, installation, dynamic collection, MSR access,
platform mutation, calibration, pilot work, measurement, or confirmation.

## Outcome

The clean measurement release, Q15-S3 qualification-component release, and
Q15-R-P1 controller-bearing v2 base release are closed and hash-bound. Q15-S1
through Q15-S3 implement the split
tool boundary, exact probe/collector contract, deterministic pointer slice,
same-buffer session, Linux acquisition seams, and seven collectors. The Q15-S3
archive SHA-256 is
`20acaded8002c130db725369c67013582dbcfccbd826a033a14658281387f848`.
Q15 authorization remains blocked. D-057 through D-060 are accepted and
locally implemented in the separate
[`Q15-R decision/input bundle`](Q15_R_DECISION_INPUT_BUNDLE.md). Clean commit
`a75bcdd0367d79f8ee0496c55edda74311c9ef7d` produced the v2 base archive
SHA-256 `48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035`,
but its CLI and manifest deliberately grant no authority. The operational
adapter, actual credentials/trust/custody, executable argv, validity/signature,
and fresh dynamic evidence do not exist.

An authorization document cannot be emitted with placeholders. The split
authority schema represents only `AUTHORIZED`; the separate preparation schema
represents only `BLOCKED_INPUTS_REQUIRED` with all authority flags false. The
unresolved values are machine-readable in `config/q15/` and remain blocked until
independently supplied and hashed.

## Exact sealed release binding

| Field | Exact value | State |
|---|---|---|
| Source revision | `693f00b3878ed027dc09aea7916f149874fb12a1` | `VERIFIED_CLEAN` |
| Bundle profile | `STAGE17-PILOT-CANDIDATE-BUNDLE-v1` | `VERIFIED` |
| Archive | `cpu-prefetch-pilot-candidate-2.0.0-693f00b-clean-7af3ae772dcb.tar.gz` | `SEALED_NO_AUTHORITY` |
| Archive bytes | `4641184` | `VERIFIED` |
| Archive SHA-256 | `f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1` | `VERIFIED` |
| Source archive SHA-256 | `7af3ae772dcb10120479764bbd4d794724e9a8e154c23c293923d6e8d74f3791` | `VERIFIED_CLEAN` |
| Bundle manifest SHA-256 | `b5919e4a24973550101b4a9795892e0a7f16cf7c60729ad7f69cd26ae9a282aa` | `VERIFIED` |
| SBOM SHA-256 | `e4e82b2e48a6d08426a22d110dfb23ed9bb68c47e5af2869012d6fe6a864f1e5` | `VERIFIED` |
| Build metadata SHA-256 | `a4f1dbffa8f01532719d85c81da29f69be4474bda76f13e52972847721df5bb3` | `VERIFIED` |
| Protocol import manifest SHA-256 | `e06ac6bdc4f4d6b47a6f3c0d548f2b3b0f1088684a77cae08cbf7167800a1d76` | `VERIFIED` |
| Repository license | `NO-LICENSE-GRANT` | `BOUND` |

The clean extraction verifier passed all 94 internal files. The smoke and
preflight self-tests passed as unprivileged UID/GID `1000/1000`. Release GCC
tests passed 216/216. The candidate manifest records
`dynamic_qualification_authorized=false`, `pilot_authorized=false`,
`confirmatory_authorized=false`, and
`measurement_execution_command_present=false`.

### Exact release artifacts

| Artifact | SHA-256 |
|---|---|
| `release/bin/cpu_prefetch_runner` | `8bf2577750872a7595e62797e6ef278607f3bd5308820e2c21cc957ff192c2c7` |
| `release/bin/cpu_prefetch_qualification` | `59243dd5d033c6557446a2dbf9e79e9b62f0df63e43e5b1afc8bc9b01126288c` |
| `release/bin/cpu_prefetch_preflight` | `662484a215ba330330c34d52dcf97c9b9d98daf6192bae09f0e5b11b6118f6f0` |
| `release/bin/cpu_prefetch_smoke` | `1433c2b503db4007174b459a0da2f91ca01c05b724eeca04de5440b509844f43` |
| Runner admission v3 schema | `0284f9bfedb806545fd12a178d65c7bbc9bd3c7e46b967b4aa7d9c5534fad8a7` |
| Stage 17 authorization v2 schema | `e63eb5c21683b1762975ca17e3fd7c6eb85bcdf22e7bd68c93b47f0a265b2884` |
| Hardware-prefetch qualification schema | `97d2234428fd706f3b99a2a4c5ee326118aaed13608a6c0016f592ea450c825b` |
| Combined runner codegen report | `2396a5f134bb16393a91c79ba1d3368b5214a43fac3c55498f473974a921157a` |
| Relax codegen report | `863f04eb1cfcaf0859bb3af0fd7edb037e9b75c15fdc5f12dbe958163fe3592a` |
| Queue codegen report | `ffaa7511909c65ac6acc71cba7d188ac450bc3e3a873c9c834c0a77a1e838496` |
| Workload codegen report | `4caaafd7af71c77ec63ac7db4e7f184fd276f37ee5853f81538ae6712147df2e` |
| Timing codegen report | `46dac5416f78e31293c33610d0ffe9c5151084206078a0606d4e366991b3ece0` |
| Storage codegen report | `d0de2951b58a18f49435f5f56a0a5e40748d1950ad97c42246ac04c5fcbbe40c` |

The fixed identities are runner profile
`STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3`, CPU-pair selection
`XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1`, relax mapping
`X86-PAUSE-ONE-PER-RELAX-SITE-v1`, software-prefetch mapping
`X86-64-PREFETCHW-PREFETCHT0-v1`, and hardware-prefetch mapping
`INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1`.

### Clean Q15-R-P1 v2 base release

| Field | Exact value | State |
|---|---|---|
| Source revision | `a75bcdd0367d79f8ee0496c55edda74311c9ef7d` | `VERIFIED_CLEAN` |
| Bundle profile | `Q15-QUALIFICATION-TOOL-BUNDLE-v2` | `VERIFIED_NO_AUTHORITY` |
| Archive | `cpu-prefetch-q15-qualification-tool-2.0.0-a75bcdd-clean-b4438745f3ca.tar.gz` | `SEALED_NO_AUTHORITY` |
| Archive bytes | `4247166` | `VERIFIED` |
| Archive SHA-256 | `48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035` | `VERIFIED` |
| Sidecar SHA-256 | `9c7dee2e07c49e51af8b3e922e8295ecce959dfe53deed4d3604e59722655505` | `VERIFIED` |
| Source archive SHA-256 | `b4438745f3ca5a461a456ea7200970b41893572869866bf40a5d58da4c18d2c7` | `VERIFIED_CLEAN` |
| Manifest SHA-256 | `90f01cd1be57d844f532d0b9f5612179aa9436a44ba353e3aeda724d10704030` | `VERIFIED` |
| SBOM SHA-256 | `c1b915f082ce3b6a1c916c7bef1d17e008d0dede623ec8aa927dbe868dd3f537` | `VERIFIED` |
| Controller SHA-256 | `36607f03669d194b22d37bc6652e92fe8486ab0ef4964ef5217ad73d18d15cf1` | `NO_AUTHORITY_CLI` |
| Q15 tool SHA-256 | `ba93d6384eb536654ccdfa94dc4b52c0cfde9408b9d79ef902ea6e3749548d15` | `NO_AUTHORITY_CLI` |

All 118 internal inventory entries and five non-authorizing self-tests pass.
The adapter is now implemented only in the later dirty repository state; it is
not in this archive. This archive is not an execution release, and possession
grants no authority.

## D-051 accepted decision: split qualification authority and tool boundary

Classification: security/platform engineering decision; no scientific
semantic change.

Options considered:

1. Authorize one root session with prestate values filled after commands run.
2. Treat read-only inventory as the MSR prestate and authorize writes.
3. Add mutating controls to the sealed measurement candidate and reseal it.
4. Preserve the sealed candidate; create a separate hash-bound,
   no-measurement qualification-tool bundle; authorize exact read-only
   acquisition as `Q15-R`, then prepare a separate `Q15-W` apply/probe/restore
   authorization that binds the immutable Q15-R prestates.
5. Declare the candidate ineligible.

Accepted option: **4** under Q15-S1/ADR-0051. Options 1 and 2 violate exact-
prestate and independent-verification requirements. Option 3 unnecessarily couples
privileged control code to the measurement release and invalidates its current
hashes. Option 5 remains the fail-closed fallback if the tool, authority, or
restoration evidence cannot be established.

Scientific effect: none; both records are qualification-only and cannot use a
scientific schedule, queue outcome, calibration namespace, or treatment
comparison. Compatibility effect: both authorization documents, the separate
tool source/binary hashes, stand identity, command vectors, prestate artifacts,
and release hashes become qualification identity. Owners: platform, security,
controller, protocol, custody, and audit. Gate: before any dynamic stand
qualification. Supersession: new immutable Q15-R/Q15-W records and full
requalification after any bound artifact changes.

## Q15-S1 local implementation

The repository now provides `Q15-FIXED-QUALIFICATION-TOOL-v1`, fixed to CPUID
family 06/model 55H, MSR 0x1A4, and CPUs 0/1/26. Its reader and one-control
apply/restore operations accept no arbitrary path, address, mask, or CPU list.
Every transition checks the authorization-bound complete current value before
one complete-value write and requires a separate auditor readback. Tests use an
in-memory file-operation boundary and never open an MSR device.

`cpu-prefetch-q15-qualification-authorization/1` admits only separate
`Q15_R_READ_ONLY` and `Q15_W_APPLY_PROBE_RESTORE` records. New omnibus v2 Q15
documents are rejected. `config/q15/q15-r.preparation.json` and
`config/q15/q15-w.preparation.json` bind the known measurement candidate and
enumerate missing inputs, but cannot validate as authority. See
[`Q15_QUALIFICATION_TOOL.md`](Q15_QUALIFICATION_TOOL.md).

## Mandatory inputs still unresolved

### Before a controller-bearing qualification-tool release can be used dynamically

- a new clean no-authority release binding that controller, the existing
  components, all generated-code reports, and exact source/binary hashes;
- exact independent readback executable/identity, not merely a second call
  through the writer identity;
- negative tests proving no measurement, calibration, pilot, wildcard target,
  unlisted privilege, or silent fallback; and
- clean source, binaries, SBOM/license inventory, manifests, internal/outer
  hashes, sanitizer/static tests, and nonprivileged self-tests for that tool
  bundle.

### Before Q15-R read-only acquisition can be authorized

- exact stand ID and current inventory/topology artifact IDs and hashes;
- four distinct operator, controller, custodian, and auditor identities plus
  their account/key/group/capability mapping;
- negative OS access evidence for every forbidden role/action pair;
- exact executable hashes and complete argv arrays for each read/collector
  command, with exact targets and output artifact IDs;
- exact primary and secondary custody-domain IDs, output root, append-only,
  transfer, partial-artifact, recovery, quota, and receipt policies;
- exact issue/expiry times, detached-signature scheme/signer/artifact/hash;
- exact maximum wall seconds, CPU seconds, output bytes, and artifact count;
- exact stop conditions; and
- the two start-barrier limits and external process-watchdog bound required by
  ADR-0048, with prospective rationale independent of outcomes.

### Before Q15-W mutation can be authorized

- a passed, sealed, transferred, independently verified Q15-R evidence set;
- exact complete 64-bit prestates for CPUs `0`, `1`, and `26`;
- exact H0 no-write and H1 `prestate|0x0f` values preserving bits 63:4;
- exact writer argv, inverse argv, independent complete-value readback argv,
  both probe argv arrays, and output artifact IDs for every permitted command;
- one-control-at-a-time order, reverse restoration order, independent restore
  readback, and quarantine behavior;
- explicit byte/CPU/wall/artifact limits and UTC validity; and
- detached approval/signature over the canonical authorization bytes.

No requested hardware value may be copied into the verified-state field. A
successful command exit status is not verification.

## Mandatory Q15-R/Q15-W prohibitions

Both records must explicitly prohibit calibration, pilot and confirmatory
execution; scientific schedules and namespaces; measurement-run admission;
outcome-driven tuning; top-up; cell repair; hidden retry; later-phase
execution; wildcard or `latest` references; unlisted targets or privilege;
service/boot changes not named in the record; and use after expiry,
supersession, mismatch, partial application, custody failure, or uncertain
restoration.

Q15-W must stop after the first mismatch, preserve all actual partial evidence,
restore successfully applied controls in reverse order, independently verify
restoration, and quarantine the stand if restoration is uncertain.

## Approval readiness

The exact sealed measurement candidate, clean Q15-S3 component release, and
clean no-authority Q15-R-P1 v2 base release are verified evidence. The Q15-R-P2
adapter seam is locally implemented and clean commit `c8b69ab` produced a
verified adapter-bearing release candidate with authority `NONE`. D-065
is accepted by Q15-R-P3 as evidence only. Q15-R and Q15-W themselves are not
approval-ready because actual trust anchor, role/custody/signature artifacts,
and values above are absent.
A generic reply such as `approve Q15`, prior SSH permission, root access, or
approval of this prepared document cannot authorize stand activity.

Q15-R-P2 accepted D-061 through D-064 in the
[`operational-prerequisite bundle`](Q15_R_OPERATIONAL_PREREQUISITE_DECISION_BUNDLE.md).
The exact next safe work is to supply and review every missing setup input and
then request a separate literal stand-setup authorization. Q15-R may be
prepared for signed approval only after that setup and release pass. Q15-W can
be prepared only after sealed Q15-R evidence exists.
