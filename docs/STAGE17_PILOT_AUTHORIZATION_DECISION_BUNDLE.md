# Pre-Stage-17 blocker-closure and pilot-authorization decision bundle

Status: **`Q15_P0_ACCEPTED; V3_LOCAL_PREREQUISITES_IMPLEMENTED_AND_VERIFIED; CLEAN_SEALING_PENDING; NO_STAND_OR_EXECUTION_AUTHORITY`**

Date prepared: 2026-08-22

Protocol: `2.0.0-pre.2`

Accepted decision IDs: **D-044**, **D-045**, and **D-046**

Owners: repository, build, controller, platform, timing, queue-correctness,
storage, data-integrity, security, custody, calibration, protocol, and
statistical owners

This bundle defines how the remaining blockers may be closed and how a later
pilot can be authorized. It supplies no missing platform or scientific value.
Preparing or accepting Q14 does not access the candidate stand, use privilege,
run dynamic qualification, execute calibration or pilot work, expose an
outcome, or authorize confirmatory Stage A.

The current Stage 16 bundle remains an immutable preflight-only artifact. A
later pilot candidate must be a new clean release with a new profile and
hashes; it must not overwrite or silently extend that bundle.

### Q15-P0 addendum

On 2026-08-24 the owner accepted only the recommended pre-Q15 prerequisite
closure. D-048 through D-050 and ADR-0048 through ADR-0050 now correct the
worker-watchdog boundary, fix the candidate Intel 06_55H H0/H1 mapping in
software, and fix the four-role/two-domain prerequisite policy. The current
runner/admission identity is v3. No stand access, dynamic collection, account
or privilege change, MSR operation, calibration, pilot, or confirmation was
authorized. The complete local compiler, sanitizer, static-analysis, schema,
protocol-integrity, and dual-disassembler verification matrix passes; the
uncommitted source still cannot be sealed as an exact clean candidate.

## Current evidence boundary

The following facts are accepted or directly evidenced:

- immutable protocol `2.0.0-pre.2` and its imported hashes;
- Q13/ADR-0043 CPU pairs `(0,1)` for `NEAR` and `(0,26)` for `FAR`;
- one x86 `PAUSE` at every producer/consumer relax site;
- the fail-closed five-specialization runner-entry profile;
- read-only inventory/topology evidence for candidate stand `xeon-cpu-fetch`;
- the Stage 3 through Stage 16 software, sanitizer, schema, synthetic,
  component-codegen, and preflight evidence; and
- the accepted D-035 through D-039 calibration estimators, arithmetic, record,
  invalidation, and treatment-blind global-load rules.

These facts do not establish dynamic pair qualification, an eligible hardware
prefetch state, exact watchdog values, page residency, a second durable domain,
named operational authorities, calibration inputs, a pilot plan, or pilot
execution authority.

## Accepted decisions

| ID | Classification | Options considered | Recommended selection | Evidence | Scientific effect | Compatibility effect | Owner | Deadline/gate | Supersession rule |
|---|---|---|---|---|---|---|---|---|---|
| D-044 | Pre-pilot production-release closure | Treat component seams as a runner; add a generic runtime-dispatch runner; complete the accepted static profile and issue a new fail-closed pilot-candidate bundle; postpone | Complete the accepted static profile with an affined preparation/execution adapter, qualification-only tools, full combined-worker source/dual-disassembler audit, and a new `STAGE17-PILOT-CANDIDATE-BUNDLE-v1`; keep all execution commands disabled unless an exact phase authorization passes | Q13/ADR-0043; Stage 16 component audit; Q14 local implementation and partial audit | Changes no scientific operation; it makes the accepted operation graph auditable as one release | Source, build, runner, specialization, codegen, schema, admission-set, and bundle hashes become release identity | Repository/build/controller/queue/timing/storage owners | Accepted at Q14; resolve physical emitter and strict clean release before Q15 | New profile and ADR; repeat complete clean build, sanitizer, codegen, bundle, and stand qualification |
| D-045 | Stand qualification and privilege authority | Reuse inventory; omnibus root session; one broad qualification authorization; separate nonprivileged/dynamic qualification and exact-whitelist privileged rehearsal | Require a hash-bound qualification authorization for the exact release and stand; separate nonprivileged/dynamic evidence from privileged one-control-at-a-time apply/readback/probe/restoration; no scientific schedule or pilot namespace | ADR-0018 through ADR-0020; Stage 9 interfaces; current inventory-only state; Q13 pair selection | Supplies platform eligibility evidence only; no treatment comparison, `mu_ref`, `d2`, or pilot outcome | Stand/release/pair/control/authority/whitelist/pre-state/readback/probe/restoration hashes are qualification identity | Platform, timing, queue-correctness, security, custody, and audit owners | Policy may be accepted at Q14; no stand execution until a complete future Q15 record is explicitly authorized | New qualification record and requalification after any material stand, release, pair, control, kernel, firmware, or policy change |
| D-046 | Stage 17 calibration/pilot execution authority | One omnibus Stage 17 approval; authorization by shell access; one conditional approval for all dependent phases; immutable phase-scoped authorizations | Authorize only exact dependency-ready phases: D2 calibration, service-rate calibration, feasibility probes, and blinded pilot/freeze collection each receive their own immutable authorization after all phase inputs and predecessor hashes exist | Imported calibration dependency graph; D-035 through D-039; lifecycle/failure/custody rules | Prevents later calibration or pilot inputs from being silently chosen before prerequisite evidence exists; changes no accepted estimator | Authorization ID, phase, run-plan/config/schedule/namespace/seed/budget/stand/build/qualification/storage/authority hashes and expiry are identity | Protocol/statistical/calibration/platform/controller/security/custody owners | Policy may be accepted at Q14; each actual phase requires a later explicit authorization | New prospective authorization linked to the superseded record; completed/failed evidence remains immutable and dependent phases are invalidated by material change |

