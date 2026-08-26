# Decisions Required

Protocol version: **`2.0.0-pre.2`**; predecessor `2.0.0-pre.1` retained

Stage 2/16 disposition: **`D094_BOOTSTRAP_ROOT_ACTIVE_NO_SIGNING_AUTHORITY; P4_K_A_SIX_INPUTS_AND_AUTHORITY_REQUIRED`**

Stage 15 disposition: **`COMPLETE_LOCAL_SYNTHETIC; EXTERNAL_INPUTS_OPEN`**

The repository still contains no authorized production benchmark execution.
Q13 adds a fail-closed runner admission/static-dispatch core whose CLI cannot
start measurement. Stages 11 and 12 contain the accepted physical observation
boundary and synthetic post-run reconciliation, not an authorized scientific run path.
Stage 16 now also retains a verified nonprivileged candidate-stand snapshot
with two packages and two NUMA nodes. Q13 selects explicit static worker pairs
from later hashed topology evidence but supplies no dynamic qualification.
ADR-0047 now fixes the physical software-prefetch mapping and its strict
dual-compiler/disassembler software gate. Stage 5 contains queue
correctness-only production cores, Stage 6 contains
deterministic workload-construction components, and Stage 7 contains offline
schedule generation/validation. Q1 through Q6 were accepted by the repository
owner on 2026-08-17; Q7 was accepted on 2026-08-20; Q8 through Q12 were
accepted on 2026-08-21; Q13 and Q14 were accepted for implementation/policy
only on 2026-08-22. Q15-P0 and Q15-S1 through Q15-S3 were accepted on
2026-08-24 and are recorded through ADR-0056. Earlier decisions are recorded
through ADR-0046, with ADR-0039
closing the delegated Stage 13 profile, ADR-0040 closing the Stage 14
implementation-owned planning/access profile, and ADR-0041 closing the
synthetic-only Stage 15 analysis profile. Exact scientific,
platform, and pilot facts remain open until their listed phases; they were not
replaced by engineering defaults.

Q15-R-P4-F was accepted on 2026-08-25 and is recorded in ADR-0072 through
ADR-0075. It freezes repository-local literals and still-unissued templates
only; it supplies no operational evidence or execution authority.

## Accepted Q15-P0 prerequisite closure; exact Q15 inputs still required

Q15-P0 accepts D-048 through D-050 for repository-local implementation only.
ADR-0048 removes in-measurement poll-count expiry and introduces admission/
runner v3. ADR-0049 fixes the narrow Intel 06_55H MSR-0x1A4 H0/H1 mapping and
fake-tested transaction/evidence contracts. ADR-0050 fixes four distinct roles
and candidate-to-development two-domain custody policy. See
[`Q15_PREREQUISITE_CLOSURE.md`](Q15_PREREQUISITE_CLOSURE.md).

Clean revision `693f00b3878ed027dc09aea7916f149874fb12a1` and the sealed
no-authority archive SHA-256
`f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1`
close the release prerequisite. Still unresolved before exact Q15 approval:
two start-barrier values and an external process-watchdog bound;
actual accounts/person/key/capability mappings plus negative OS tests; exact
command argv/hashes/limits/paths/signature; fresh complete MSR prestate and
dynamic H0/H1 readback/probes/restoration; pair clock, atomics/layout,
actual-CPU/migration, residency, storage/custody, and recovery evidence. Q15-P0
does not authorize stand access or any dynamic/privileged action.

D-052/ADR-0052 now freezes `Q15-PROBE-COLLECTOR-CONTRACT-v1`: exact raw PMU
programming, regular and pointer-dependent traversals/classification, and seven
collector acceptance boundaries. Q15-S2/ADR-0053 resolves the frozen seed as
the ADR-0025 master seed and locally implements the exact pointer cycle,
complete-buffer integrity, pure classification, and counted traversal bodies.
Q15-S3/ADR-0054 through ADR-0056 implement and cleanly release the same-buffer
session, fixed fakeable Linux acquisition mechanisms, and seven distinct
collectors. Commit `7a92629` and archive SHA-256
`20acaded8002c130db725369c67013582dbcfccbd826a033a14658281387f848`
bind those components and code-generation reports. The release intentionally
lacks a production controller.

