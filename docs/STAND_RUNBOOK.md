# Stage A Stand Runbook

Status: **Stage 17 operational successor `PREPARED`; external inputs
required**. This runbook does
not authorize a platform mutation, calibration, pilot, or confirmatory
execution. Commands in the read-only section only observe state and do not make
the current machine an eligible stand. It becomes operational only after the
corresponding `PLAN.md` gates, authority records, exact mappings, and accepted
platform records are complete.

## Stage 16 operational phase map

The versioned stand bundle deliberately separates these six activities. A pass
in an earlier activity does not imply authority for a later one.

### 1. Install/build verification

Verify the outer archive sidecar before extraction. Extract into a new empty
directory, run the internal verifier, `cpu_prefetch_smoke`, and the preflight
self-test exactly as documented in [`STAND_BUNDLE.md`](STAND_BUNDLE.md). If a
source rebuild is required, extract the bundled source archive and use the
recorded offline dependency prefixes and README commands. Do not substitute a
different compiler, dependency, schema, protocol snapshot, or build flag.

### 2. Nonprivileged inventory

Assign a new evidence ID and UTC timestamp outside the filesystem name, then
run the bundle's read-only collector as an unprivileged account:

```sh
release/bin/cpu_prefetch_preflight \
  --snapshot-id ASSIGNED_EVIDENCE_ID \
  --captured-at-utc YYYY-MM-DDTHH:MM:SSZ > preflight-inventory.json
sha256sum preflight-inventory.json > preflight-inventory.json.sha256
```

Replace both uppercase tokens explicitly. The output is always inventory-only
and does not qualify the stand. No scientific run identity is parsed from its
filename.

The current clean-release example is append-only inventory
[`STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02`](evidence/stage16/STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02/README.md).
Separate hashed
[topology](evidence/stage16/STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01/README.md)
and
[storage](evidence/stage16/STAND-STORAGE-XEON-CPU-FETCH-20260822-01/README.md)
sets support candidate selection and blocker discovery only. They do not
qualify a pair or domain. Q13 accepts the pair/relax/runner entry choices for
implementation only in the
[Stage 17 entry bundle](STAGE17_ENTRY_DECISION_BUNDLE.md); it grants no stand
control or execution authority.

The prospective
[finite Stage 17 operational successor](STAGE17_OPERATIONAL_AUTHORIZATION.md)
now owns pilot admission. Its current state is `PREPARED`; it may advance only
through `AUTHORIZED_FOR_READ_ONLY_PREFLIGHT`, `PREFLIGHT_ACCEPTED`, and
`READY_FOR_STAGE17_PHASE_AUTHORIZATION`. ADR-0105 makes the graph and ten-item
requirement catalog immutable and derives state only from canonical genesis
plus sequential append-only evidence-resolution and transition records. The
legacy successor/checklist are definition/templates, not current status. No
state is inferred from SSH reachability or metadata hashes, and the last graph
state is permission to prepare an exact phase authorization rather than
permission to execute it.

Before the first read-only preflight, complete the exact
[`S17-EXT-001` draft](STAGE17_S17_EXT_001_AUTHORIZATION_DRAFT.md). The owner
must provide the target, pinned host-key evidence, UTC window, finite limits,
archive/sidecar locators, and six exact read-only command/output contracts. Do
not use the draft itself as evidence. Create the authorization and supporting
contract as new repository files, recompute their actual sizes and SHA-256
values, create one append-only resolution, and create the adjacent transition
only after the validator accepts those files. There is one attempt per frozen
observation, zero retry, and partial evidence is retained.

### 3. Privileged capability verification

A separately named platform operator reviews the read-only inventory and
creates the prospective authority/whitelist/readback/probe/restoration plan.
Its future envelope must conform to the current
[`stage17-authorization-v2.schema.json`](../config/schemas/stage17-authorization-v2.schema.json)
and the semantic validator before owner review; schema conformance does not
grant authority.
There is no automatic privileged path in the bundle. Do not use `sudo`, write
sysfs/MSRs, stop services, change boot state, or apply a control until the exact
target/value/inverse and independent verification have been approved.