### Q14 disposition

The owner accepted D-044 through D-046 as governance and implementation policy
only on 2026-08-22. ADR-0044 through ADR-0046 record the selections. Q14
preserves explicit future authority for stand access, privilege, calibration,
pilot, and confirmation; it grants none of them.

## Non-collapsible authorization gates

```text
Q14 preparation policy accepted
  -> local runner/qualification/bundle implementation and clean verification
  -> complete hash-bound qualification request
  -> Q15 stand qualification authorization
  -> qualified stand/release/control/storage evidence
  -> exact dependency-ready Stage 17 phase request
  -> Q16a/Q16b/Q16c/Q16d phase authorization as applicable
  -> immutable Stage 17 evidence and treatment-blind freezes
  -> separate pre-Stage-18 readiness review and authorization
```

No earlier state implies a later authorization. SSH access, a root account, a
successful command, an inventory pass, a buildable runner, or a Q14 acceptance
is not a substitute for Q15 or any Q16 authorization.

## Gate 0: local closure after Q14

Q14 authorizes repository-local implementation and verification only:

1. Complete the affined preparation/execution adapter without supplying
   platform defaults or an execution CLI that can bypass admission.
2. Implement qualification-only artifact producers for selected-pair clock,
   runtime atomic/layout, actual-CPU/migration, and address-residency evidence.
3. Bind the five static package specializations to the accepted queue,
   workload, timing, lifecycle, and bounded-storage components.
4. Audit the complete generated producer and consumer call graphs for every
   package and reject allocation, I/O, logging, compression, parsing, analysis,
   blocking waits, queue retries, scheduler calls, dynamic dispatch, and
   unregistered work.
5. Build a new clean `STAGE17-PILOT-CANDIDATE-BUNDLE-v1` containing the exact
   release, debug-symbol strategy, schemas, validators, qualification tools,
   admission contract, source/build/dependency/SBOM records, and checksums.
6. Repeat the complete compiler, library, sanitizer, stress, schema, static,
   formatting, generated-code, synthetic lifecycle, recovery, and bundle
   verification matrix from clean state.

The bundle must contain no invented watchdog, capacity, duration, namespace,
seed, hardware state, storage path, authority, budget, or pilot authorization.

### Gate 0 implementation result

The v2 admission/profile, owner-thread affinity/readback/actual-CPU preparation,
private-stream first touch, qualification-only typed artifacts, future Q15/Q16
authorization schema/semantic checks, ten-shape combined operation audit, and
strict candidate-bundle target are implemented. GCC passes 207/207 development
tests; the complete Clang/libc++ development suite and all four targeted
runner/lifecycle sanitizer matrices pass. Both release compilers pass the
partial GNU/LLVM audit and forbidden-work mutant.

The owner subsequently accepted D-047/ADR-0047 as
`X86-64-PREFETCHW-PREFETCHT0-v1`. R1/R2 producers use `PREFETCHW`; R1/R2
consumers and the L1 successor use `PREFETCHT0`; all other package/role shapes
contain no software prefetch. Both owner threads must pass PRFCHW capability
after affinity and before first touch. Both release compilers now pass the
strict GNU/LLVM ten-operation audit and four negative mutants. The bundle
creator still rejects dirty trees, drift, overwrite, and authority-bearing
manifests; the exact clean candidate and SHA-256 are release outputs, not
execution authority.

## Inputs that block Q15 stand qualification

Every row remains unresolved until its exact evidence exists.