Q15-R-P1 accepted D-057 through D-060 in the
[`Q15-R controller-closure decision/input bundle`](Q15_R_DECISION_INPUT_BUNDLE.md).
The repository-local fixed controller, authorization-v2/profile validators,
fake tests, generated-code audit, and unapplied role/custody plan now pass.
Clean commit `a75bcdd0367d79f8ee0496c55edda74311c9ef7d` and v2 archive
SHA-256 `48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035`
close the no-authority base-release gate. This closes neither the operational
adapter, stand setup, nor execution gates.
Stand access, account/key changes, Q15-R issuance/execution, Q15-W, dynamic
qualification, calibration, pilot, measurement, and confirmation remain
prohibited.

Q15-R-P2 accepted D-061 through D-064 in the
[`Q15-R operational-prerequisite decision bundle`](Q15_R_OPERATIONAL_PREREQUISITE_DECISION_BUNDLE.md)
and ADR-0061 through ADR-0064. The fixed inherited-descriptor adapter is
implemented and fake-tested locally; the v2 base release remains prerequisite
authority `NONE`. The synchronized role/custody and Q15-R/Q15-W preparation
records bind the acceptance and adapter identities without inventing any stand
fact. The exact command graph is preserved in the
[`blocked stand-setup authorization preparation`](Q15_R_STAND_SETUP_AUTHORIZATION_BUNDLE.md).

Q15-R-P3 accepts D-065/ADR-0065 and creates versioned successor preparation
v2. Only the clean-release evidence group is resolved. The predecessor remains
byte-preserved; all five external setup groups and every authority field remain
unresolved or false.

The [Q15-R-P4 external-input acquisition bundle](Q15_R_EXTERNAL_INPUT_ACQUISITION_DECISION_BUNDLE.md)
records the accepted D-066 through D-070 acquisition methods: an offline signer boundary, a
fresh-prestate-selected content-addressed operational root, an independently
controlled non-stand custody root, a fixed read-only prestate collector, and a
canonical independently verified allowed-signers binding. ADR-0066 through
ADR-0070 record the decisions. They fill no literal value and grant
repository-local collector implementation only.

Clean commit `c8b69abf0c6aec7b740efe78d998a93545302a94` produced and
verified an adapter-bearing no-authority release with archive SHA-256
`8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01`.
D-065 is [accepted by Q15-R-P3](Q15_R_OPERATIONAL_RELEASE_DECISION_BUNDLE.md)
as the exact future setup release input. The predecessor six-input preparation
remains immutable; versioned successor v2 resolves only release evidence and
retains five external groups: literal allowed-signers source, operational
release root, secondary custody root, fresh stand prestate, and the actual
allowed-signers artifact/hash/fingerprint. Named authority, UTC validity,
evidence IDs/hashes, signature, and independent review also remain mandatory
for the later exact authorization. A generic approval, SSH
permission, or root access cannot substitute; setup would still not authorize
Q15-R.

The fixed collector and validator are implemented with fake evidence. Clean
commit `34da95d002e912069c959bfef8e88a23b4880cea` produced the verified
collector-bearing v3 archive SHA-256
`f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`
with authority `NONE`. Q15-R-P4-E accepts the
[D-071 collector-release decision](Q15_R_P4_R_COLLECTOR_RELEASE_DECISION_BUNDLE.md)
and hash-binds that release. Versioned successor P4-R preparation v2 resolves
only the clean collector-release evidence group and retains seven null external
inputs. The original P4-R preparation remains immutable with eight null inputs;
P4-K remains unissued and retains all eight null inputs. The smallest next
gates require owner/platform evidence for those external values and separate
exact authorization; no value may be inferred. Separate
future Q15-R-P4-R, Q15-R-P4-K, Q15-R-P5, Q15-R, and Q15-W gates remain
mandatory and unopened.