ADR-0104 supersedes ADR-0050's distinct-identity requirement for Stage 17 pilot
operations only. The declared principal `cpu-prefetch-stage17-pilot-owner` may
act as owner, operator, controller, custodian, and auditor, and every review
must state `distinct_auditor=false` and `independent_review_claimed=false`.
This role collapse does not grant privilege: commands, targets, limits,
readbacks, restoration, and storage paths still require exact evidence and
authorization. The proposed primary qualification-output domain remains the
candidate stand filesystem on `/dev/md3`; an actual independent secondary
custody domain remains external evidence.

### 4. Safe restoration

Before the first authorized apply, capture the exact pre-state and test the
inverse operation. Apply one whitelisted control at a time, restore successful
steps in reverse order on failure, independently reread every restored value,
and retain both success and failure artifacts. Quarantine the stand if
restoration cannot be proved.

For ADR-0049, the only accepted hardware-prefetch mapping is family 06 model
55H, MSR 0x1A4, CPUs 0/1/26, H0 complete unmodified prestate, and H1
`prestate|0x0f`. Preserve bits 63:4, independently read the complete value, run
both regular and pointer-stream probes, restore the complete prestate in
reverse order, and independently reread it. The repository currently has no
production MSR adapter, so these steps cannot be run from the Q15-P0 measurement
candidate. Q15-S1 adds a separate fixed-scope tool, but this runbook does not
authorize its dynamic options. Those require a clean hash-bound tool bundle,
exact signed Q15-R and later Q15-W records, and effective role separation.
D-052 freezes `Q15-PROBE-COLLECTOR-CONTRACT-v1`; the bundle's contract and
validator are documentation/self-test inputs only. There is not yet an
authorized probe/collector command, and the runbook must not improvise one.

### 5. Calibration/pilot preparation

Only after the successor reaches `READY_FOR_STAGE17_PHASE_AUTHORIZATION` and
all entries in `STAGE17-EXTERNAL-INPUT-CATALOG-v1` have verified append-only
resolutions may the owner issue the
exact phase-scoped pilot authorization. Bundle verification, inventory, or
preflight acceptance does not authorize calibration or pilot. Confirmatory
namespaces and outcomes remain inaccessible.

`S17-EXT-006` is not resolved by the historical release metadata. Supply the
real archive and sidecar to the explicit integration checker documented in
[`STAGE17_OPERATIONAL_AUTHORIZATION.md`](STAGE17_OPERATIONAL_AUTHORIZATION.md).
It checks exact bytes, safe extraction, manifest identity, internal bundle
verification, and no-authority flags. Missing or nonidentical bytes keep the
input external-required.

### 6. Artifact transfer to the development repository

End the session, restore authorized controls, seal actual artifacts, and create
a manifest plus SHA-256 inventory. Transfer a byte-identical copy through the
approved custody channel into a new append-only evidence location. Verify the
hashes independently before any repository-side schema or semantic validator
opens the artifacts. Never overwrite an earlier collection or infer identity
from the transfer directory.

## Safe software prerequisites

Use the accepted, pre-provisioned Linux x86-64 toolchain and dependencies from
`README.md`; stand configure/build/test must not fetch from the network. For
inventory, the base OS must expose procfs and sysfs. `lscpu`, `getconf`,
`findmnt`, `taskset`, and `sha256sum` are expected from Ubuntu's standard
util-linux/coreutils packages. `numactl`, `cpupower`, `lstopo-no-graphics`, and
`dmidecode` are optional read-only cross-checks, not substitutes for the typed
collector or independent run-address verification.

Before any actuation adapter is accepted, record the exact stand identity,
kernel and firmware, CPU vendor/model/stepping/microcode, selected core pairs,
NUMA/cache ancestry, measurement build and dependencies, approved platform
operator, allowed targets/values, verification mechanisms, and rollback tests.
Missing evidence remains missing; it is not replaced by a package default.

D-047 fixes `X86-64-PREFETCHW-PREFETCHT0-v1`. Under a future exact Q15, each
already-affined selected worker must independently retain its maximum extended
CPUID leaf and `CPUID.80000001H:ECX`; bit 8 must be set before private-stream
first touch. Inventory CPUID bytes support planning but do not replace this
release-bound dynamic record. No fallback instruction is permitted.

