# Q15 stand-qualification decision/input bundle

Status: **`D053_POINTER_SLICE_RELEASED_NO_AUTHORITY; NOT_AUTHORIZATION_READY; NO_STAND_AUTHORITY`**

Date prepared: 2026-08-24

Protocol: `2.0.0-pre.2`

Scope: exact stand qualification only. This document does not authorize stand
access, account or key changes, installation, dynamic collection, MSR access,
platform mutation, calibration, pilot work, measurement, or confirmation.

## Outcome

The clean measurement-release prerequisite is closed and hash-bound below.
Q15-S1 accepts D-051 and implements a separate fixed-scope qualification tool,
bundle profile, split authority schema, and blocked preparation records. Exact
ADR-0052 now freezes the exact probe/collector definitions. Q15-S2/ADR-0053
resolves and locally implements the pointer permutation, integrity, pure
classification, and counted traversal/codegen slice. Q15 authorization remains
blocked because clean tool-release/report hashes, the dynamic probe path,
seven collector executables, authority, command, numerical-limit, prestate, and
custody fields required by ADR-0045 and ADR-0049 through ADR-0052 do not exist.

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

### Before a qualification-tool release can be used dynamically

- clean source and release hashes for the locally implemented fixed-address
  family-06/model-55H, MSR-0x1A4, CPUs-0/1/26 adapter;
- exact dynamic implementation and generated-code/release evidence for the
  frozen regular-stream, pointer-dependent, and seven-collector contract;
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

The exact sealed measurement-candidate portion, D-052 contract, and D-053
local implementation decision are
approval-ready evidence. Q15-S1 is accepted and locally implemented, but Q15-R and Q15-W are not
approval-ready because their mandatory artifacts and values above are absent.
A generic reply such as `approve Q15`, prior SSH permission, root access, or
approval of this prepared document cannot authorize stand activity.

The exact next safe work is to implement and audit the remaining dynamic PMU
path and seven collectors, then produce a clean no-authority tool release and
supply the remaining Q15-R executable/command, role, limit, custody, and
validity values. Q15-R may only then be prepared for separate approval. Q15-W
can be prepared only after Q15-R evidence exists.