The [exact Q15-R-P4-R staging/authorization bundle](Q15_R_P4_R_STAGING_AUTHORIZATION_DECISION_BUNDLE.md)
records the immutable D-072 through D-075 proposal at machine-record SHA-256
`18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604`.
Q15-R-P4-F accepts one create-exclusive staging tree, fixed capture and
development-custody paths, named operator/auditor/custodian roles, a
nonrenewable 1,800-second UTC policy, the accepted SSHSIG profile, and a split
read-only identity then one-shot collection graph. Acceptance SHA-256 is
`ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`;
ADR-0072 through ADR-0075 record the choices. The P4-R-I and P4-R-C successor
templates remain unissued with six null external-input groups each. The
smallest next gates are exact P4-K-A ceremony/custody/bootstrap-signing inputs
or a later exact signed P4-R-I authorization; P4-R-C may be prepared for
issuance only after accepted fresh identity and review hashes exist. No gate
auto-continues.

The repository-local
[`Q15-R-P4-K decision/input bundle`](Q15_R_P4_K_DECISION_INPUT_BUNDLE.md)
is accepted by Q15-R-P4-K-D/ADR-0076 through ADR-0079. Acceptance SHA-256 is
`11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`.
It selects the new-offline-ceremony source mode, logical custody domain
`OWNER-OFFLINE-Q15-KEY-CUSTODY`, custodian
`cpu-prefetch-q15-custodian`, split one-shot P4-K-A then independent P4-K-R,
and the accepted operator/1,800-second/JCS-I64/SSHSIG/distinct-auditor profile.

The logical identifiers are not operational evidence. The immutable original
P4-K preparation retains all eight null external inputs. The separate P4-K-A
and P4-K-R templates remain unissued with 13 and 9 null input/output fields.
Before P4-K-A can be prepared for exact issuance, the owners must supply:

1. exact offline ceremony/public-extraction tools, versions, SHA-256 values,
   and fixed argv;
2. create-exclusive public artifact IDs and absolute public source paths;
3. operational offline custody-control and ceremony-environment evidence ID
   and SHA-256, without private-key paths or bytes;
4. bootstrap authorization signer fingerprint and trust-evidence SHA-256—the
   nonexistent target key cannot authorize its own creation;
5. literal issue/expiry UTC instants and canonical authorization/signature
   hashes; and
6. distinct auditor pre-execution review evidence.

P4-K-R remains blocked until a complete accepted P4-K-A action receipt and all
exact public/custody evidence exist. Private key bytes, passphrases, seeds, or
secret paths must never be submitted. P4-K-A, P4-K-R, P5, P4-R-I/P4-R-C, and
every Q15 or experiment phase still require separate exact approval.