## Privilege model

The measurement process remains unprivileged and receives no `sudo`, Linux
capabilities, writable sysfs, `/dev/cpu/*/msr`, service-management, boot-loader,
or validation-custody access. A separate named platform operator or narrow
audited service may act only before or after the timed horizon and only after
its whitelist, authority, readback, probes, and restoration procedure are
approved.

Inventory and independent readback should normally run without privilege.
Firmware or kernel-log evidence that the OS restricts may be collected by the
platform operator as a separate artifact; granting broader access to the
measurement process is not an acceptable workaround. Successful exit status
from an operator command proves only that the command returned successfully.

## Safe read-only verification commands

The following commands do not request a state change. Review their output and
retain it as development/stand inventory evidence with command, UTC time, exit
status, and SHA-256. Do not prefix the whole list with `sudo`.

```sh
uname -a
cat /etc/os-release
lscpu --json
lscpu --extended=CPU,NODE,SOCKET,CORE,ONLINE,MAXMHZ,MINMHZ
getconf PAGE_SIZE
numactl --hardware
lstopo-no-graphics
taskset -pc $$
cat /proc/self/status
cat /sys/devices/system/cpu/online
cat /sys/devices/system/cpu/isolated
cat /sys/devices/system/cpu/nohz_full
cat /sys/devices/system/cpu/smt/active
cat /sys/devices/system/cpu/smt/control
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
cat /sys/devices/system/cpu/cpuidle/current_driver
cat /sys/devices/system/cpu/cpuidle/current_governor_ro
cat /sys/kernel/mm/transparent_hugepage/enabled
cat /proc/irq/default_smp_affinity
cpupower frequency-info
findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS /
```

Some files or optional tools may be absent. Record that fact and let capability
detection fail closed where the evidence is mandatory. Do not use `taskset -p`,
`numactl` launch options, `cpupower frequency-set`, writes to sysfs, `wrmsr`,
service stops, CPU offlining, IRQ rewrites, or boot-parameter changes in this
read-only step.

## Platform evidence collection

Create a new session directory rather than overwriting an earlier collection.
One safe shell pattern for a small human-readable inventory is:

```sh
stage9_evidence_dir="evidence/stage9/SESSION_ID"
mkdir -p -- "$stage9_evidence_dir"
date -u +%Y-%m-%dT%H:%M:%SZ > "$stage9_evidence_dir/captured_at_utc.txt"
uname -a > "$stage9_evidence_dir/uname.txt"
lscpu --json > "$stage9_evidence_dir/lscpu.json"
lscpu --extended=CPU,NODE,SOCKET,CORE,ONLINE > "$stage9_evidence_dir/cpu-map.txt"
getconf PAGE_SIZE > "$stage9_evidence_dir/base-page-bytes.txt"
cat /sys/devices/system/clocksource/clocksource0/current_clocksource > "$stage9_evidence_dir/clocksource.txt"
sha256sum "$stage9_evidence_dir"/* > "$stage9_evidence_dir/SHA256SUMS"
```

Replace `SESSION_ID` with a new externally assigned identifier before running;
do not derive scientific identity from the directory name. The typed
`LinuxInventoryProvider` additionally reads per-CPU cache/core/package/NUMA and
PCI locality files. Its development-host smoke test is
`ctest --preset dev-gcc -L platform --output-on-failure`; a successful smoke
test is not a platform record or qualification.

For a candidate stand, retain the rich Stage 9 evidence manifest, the exact
imported-schema platform record, command transcripts, binary/dependency hashes,
authority records, pre-state, apply audit, independent readback, behavioral
probes, reverse restoration audit, and Stage 8 clock artifacts. Bind them by
content hashes; never paste a requested value into a verified field.

## Calibration preparation and authority

Stage 13 software completion does not authorize calibration on a stand. Before
an operator schedules any calibration interval, the calibration and platform
owners must append and approve a prospective plan naming the exact stand/build,
all service and ring contexts, verified H0/H1 mechanisms, line/slot geometry,
logical capacities, fixed durations, complete run IDs and counts, minimum ring
series counts, disjoint calibration/probe namespaces and seeds, raw/durable
storage budget, schedule family, operator authority, and stand-hours. No value
comes from a repository default or a development fixture.