| Required input | Exact evidence needed | Owner | Current state |
|---|---|---|---|
| Clean pilot-candidate release | Source revision, clean-state proof, compiler/library/link flags, binary and specialization hashes, complete combined codegen report, bundle manifest and SHA-256 | Build/repository owners | `READY_FOR_SEALING`: D-047 mapping and strict combined `PASS` exist; seal from one clean exact revision and retain the archive/hash as Q15 input |
| Start/external watchdog bounds | Exact controller/worker barrier values plus external process wall-clock bound; prospective rationale and failure mapping | Controller/platform owners | `BLOCKED`: ADR-0048 removes unsafe worker-loop caps; remaining exact values have no defaults |
| Hardware-prefetch H0/H1 dynamic evidence | ADR-0049 mapping plus exact prestate, authorized adapter/command, full readback, regular/pointer probes, inverse/restoration and quarantine evidence | Platform/protocol owners | `SOFTWARE_MAPPING_ACCEPTED; DYNAMIC_BLOCKED`: no MSR access occurred |
| Named authority | Four distinct least-privilege operator, controller, custodian, auditor identities; credentials/capabilities, negative-access evidence, validity interval | Security/custody owners | `POLICY_ACCEPTED; OPERATIONS_BLOCKED`: no accounts/keys were created |
| Pair/clock qualification plan | Exact release and pairs, 10,000,000-call traced-vDSO plan, per-core full-count streams, bidirectional three-window plan, thresholds, artifacts, and before-block repetition | Timing/platform owners | `BLOCKED`: software evaluator only |
| Runtime queue/platform proof | Pointer/u32 lock-free and alignment probes, cache-line layout, actual CPU and migration evidence, topology binding | Queue/platform owners | `BLOCKED` on exact release/stand execution |
| Address residency | Producer-home shared pages, worker-local private pages, before/during/after mechanism, migration threshold, unavailable-page-frame treatment | Platform/storage owners | `BLOCKED` |
| Storage/custody | Two distinct durable failure/custody domains, permissions, append-only enforcement, free-space reserve, capacity proof, crash/recovery/hash-readback rehearsal | Storage/custody owners | `BLOCKED`: only `/dev/md3` is presently evidenced |
| Qualification limits | Exact commands/tools, allowed duration/CPU use, output paths, maximum artifacts/bytes, UTC validity interval, stop conditions | Platform/controller/audit owners | `BLOCKED` |

### Future Q15 record requirements

Q15 must name and hash all inputs above. It may authorize only the listed
qualification commands and exact privileged targets. It must explicitly state
that no calibration schedule, pilot namespace, producer/consumer scientific
run, or confirmatory access is allowed. A placeholder, wildcard target,
unbounded root command, unhashed script, or “current/latest” reference makes
Q15 invalid.

## Stage 17 phase authorizations after Q15 passes

Stage 17 is not one executable phase. Later phases depend on immutable outputs
from earlier phases and therefore require separate authorization records.

### Q16a: D2 calibration

Prerequisites include the qualified release/stand/control/storage evidence,
frozen near/far capacities and line/slot geometry, exact duration, a fixed
prospective run count and complete run IDs for each of H0 and H1 in each of the
six placement/working-set contexts, minimum trace-series counts and buffer
proof, disjoint D2 namespaces/seeds, and stand-hours. Evaluation requires at
least 59 valid independent results from each fixed prospective set.

Only ring-off R0 with no software prefetch is eligible. Producer and consumer
demand/issue evidence is retained separately. No top-up is allowed if fewer
than 59 planned runs remain valid. Cap collapse makes a context ineligible or
requires a prospective capacity revision and new evidence.

### Q16b: service-rate calibration

This phase requires accepted D2 outputs so R2 is immutable. Its plan must name
all 60 package/state/placement/working-set cells, fixed duration, an exact
prospective run count and complete run IDs per cell, continuous-ready-only
workload difference, capacities, verified states, namespaces/seeds,
raw/storage budgets, and stand-hours. Evaluation requires at least 59 valid
independent results from each fixed prospective cell set.

`mu_cell` and `mu_ref` are evaluated only from the prospectively enumerated
valid runs. Missing or invalid runs are retained and never topped up. A zero
valid throughput is not discarded.

### Q16c: matrix zero-loss feasibility probes

This phase requires immutable `mu_ref` and the three exact rational candidate
rates. Each evaluated global scale uses a distinct predeclared namespace and a
complete 180-cell open-loop plan with exact run IDs, counts, schedules,
offered-event exposure, buffers, storage, and stand-hours. Candidates form the
accepted descending prefix `1`, `9/10`, `4/5`, `7/10`, `3/5`; stop after the
first passing candidate. No cell-specific adjustment or later favorable probe
is allowed.