The repository-local
[`Q15-R-P4-K-A operational-input decision bundle`](Q15_R_P4_K_A_OPERATIONAL_INPUT_DECISION_BUNDLE.md),
machine-record SHA-256
`8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`,
is accepted as policy by Q15-R-P4-K-A-D/ADR-0080 through ADR-0085. Acceptance
SHA-256 is
`c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
It originally mapped seven null P4-K-A inputs to exact environment/toolchain,
encrypted-key custody, public export, bootstrap-root, fixed-controller, and
issuance/review contracts. D-094 resolves only bootstrap trust in a versioned
successor; the immutable predecessor remains unchanged.

The owner originally selected
`P4KA-Q4=NO_QUALIFYING_BOOTSTRAP_SIGNER_REMAIN_BLOCKED`. D-093 subsequently
superseded the unaccepted D-087 through D-092 bootstrap-genesis recommendations
and explicitly accepted one-owner role collapse, development-host creation, an
unencrypted Ed25519 private key, no independent recovery, and the resulting
critical impersonation and key-loss risks. The single authorized create-
exclusive action completed. Its public evidence verifies. D-094 subsequently
activated that fingerprint. D-095 later superseded the target-action security
controls for one exact development-host unencrypted single-owner transaction.
It created and independently verified one bootstrap signature, then stopped
terminally before target-key generation because the wrapper passed both
`stdin` and `input` to `subprocess.run`. Four public partial artifacts are
retained, the target private path is absent, and D-095 permits no retry,
repair, overwrite, cleanup, deletion, or continuation.

D-096/ADR-0096 was accepted and superseded only the terminal D-095 action. Its
new create-exclusive `p4-k-v2` transaction completed with authorization
SHA-256 `8feb2ccf...`, independently verified bootstrap signature SHA-256
`2514a671...`, target fingerprint
`SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM`, and complete-evidence
SHA-256 `8c30c1fb...`. The failed `p4-k-v1` tree remains preserved and was not
retried or repaired. Private key contents remain outside the repository and
were not read or hashed.

D-097/ADR-0097 was accepted and completed exactly once. Authorization SHA-256
`a34a2441...`, bootstrap signature `ab874dcc...`, review receipt `5a3233fb...`,
and complete-evidence SHA-256 `b7c6125d...` verify. The public-only review
verified all D-096 public hashes, target fingerprint, principal, and public-key
byte equality. It performed no private-key access or presence probe, no
installation/activation, and no retry; it stopped before P5.

The next decision path is documented in the
[`D-098 P5 bundle`](Q15_R_P5_D098_DECISION_BUNDLE.md). Preparation v3 resolves
only the two reviewed public-trust groups. Three inputs remain null and block
P5: the literal operational release root, independent secondary custody root,
and fresh current stand-prestate artifact ID/SHA-256.

D-099/ADR-0099 completed P4-R-I exactly once. Its canonical authorization,
target-key SSHSIG, four pinned-host read-only observations, create-exclusive
identity capture, and single-owner public review verify. Complete-evidence
SHA-256 is `afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241`.
It made no stand filesystem mutation and stopped before P4-R-C.

The next unresolved gate is a new exact P4-R-C preparation, signature, and
explicit execution approval bound to the accepted D-099 identity/review.
P4-R-C may then stage and run the fixed prestate collector only within its own
authority. P5, stand setup, Q15, calibration, pilot, measurement, and
confirmation remain unauthorized.

The exact
[`D-100 through D-103 P4-R-C bundle`](Q15_R_P4_R_C_D100_DECISION_BUNDLE.md)
has machine-record SHA-256 `faa4c377...`; the directly responsive bounded owner
acceptance has SHA-256 `bdfe690a...`. ADR-0100 through ADR-0103 now select the
single-owner P4-R-C review downgrade, compatibility with only the exact
pre-existing D-099 custody root, the fixed OpenSSH login-shell boundary, and
the create-exclusive namespace-parent rule. The repository-local executor,
schemas, fake failures, and still-unissued preparation are implemented.

The next unresolved compatibility input is narrower: D-099 did not capture the
stand's absolute `/usr/bin/python3`, `/usr/bin/dd`, or Python tar-runtime
identity used by the fixed executor. D-102 says tool bytes are compatibility
identity, so the executor's runtime-acceptance constant remains null and its
action path fails closed. Prepare and separately authorize a read-only runtime
identity acquisition or explicitly accept exact runtime compatibility risk,
then freeze a clean successor before any D-104 signature or stand mutation.
P4-R-C action, key use, P5, Q15, calibration, pilot, measurement, and
confirmation remain unauthorized.

ADR-0086 now implements the generic repository-local controller, admission
schema, fake tests, and profile under the later owner delegation. It has no OS
backend and cannot mint a ticket while bootstrap, environment, toolchain,
custody, path, issuance, and review evidence are absent.

The preserved predecessor is the
[`Q15-R bootstrap governance-root decision/input bundle`](Q15_R_BOOTSTRAP_GOVERNANCE_ROOT_DECISION_BUNDLE.md),
SHA-256
`065d8a6d5f882bff84ee9bdbe27eb0e0c9e2bfea56c58cbe2b9bfc61cab3a4b7`.
D-087 through D-092 remain byte-preserved but are superseded by D-093 rather
than accepted. The D-093 authorization, public evidence, and lifecycle policy
are machine checked. The private key remains outside the repository; repository
tools record only its exact authorized path and metadata, never its contents or
content hash. D-094 made the root eligible for separately authorized signing
and produced an unissued P4-K-A successor. D-095 consumed its exact one-
signature authority and failed terminally before producing a target key. D-096
used a new authorization, signature, transaction, and path and completed the
target-key action. Active trust, the D-095/D-096 signatures, and the target key
did not themselves grant P4-K-R. D-097 separately completed the public review,
but its receipt and reviewed target identity are not P5 or downstream authority.

The prepared
[`Q15 stand-qualification decision/input bundle`](Q15_STAND_QUALIFICATION_DECISION_BUNDLE.md)
records D-051 as accepted by Q15-S1/ADR-0051. The fixed adapter, separate tool
and bundle profile, split authority schema, and blocked preparation records are
implemented locally. The clean no-authority bundle build is separately
completed for the v2 base and adapter-bearing candidate releases, but no Q15
authorization may be emitted while the role, command, custody, trust,
signature, and predecessor fields are missing.

## Accepted Q14 governance and D-047 mapping; next qualification inputs required

The
[`pre-Stage-17 blocker-closure and pilot-authorization decision bundle`](STAGE17_PILOT_AUTHORIZATION_DECISION_BUNDLE.md)
is accepted as Q14/ADR-0044 through ADR-0046. The permitted repository-local
runner, qualification-record, authorization-schema, combined-audit, and
candidate-builder work is implemented.

Q14 and D-047 do **not** authorize SSH/stand access, dynamic qualification,
privilege, calibration, pilot, or confirmatory execution. The exact release now
exists, but Q15 and Q16a through Q16d remain blocked because their authority,
commands, limits, predecessor artifacts, plans, namespaces, seeds, budgets,
storage domains, and required hashes do not yet exist.

D-047/ADR-0047 selects `X86-64-PREFETCHW-PREFETCHT0-v1`: producer ring sites
use `PREFETCHW`, consumer ring and linked-successor sites use `PREFETCHT0`, and
each owner must pass the PRFCHW capability gate before first touch. GCC and
Clang pass the strict dual-disassembler ten-operation audit and four negative
mutants. The clean exact no-authority candidate is sealed and verified, but
Q15 still requires every exact command, limit, authority, control, storage,
and custody input listed in the accepted bundle. A generic Stage 17 approval
remains invalid.

## Accepted Stage 13 bundle

[`STAGE13_CALIBRATION_DECISION_BUNDLE.md`](STAGE13_CALIBRATION_DECISION_BUNDLE.md)
contains four accepted decisions:

| Approval | Accepted decisions | What acceptance authorizes | What remains blocked |
|---|---|---|---|
| Q12 | D-035 nonparametric service-rate lower limit; D-036 run-cluster matrix zero-loss method/threshold/global ladder; D-037 ring-distance tail calibration; D-038 records/arithmetic/invalidation | Stage 13 typed plans, calculators, validators, fake modes, and synthetic verification only | Every stand run; exact durations/counts/sample minima; capacities/seeds; `mu_ref`; `d2`; final `Rtotal`/schedules/exposure; authority/budget; pilot/confirmation |

The owners answered `Q12 - accept the bundle` on 2026-08-21. ADR-0035 through
ADR-0038 now freeze these methods prospectively. Any requested change requires
a superseding ADR and complete requalification/recalibration as applicable;
calibration or confirmatory outcomes may not select the replacement.

## Resolved Stage 2 question

### Q4 — Repository source-license posture

The repository owner selected **no license**. ADR-0021 records no license grant, no `LICENSE` file, and no repository-authored SPDX license claim. Third-party dependency licenses remain separate provenance records.

**Gate result:** resolved before Stage 3 source was created. Use, copying, modification, and distribution remain unauthorized unless a later owner-approved ADR grants a license.

## Accepted Stage 2 bundles

| Bundle | Accepted decisions | ADRs | Later evidence that remains validly open |
|---|---|---|---|
| Q1 software foundation | C++20; Linux x86-64; GCC 16.x/libstdc++ primary; Clang 22.x/libc++ secondary; CMake/Ninja offline builds; GoogleTest/RapidCheck/CTest/custom stress; no generic scientific-loop framework | ADR-0007 through ADR-0011 | Stage 3 baseline/probes are D-029; exact measured-release lock remains pre-pilot |
| Q2 queue/process/atomic/integrity/correctness | One unprivileged process and two workers; non-dispatch binding; independent queues with no FastFlow source use; C++ atomic envelope; OpenSSL SHA/HMAC and `JCS-I64-v1`; generated-code and sanitizer policy | ADR-0012 through ADR-0017 | Exact atomic representation/proof Phase 5; exact consumer mixer Phase 6 |
| Q3 platform/custody boundary | External authorized control; replaceable Linux request/readback/probe/rollback interface; separate platform and validation principals with technical sealing | ADR-0018 through ADR-0020 | Exact stand/operator/API/register facts Phase 9; custody principals/enforcement by Phase 16/final confirmation |
| Q4 repository license | No repository license grant; no `LICENSE` file or repository SPDX claim | ADR-0021 | Any later license grant needs owner/legal/compatibility review |
| Q5 deterministic workload bundle | Independent Philox4x32-10/HMAC-SHA-256 stream suite; unbiased Fisher-Yates; separated purpose domains; fixed consumer mixer and canonical content/order/delta inputs; explicit record/package representations | ADR-0025 through ADR-0028 | Concrete seeds, platform facts/capacities, page-frame qualification, retaining prefetch instructions, and calibrated per-context `d2` |
| Q6 deterministic schedule bundle | Offline Python Decimal80 exponential transform; exact midpoint Philox mapping; picosecond cumulative-floor absolute deadlines; fail-closed overflow; versioned artifact/decoded/envelope identities | ADR-0029 | Stage 7 implementation evidence passes; concrete seed, namespace, rate, origin, and horizon values remain later lifecycle inputs |
| Q7 Stage 8 clock bundle | vDSO `CLOCK_MONOTONIC_RAW`; exact nanosecond-to-picosecond conversion; compiler-only read boundaries; bracketed publication/observation; no correction; explicit qualification limits | ADR-0030 | Stage 8 software/generated-code pass; dynamic traced-vDSO/full-count evidence and an explicit eligible worker pair remain required |
| Q9 Stage 11 storage bundle | Exact fixed u64le literal-run-ID rows; JCS envelope; no compression; one temporary and two verified durable copies in explicit distinct domains | ADR-0032/0033 | Stage 11 software passes; concrete run-plan capacity, worker-page residency, real domains/custody, and operational recovery remain Phase 16 evidence |
| Q10/Q11 D-031 and Stage 12 | Exhaustive ordered blocker set; non-priority `BLOCKED_MULTIPLE`; immutable pre.2 import; exact run-level reconciliation/status implementation | ADR-0034 | Stage 12 software passes; Stage 14 still supplies authoritative block completeness and access chronology |
| Q12 Stage 13 calibration methods | Nonparametric 95/95 service-rate lower limit; run-cluster Hoeffding matrix feasibility and global ladder; run-tail ring distance; versioned records/arithmetic/invalidation | ADR-0035 through ADR-0039 | Synthetic software/profile tests pass; every exact stand/duration/count/seed/capacity/authority/budget and final exposure remains externally gated |
| Stage 14 engineering closure | Exact typed product proof, explicit-key deterministic ordering, fixed precision registries, access chronology/segregation, and full-block replacement enforcement | ADR-0040 | Concrete precision counts, namespace/seed catalogs, platform/build, authorities/custody, replacement budget, and final block records remain externally gated |
| Stage 15 engineering closure | Exact inverse-ECDF estimands; complete-block Philox bootstrap; separate 7/20 max-T families; 270/540/54 H3 ordering; strict artifact/access/replacement admission; byte-stable synthetic reports | ADR-0041 | Production artifact adapter, exact release, concrete precision/count/seed/block/access/stand/storage/custody evidence, and every empirical output remain externally gated |

## Stage 3 through Stage 8 engineering baselines

ADR-0022 accepts the constrained compiler/build/test/dependency/CI baseline and
records it as D-029. ADR-0023 accepts the dependency-free typed-model and
record-local validation implementation as D-030. Neither approves a scientific
algorithm, a target stand, or an experiment. Coverage remains unselected because
it is not required to start Stage 5; adding a coverage gate requires a later
engineering decision.

ADR-0024 accepts the exact independent queue representation, memory-order,
layout-input, claim, and refinement boundary as D-032. Development-host
unit/property/stress and sanitizer evidence passes. GNU Binutils 2.46 and LLVM
22.1.6 generated-code checks, mutants, and human review pass, so Phase 5 is
complete. Eligible-stand runtime layout/lock-free qualification remains later
platform evidence rather than a Phase 6 blocker.

Q5 and ADR-0025 through ADR-0028 accept D-011 through D-013 and D-033. Stage 6
implements their deterministic primitives, immutable event arena, linked-node
order, exact footprint arithmetic, five statically bound package mechanisms,
no-allocation prepared path, integrity grammars, and generated-code checks.
No development fixture is a qualified stand value or scientific outcome.

## Accepted Q6 — Stage 7 deterministic schedule suite

State: **`ACCEPTED`**.

The repository owner answered `Q6 - accept the bundle` on 2026-08-17.
[`docs/STAGE7_DECISION_BUNDLE.md`](STAGE7_DECISION_BUNDLE.md) and
[ADR-0029](decisions/0029-stage7-schedule-generation-suite.md) therefore select the
offline suite `POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS-v1`:
midpoint mapping of one Philox draw per candidate, a fixed Python 3.14
80-digit decimal inverse transform, cumulative-floor picosecond deadlines,
absolute unsigned-64 big-endian storage, fail-closed overflow, and versioned
artifact/decoded/envelope SHA-256 identities. It uses the already-approved
Python standard library and adds no dependency.

The acceptance and implementation gates for Stage 7 are satisfied. Full
golden, decoder, semantic, corruption, namespace/common-family, append-only
publication, and completion-independence evidence passes. The decision does
not select concrete lifecycle inputs or authorize an experiment.

## Accepted Q7 — Stage 8 clock suite

State: **`ACCEPTED`**.

The repository owner answered `Q7 - accept the bundle` on 2026-08-20. The
final [D-009 bundle](STAGE8_CLOCK_DECISION_BUNDLE.md) and
[ADR-0030](decisions/0030-stage8-clock-suite.md) therefore select qualified vDSO
`CLOCK_MONOTONIC_RAW`, exact integer nanosecond-to-picosecond conversion,
compiler-only read boundaries, bracketed enqueue-publication/dequeue-observation
timestamps, no overhead correction, and fixed monotonicity, resolution,
read-cost, skew, drift, migration, syscall, and generated-code gates. Direct
TSC remains diagnostic-only for v1 because the supplied stand is dual-socket
and its CPUID ratio does not enumerate a crystal frequency.

Q7 supplies no worker CPU pair and does not treat static inventory as clock
qualification. Stage 8 implements the accepted reader, boundary map, exact
equations, no-correction diagnostic interface, qualification evaluators, and
dual-disassembler/source-mutant rules. Dynamic traced-vDSO, full-count,
affinity/source, selected-pair, and before-block evidence still must pass at
the applicable Phase 9/16 gates.

## Pre-pilot decisions that may remain open after Stage 2

| Decision IDs | Required choice/evidence | Owner | Blocking gate |
|---|---|---|---|
| D-009 | Software/codegen slice passes and Q13 selects explicit `(0,1)`/`(0,26)` pairs; still supply 10-million-call traced vDSO evidence, per-core full-count streams, bidirectional three-window streams, and before-block repetition | Timing/platform/queue-correctness/code-generation owners | Pre-pilot platform qualification; repeat and bind every block |
| D-010, D-020 | Decisions and Stage 11 software pass under Q9/ADR-0032/0033; read-only storage discovery observes one mounted durable data namespace; remaining inputs are the concrete run plan, available bytes/reserve, actual worker-page residency, a second real durable domain/custody boundary, and exact-release recovery proof | Storage/data-integrity/custody owners | Operational capacity/domain/residency/recovery proof by Phase 16 |
| D-008 | Queue pointer width/order/refinement and u32 release/acquire termination mapping are implemented; repeat runtime lock-free/layout probes and integrated generated-code checks on the eligible measured release. | Queue correctness/controller/platform owners | Controller mapping accepted in ADR-0031; stand/release evidence by Phase 16 |
| D-018 | Q13 accepts static near/far pairs and one x86 `PAUSE`; still supply exact watchdog/failure bounds, eligible-stand API/control mapping, capability/readback/probe/rollback evidence, real prefetch mapping, and final combined generated code | Platform/controller owners | Operational evidence before pilot |
| D-019 | Named operator/custodian, accounts/keys/storage, negative access, recovery, and audit retention | Security/custody owners | Operational proof by Phase 16; final authority before confirmation |
| D-040 and protocol freeze inputs | Supply prospective precision results, exact role/common namespaces, master/derived seed catalogs and derivation evidence, platform/build identity, segregated access principals/enforcement, `R_replacement_max`, budget evidence, and final block-plan/access records | Protocol/statistical/block-planning/security/custody owners | Treatment-blind pilot/freeze evidence before final Phase 16 readiness and Phase 18 execution |

These choices must be treatment-blind. Clock, remaining schedule inputs,
mixing, storage, and platform choices cannot be selected or revised because a
performance result is convenient.

## Confirmatory and submission gates

The protocol-defined open values listed at the end of
`docs/IMPLEMENTATION_DECISIONS.md` remain later work. They do not invalidate the
completed Stage 5/6 correctness evidence and must not be fabricated.
Submission identities, venue rules, accessibility, archive, and publication
license remain submission-only.

## Supersession rule

Accepted bundles can change only through new ADRs and full
compatibility/requalification evidence. Any replacement that changes
protocol-fixed scientific behavior stops the affected work and requires a
versioned protocol amendment. Stages 11 through 15 are complete locally under
ADR-0032 through ADR-0041, and ADR-0042 plus snapshot
`STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-01` close the Stage 16
software/bundle/count-level inventory slice. Q13/ADR-0043 then closes only the
runner-entry implementation choices. Q14/ADR-0044 through ADR-0046 accept the
local closure and future authority policies. D-047/ADR-0047 accepts and
implements the physical software-prefetch mapping and closes the strict
combined audit. The clean no-authority candidate is sealed and verified.
D-053's deterministic pointer/counting slice is implemented, committed, and
carried by a separate clean no-authority qualification-tool bundle. Q15-S3
accepted D-054 through D-056. The clean exact commit and separate no-authority
qualification-tool bundle bind the repository-local same-buffer session,
fixed Linux acquisition seams, seven collectors, dynamic profile, and both
strict codegen reports. That release grants no stand access or dynamic
authority.

With the clean controller-bearing v2 base release verified, Q15-R-P2 now closes
owner disposition and repository-local trust-adapter implementation. The new
clean operational release is selected by Q15-R-P3 as evidence only; Q15-R still
needs separately authorized and verified stand setup. It then needs its own
exact signed authorization:
fixed controller argv/endpoint, stand/binding, distinct effective identities,
actual expiry/signature, quotas/custody evidence, and read-only targets. Q15-W remains
blocked until sealed Q15-R evidence and all three complete prestates exist.
Stand-side qualification remains a later exact
Q15-R/Q15-W authorization, and every
Stage 17 phase remains a later dependency-ready Q16 request. Every external
scientific or stand-dependent value remains blocked until its listed evidence
gate. Measurement, calibration execution, pilot, and confirmatory execution
remain prohibited.