Service calibration must reproduce each corresponding Stage A queue, package,
consumer action, placement, capacity, working set, hardware state, software
policy, clock, reset, and drain; continuous-ready producer work is the sole
workload difference. Ring calibration uses R0 with software prefetch absent,
separate H0/H1 plans, preallocated acquire-demand traces, and no confirmatory
access. Zero-loss feasibility is a separate open-loop exactly-one-attempt
probe using predeclared schedule namespaces. Operators may not top up invalid
runs, select a cell-specific rate, or inspect treatment/confirmatory outcomes.

After immutable evidence exists, run only the offline evaluators and schema
checks described in [`CALIBRATION.md`](CALIBRATION.md). A result remains
`NOT_EVALUATED` if a planned run, required context, hash, final `Rtotal`, or
schedule exposure is absent. An R2 cap collapse makes that context ineligible
or requires a prospective capacity revision before freeze. The common scale
ladder may move downward only before freeze and only for the complete matrix.

For software verification without stand output:

```sh
cmake --build --preset dev-gcc --target calibration-check
ctest --preset dev-gcc -L calibration --output-on-failure
```

These commands use synthetic/fake evidence. They are not calibration commands
and must not be archived as platform results.

## Rollback and restoration

Every authorized mutating control must have an independently observed pre-state
and an exact inverse operation before the first apply. Apply one whitelisted
control at a time. On partial failure, stop, restore successfully applied
controls in reverse order, independently read back every restored value, and
retain both the apply and restoration failures. If restoration cannot be
proved, quarantine the stand from measurement and escalate to the platform
owner; do not proceed with a presumed default.

Persistent changes to services, boot parameters, firmware, CPU online state, or
system-wide policy are outside any automatic repository path. This runbook does
not provide mutation commands because their exact targets, values, and inverse
operations are stand-specific evidence still awaiting approval.

## 1. Roles and separation

ADR-0104's single-owner collapse applies only through Stage 17 pilot
operations. It is an explicitly accepted loss of independent operational
review, not a claim that one identity is independent of itself. One owner
authorization may cover one frozen set of read-only preflight observations;
do not create one PKI ceremony per observation.

The following role separation remains mandatory for Stage 18 confirmatory
sealing and access. Pilot role collapse cannot satisfy it:

Before stand access, record named identities and approved combinations for:

- freeze authority;
- platform operator with least privilege for hardware controls;
- controller operator;
- data custodian;
- training analyst;
- validation authority/custodian;
- confirmatory analyst;
- replacement authority;
- independent access/audit reviewer.

The access design must keep validation outcomes technically inaccessible through training selection and prevent H1/H2 access until `H1H2_RELEASED`. A role label without an enforcement boundary is insufficient.

## 2. Authorization gates

### Before any pilot

Require all of the following as immutable, source-hashed evidence:

- the operational successor has reached
  `READY_FOR_STAGE17_PHASE_AUTHORIZATION`, every item in
  `STAGE17-EXTERNAL-INPUT-CATALOG-v1` has a verified resolution, the latest
  journal has one valid predecessor chain, and the exact phase authorization
  binds those record and snapshot hashes;

- accepted queue provenance/licenses/modes, atomic mapping, refinement/progress arguments;
- supported platform inventory with eligible near/far topology;
- clean-room build and exact build/dependency provenance;
- schema and semantic conformance suites;
- unit/property/queue/stress/sanitizer acceptance;
- atomic lock-freedom and generated-code acceptance for every package;
- fixed RNG, derivation, permutation, consumer mixing, checksum, schedule, physical row, compression/copy, and serialization records;
- proven raw-buffer and durable-storage capacity for the proposed pilot horizon;
- authorized affinity/NUMA and hardware-state control/readback procedures;
- clock, processor-relax, timestamp, and boundary acceptance procedures;
- synthetic end-to-end dry run that is explicitly not a performance experiment;
- pilot durations, repetitions, namespaces, treatment-blind acceptance plan, and stand-hours.