The final feasibility freeze remains `NOT_EVALUATED` until immutable
`Rtotal`, `Nruns=180*Rtotal`, and every confirmatory schedule count exist.

### Q16d: blinded pilot and freeze-input collection

The final pilot-collection authorization must prospectively name the exact
pilot matrix, durations, repetitions, schedules, namespaces/seeds, roles,
access restrictions, environment thresholds, storage/stand budgets, and
analysis configuration. Its outputs may support:

- tail-indicator correlation horizons and moving-block diagnostics;
- the common measurement horizon and warm-up/recovery outputs;
- frequency, thermal, interrupt, switch, migration, and residency limits;
- treatment-blind covariance/precision inputs for the fixed 7, 20, 270, and
  540 families; and
- duration and complete stand-budget estimates.

Pilot data cannot enter confirmatory inference, select a favorable treatment,
repair another phase, or authorize Stage A. Validation and confirmatory
namespaces remain inaccessible.

## Exact fields in every Q16 authorization

Every phase authorization is append-only and must contain:

- authorization ID/version, protocol version, phase, status, UTC issuance and
  expiration, authority identities, signatures/checksums, and supersession;
- exact stand, platform, kernel/firmware/microcode, release/build/binary,
  runner/pair/relax, qualification, control, clock, atomic/layout, residency,
  storage-domain, recovery, and custody artifact IDs plus SHA-256 values;
- exact plan/config/schedule/namespace/seed and predecessor-output IDs/hashes;
- permitted run IDs/count, maximum wall-clock hours, maximum storage bytes,
  allowed hardware states and commands, and output locations;
- required preflight, per-run, post-run, restoration, reconciliation,
  integrity, transfer, and semantic-validation gates;
- stop conditions and the disposition of partial artifacts; and
- explicit prohibitions on later phases, confirmatory namespaces, outcome-
  driven tuning, top-up, cell repair, hidden retry, and unlisted privilege.

An authorization that refers to `latest`, a filesystem-derived identity,
unresolved input, range without an exact plan, or artifact without a verified
hash is invalid. An expired, superseded, partially applied, or mismatched
authorization cannot arm the runner.

## Mandatory run and failure rules

Every authorized Stage 17 run follows the existing lifecycle, private-stream,
join, integrity, and append-only rules. In particular:

- one attempt is made for every due open-loop arrival;
- requested and independently verified hardware state remain distinct;
- failure preserves every artifact actually produced and fabricates none;
- a correctly reconciled `FULL`, genuine low `N_eff`, or extreme valid latency
  is retained and never authorizes repetition, extension, or replacement;
- a material release, platform, queue, action, capacity, state, clock, storage,
  or policy change invalidates dependent calibration/pilot evidence; and
- restoration failure quarantines the stand and stops all later phases.

## Stage 17 exit and Stage 18 boundary

After Stage 17 artifacts are sealed and transferred, offline validators and
analysis may create treatment-blind freeze proposals for capacities, `d2`,
`mu_ref`, rates, matrix feasibility, horizon/warm-up/recovery, environmental
limits, `delta_star`, `B_boot`, precision counts, master/derived seeds, block
roles/plans, replacement budget/authority, access sealing, and stand budget.

Stage 17 completion does not authorize confirmatory execution. A separate
readiness report must prove every required freeze and issue a distinct Stage 18
authorization. If any required input is infeasible, missing, invalid, leaked,
or over budget, the affected result remains unresolved rather than being
filled, loosened, or recollected for convenience.

## Accepted approval text

The owner accepted exactly:

```text
Q14 - accept the pre-Stage-17 blocker-closure and phase-authorization governance bundle (D-044 through D-046), and authorize repository-local implementation and documentation of the remaining fail-closed production-runner, qualification-tool, and pilot-candidate-bundle work only. Do not access the stand, execute dynamic qualification, use privileged controls, run calibration or pilot work, or authorize confirmatory execution.
```

Q15 and Q16a through Q16d remain not approval-ready. Their future
approval text must embed or reference the exact authorization record ID and
SHA-256 after every prerequisite field above is complete. Do not answer with a
generic approval for those phases.

### D-047 disposition

On 2026-08-22 the owner replied `I accept everything` to the immediately
preceding exact D-047 confirmation/application statement. That statement fixed
`X86-64-PREFETCHW-PREFETCHT0-v1` and authorized only repository-local
implementation, strict verification, one clean commit on `f/phase-17`, and
creation/verification of the no-authority candidate. It explicitly prohibited
push, stand access, dynamic qualification, privileged controls, calibration,
pilot, and confirmatory execution. ADR-0047 records the decision.