Any missing item stops pilot preparation.

### Before confirmatory Stage A

Additionally require frozen application/pilot/calibration outputs: `delta_star`; capacities/residency maps; service calibration and `mu_ref`; rates; matrix zero-loss estimator, inputs, `pi_matrix`, and global rule; `d2`; warm-up/horizon/recovery/effective-tail parameters; environmental limits; `B_boot`; all repetition counts; master/derived seeds; exact block roles/plans; stand budget; replacement cap/authority; technical sealing; and access/signature records.

Verify `Rtotal = max(max(R_H1,R_H2), Rtrain + Rval)` and `Nruns = 180*Rtotal` without inventing any operand. A blocked operand stops confirmation.

## 3. Stand admission

For each authorized session:

1. Verify protocol/import, implementation revision, build artifact, dependencies, and accepted ADR/freeze hashes.
2. Verify the machine identity matches the platform record, including CPU, stepping, microcode, topology, cache line, memory, kernel/OS, firmware/power, SMT state, and the D-047 PRFCHW requirement on both selected workers.
3. Verify authorized storage locations, free capacity, custody/access controls, append-only behavior, clock source, and rollback/recovery readiness.
4. Verify role-specific namespaces and block plans have not been used, mutated, unsealed, or branched.
5. Record the session admission decision. On mismatch, create a pre-run/platform/protocol failure record and do not launch workers.

## 4. Whole-plot procedure

Follow the frozen counterbalanced hardware-state order in the block plan.

At each whole-plot boundary:

1. Platform operator applies only the authorized requested state.
2. Independently record requested state and configuration readback.
3. Run the frozen regular-access and pointer-behavior probes.
4. Record verified state as default, changed, failed, or unknown; never infer “all prefetch off.”
5. Apply the frozen cooldown/recovery and environmental acceptance checks.
6. If verification or environment fails, record failure and stop the affected launch; do not substitute another state or tune from outcomes.

Run the 90 cells within the whole plot only in the pre-generated order. Never reorder because a prior cell was slow, full, low-`N_eff`, inconvenient, or surprising.

## 5. Per-run preparation

Resolve the explicit run identity from protocol, platform, build, block/role, factor cell, and within-cell ordinal. Do not parse identity from paths.

Before worker launch:

- validate manifest/config/schedules structurally and semantically;
- verify arrival/event/node seed references and paired-treatment sharing;
- verify schedule count/order/horizon/checksum and disjoint namespace;
- allocate or confirm persistent arenas, then verify line alignment, footprints, mappings, producer-home shared data, and worker-local private buffers;
- verify linked address-pattern gates and paired checksums where applicable;
- verify pre-horizon record-content checksum and immutable event order;
- verify actual CPU affinity, cache relationship, NUMA residency, build, clock, requested/verified hardware state, and raw-buffer capacity;
- create a `PLANNED` lifecycle manifest without claiming artifacts that do not yet exist.

Any failure remains a pre-run failure with its evidence. Do not fabricate producer, consumer, join, or integrity artifacts.

## 6. Warm-up, reset, and start

1. Use the dedicated warm-up namespace and the same package, software/hardware policy, placement, persistent mappings, and consumer action as the measured run.
2. Execute the frozen warm-up duration; warm-up data never enter inference.
3. Stop new warm-up arrivals and drain all accepted warm-up events.
4. Stop both workers at the phase barrier.
5. Preserve every allocation, first-touch result, and mapping.
6. Restore ring empty slots/cursors or linked sentinel/recycler order exactly; reset event-order position, counters, sample indices, and occupancy; prove no warm-up event remains.
7. Do not remap, regenerate schedules/permutations, broadly retouch payloads, or clear cache/hardware-prefetch history.
8. Synchronize both workers at the start barrier and derive `t0` through the frozen clock protocol.
9. Seal a reset/start phase result. A failure becomes `WARMUP_FAILURE` or `RESET_FAILURE` and stops the run.

## 7. Measurement and drain

During the measured horizon, no operator or controller action may add allocation, blocking I/O, console output, dynamic parsing, compression, aggregation, analysis, state changes, or hot-line observation.

The producer handles the pre-generated half-open deadline stream in order and makes one enqueue attempt per logical arrival. The consumer polls with the fixed behavior, performs the immutable record action, and writes only its private observations. The producer and consumer never share a writable raw buffer.

After the final attempt, the producer release-publishes `arrivals_finished`. The consumer acquire-observes it and drains until empty. Accepted events scheduled within the horizon stay included when action completes in drain. A process interruption, buffer overflow, clock/platform mismatch, or corrupt output is a measurement failure; do not shorten, extend, or improvise recovery within the run.

## 8. Immediate post-run handling

1. Stop data-plane workers and seal every artifact actually produced.
2. Recheck actual CPUs, NUMA residency/migration, hardware state, clock, environment, address identities, final occupancy, node ownership, and record contents.
3. Record final rolling, pre/post content, ordered-index, and address-delta checksums with algorithm/version identities.
4. Reconcile counts and seal producer and consumer envelopes.
5. Attempt the accepted-ordinal join and always seal its audit.
6. Produce joined-derived rows only if the audit passes.
7. Complete lifecycle, join, validity, zero-loss, effective-tail, estimability, block completeness, failure, provenance, and artifact fields independently.
8. Recompute artifact SHA-256 and make the append-only custody transition.

Do not calculate a performance recommendation at the stand.

## 9. Outcome classification

Use these non-interchangeable dispositions:

| Observation | Run validity | Gate consequence | Collection consequence |
|---|---|---|---|
| Correctly reconciled `FULL` | May remain valid | Zero-loss fails; dependent confirmation blocks | Retain; no repeat/replacement |
| Genuine `N_eff < 200000` | Remains valid if otherwise valid | p99.9/effective-tail and dependent confirmation block | Retain; no extension/repeat/replacement |
| Extreme valid latency | Remains valid | Analyze under frozen protocol | Retain; no repeat |
| Correctness/count/clock/placement/sample/integrity failure | Invalid | Original block incomplete | Retain evidence; complete-block replacement only if separately authorized |
| Failed join | Invalid | No joined latency | Retain raw artifacts and failed audit; original block incomplete |

No unfavorable or inconvenient outcome authorizes deletion, reseeding, rate/capacity change, selective repeat, or cell substitution.

## 10. Complete-block replacement

When one required run is genuinely invalid:

1. Retain the original block plan, all its runs, and failure records.
2. Mark the original block incomplete; do not fill the failed cell.
3. Replacement authority verifies failure category, remaining `R_replacement_max`, role, stand-hours, and access state without using treatment favorability.
4. If authorized, create a new complete 180-cell block with new ID/ordinal, same immutable role, new role-compatible seed subspace, and new whole-plot/cell randomization.
5. Cross-link authorization, original, failure, replacement, and budget records.
6. If the cap is reached or authority denies replacement, stop collection and leave the affected study unresolved.

## 11. H3 and H1/H2 access

After collection, custody must enforce the imported access state machine. Training analysts receive only `H3_TRAIN` artifacts. Selection freezes exactly six context choices and source hashes. Validation unsealing requires the authorized predecessor record. The confirmatory analyst evaluates the fixed paired validation family, seals H3 evaluation/access records, and only then may the custodian authorize `H1H2_RELEASED` for all complete common-pool blocks.

Any premature access, summary, log exposure, or analysis is an `ACCESS_LEAKAGE` failure. Stop further release and invoke an independent audit; do not attempt an informal cleanup.

## 12. Session closeout and emergency stop

At each session end, verify append-only storage, hashes, access logs, unused namespace custody, environmental record, failure inventory, and next authorized block identity. Record planned versus completed runs without interpreting effects.

Immediately stop on protocol contradiction, version/hash mismatch, unauthorized access/privilege, platform/build mismatch, failed hardware/clock/NUMA verification, unexplained corruption, storage exhaustion, replacement-cap exhaustion, or loss of custody. Preserve existing evidence and create the appropriate failure record. Resumption requires the responsible authority and all affected gates to be satisfied; it never occurs merely because the stand becomes available again.
