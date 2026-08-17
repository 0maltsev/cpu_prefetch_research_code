# Experiment Implementation Specification

Protocol version: **`2.0.0-pre.1`**. This version is incompatible with the `1.x` raw-observation and run-manifest data model; lineage and prior hashes are preserved in `handoff/PROTOCOL_VERSION.md` and `handoff/AMENDMENTS.md`.

## 1. Purpose and boundary

This document is the pre-freeze handoff contract for a later implementation phase of the paper *Prefetching and Tail Latency in Lock-Free Inter-Core Queues: Effects of Access Pattern, Placement, and Offered Load*. It defines experimental objects, workloads, measurements, gates, and analysis without providing source code, pseudocode, build files, scripts, plotting programs, synthetic data, or machine-configuration commands. It does not authorize confirmatory execution until every mandatory item in `PROTOCOL_FREEZE_CHECKLIST.md`, including `delta_star`, is frozen.

The implementation must preserve three stages:

- **Stage A:** mandatory confirmatory comparison of a bounded SPSC ring and a linked 1P1C FIFO.
- **Stage B:** exploratory producer-contention extension using tagged-pointer NBLFQ instantiated as MPSC, if the platform satisfies its representation assumptions.
- **Stage C:** robustness ablations for mutable event preparation/ownership, burstiness, interference, pages, ordering, SMT, and overload.

Stage B or C results cannot fill missing Stage A cells. No performance measurement is acceptable before the object and platform gates pass.

## 2. Immutable experiment identity

Every pilot, calibration, confirmatory, diagnostic-counter, or exploratory run requires a unique identifier and an append-only lifecycle manifest. The identifier is composed from explicit versioned fields rather than parsed from a filesystem path: protocol version, stage, platform ID, build ID, block ID, block role, hardware whole plot, package, placement, working-set class, load level, and within-cell run ordinal. The manifest separately records schedule, node, event, warm-up, and bootstrap seed references. Pilot and calibration manifests retain their applicable schedule, seed, provenance, and integrity references; a minimal irreproducible manifest is invalid. A replacement for a correctness or measurement failure belongs to a new complete block with a new identifier; the failed run and original block remain retained. An observed full return or genuine effective-tail insufficiency never creates a replacement run.

The lifecycle state is exactly one of `PLANNED`, `PRE_RUN_FAILURE`, `WARMUP_FAILURE`, `RESET_FAILURE`, `MEASUREMENT_STARTED`, `MEASUREMENT_FAILURE`, `DRAIN_FAILURE`, or `COMPLETED`. Join status is independently `NOT_ATTEMPTED`, `FAILED`, or `PASSED`. An early failure is recordable without nonexistent raw streams. A measurement or drain failure lists every artifact actually sealed, but never fabricates a missing artifact. A failed join requires a join-audit artifact and failure record, not a successful joined dataset. A completed valid Stage A latency run requires producer and consumer raw-stream envelopes, `PASSED` join evidence, a joined-derived stream, phase/integrity evidence, complete counts, and provenance. An invalid run requires at least one failure record. Run validity remains independent of zero-loss and effective-tail status.

The manifest must include:

| Category | Required fields |
|---|---|
| Provenance | repository revision, implementation revision, build artifact hash, compiler identity, full flags, standard library, dependency versions |
| Platform | CPU model, stepping, microcode, sockets, cores, SMT state, cache topology, line size, NUMA map, memory population, firmware and power settings |
| Object | exact algorithm/source, cardinality, capacity, measured resident bytes, event-record size, memory-order mapping, arena/recycle policy, node/event order seeds and delta checksums |
| Treatments | requested and verified HW-PF state, SW-PF policy and resolved distance, placement, working set, load, page policy, batch size, background condition |
| Workload | arrival family, seed, schedule horizon, offered count/rate, exact consumer mixing operation, producer wait, consumer poll, warm-up/reset/start, termination/drain, and recovery rules |
| Timing | clock source, conversion, serialization boundary, overhead calibration, skew/drift check |
| Validity | affinity and before/during/after NUMA verification, address-pattern report, record immutability, frequency/thermal state, migrations, interrupts, context switches, run validity, count reconciliation, zero-loss, effective-tail, confirmatory-estimability, failure category, and block completeness |
| Outputs | lifecycle and join status; every artifact actually present; offered/attempted/accepted/full/consumed counts where available; mandatory full/drop rate; ordered producer and consumer raw-stream envelopes; join audit and, only after success, joined-derived stream; occupancy, counters, derived-artifact links, and phase/integrity evidence |

Manifests and data are append-only after sealing. Any correction produces a new analysis record linked to the unchanged raw record. A correctly reconciled full run may be `VALID` with zero-loss `FAIL`; a genuine low-`N_eff` run may be `VALID` with effective-tail `FAIL`. Neither condition is a failure record or replacement authorization.

## 3. Mandatory experimental objects

### 3.1 Common event representation

Both queues transfer a pointer to the same event-record type. The allocated record size is exactly one measured cache line. It contains an immutable record index, one fixed aligned 64-bit payload word, and inert padding. Logical-event sequence numbers and timestamps reside in producer- or consumer-private observation storage, not in the record. No record contains a mutable ownership field in Stage A.

Each placement/working-set cell uses one persistent, producer-home event-record arena of `C` records for all queue packages and paired hardware/software treatments in a temporal block. Before any run, a separate seed generates a permutation of record indices. Logical arrivals select pointers cyclically from that permutation; records are neither obtained from nor returned to a mutable event pool. Multiple concurrent references are safe because records remain immutable. Every logical producer row carries `run_id`, logical sequence, record index, scheduled arrival, producer-handling start, record/pointer-lookup completion, enqueue invocation, completion of the one enqueue attempt, outcome, and an accepted ordinal plus enqueue-linearization boundary only for `ACCEPTED`. A `FULL` row retains every attempt timestamp but has no accepted ordinal, consumer row, or latency. Every successful consumer row carries `run_id`, consumed ordinal, observed record index, successful-dequeue invocation, dequeue-linearization boundary, dequeue completion, and consumer-action completion. Post-run processing constructs the accepted-event sequence from producer rows and requires consumer row `k` to match producer-accepted row `k`. The join key is run identity plus accepted ordinal; the repeating record index is a validation field, not a globally unique event ID. End-to-end latency is computed only after the exact join succeeds.

One referenced phase/integrity artifact makes the checksum relationship machine-readable. Its manifest entry stores the artifact ID and SHA-256 plus algorithm-record ID, algorithm version, and value for the final consumer rolling checksum, pre-horizon event-record content checksum, post-horizon content checksum, ordered-index checksum, and address-delta checksum. The raw-stream envelopes reference that artifact. Setup also records the virtual address-delta vector, distinct cache-line/page counts, seed, and NUMA page map. A paired run is invalid if any required identity differs. The absolute arena base may differ between independent temporal blocks, but the within-arena delta vector and index order must match.

The complete event schedule, record order, payload initialization, and consumer operation are generated or initialized before warm-up. After every successful dequeue, the consumer reads the record index and payload word, combines them into a consumer-private 64-bit rolling checksum using one frozen deterministic integer-mixing operation, and records consumer completion only after that update. The operation has fixed instruction structure, no payload-dependent branch, and no allocation, and is identical for every Stage A package. It may be selected in the implementation repository before pilot, then its identity and generated-code signature are frozen. The checksum is observed after the run; no record field is made volatile, atomic, or mutable solely to prevent optimization. The producer never rewrites record payload, timestamp, sequence, index, or ownership data during Stage A. Pre- and post-horizon content checksums must match. Mutable preparation, record recycling, and ownership handoff are one separately declared Stage C extension. No record allocation, deallocation, random-number generation, sorting, permutation, formatting, or file I/O occurs during the measured horizon. Queue-metadata and event-record address ranges must be distinguishable in diagnostic attribution where the platform permits it.

### 3.2 Bounded SPSC ring

- **Algorithm and source:** the cache-line-separated SPSC circular buffer in Torquati, *Single-Producer/Single-Consumer Queues on Shared Cache Multi-Core Systems*, Fig. 3 and Sec. 2.
- **Cardinality:** exactly one producer and one consumer; any additional observer may read only out-of-band snapshots that do not touch hot ownership lines.
- **Storage:** a circular array of `C` pointer-sized slots initialized to the distinguished empty value. Producer and consumer cursors occupy separate cache lines and do not share a line with other mutable data.
- **Semantics:** bounded FIFO. A try-enqueue returns full when the next producer slot is not empty. A try-dequeue returns empty when the next consumer slot is empty. Stage A never spins or retries inside the workload driver after either result.
- **Correctness/progress target:** linearizable FIFO try-operations and wait-free completion under SPSC, aligned atomic-pointer, and frozen memory-order assumptions. The source's terminology is not enough by itself; the implemented mapping must pass Section 11.
- **Memory order:** all records are immutable before the horizon. Release publication of the selected pointer and acquire observation protect the slot handoff; no per-event payload publication is claimed. Consumer clearing and subsequent slot reuse are ordered by a release/acquire pair. Thread-owned cursor accesses are relaxed only after a language-model review establishes that the slot handoff carries the required synchronization.
- **Allocation/reclamation:** slot array and event pool are fixed before warm-up. No queue allocator or reclamation mechanism is on the measured path.
- **Timed path:** logical-arrival handling, deterministic record-index lookup, try-enqueue, producer lateness, queue residence, try-dequeue, immutable index/payload loads, and consumer-private rolling-checksum update. No mutable event preparation or event return occurs. Clock sampling is calibrated and recorded as measurement cost.
- **Software-prefetch sites:** the Stage A positive policy is bundled. The producer targets a future ring-slot cache line with a retaining write-intent hint where documented; the consumer targets the same-distance slot line with a retaining read hint. If write intent is unavailable, the producer uses the documented retaining read fallback and the manifest names the package as a distinct platform form. No event record is prefetched in Stage A. Producer-only, consumer-only, or alternative-locality forms are exploratory.
- **Invariants:** producer writes only an empty slot; consumer clears only an occupied slot; cursor wrap preserves slot order; each accepted pointer is consumed once; mutable producer and consumer state do not share a cache line.

### 3.3 Linked 1P1C FIFO

- **Algorithm and source:** Torquati's dSPSC singly linked FIFO and its bounded SPSC node cache, Sec. 3 and Fig. 6, instantiated with a fixed arena rather than fallback general allocation.
- **Cardinality:** exactly one producer and one consumer.
- **Storage and physical allocation:** one page-aligned, virtually contiguous arena contains one sentinel plus `C` event nodes. Each node starts on a measured cache-line boundary and occupies an integral number of lines. The allocation is backed on the producer's NUMA node using the frozen base-page policy; physical contiguity is neither assumed nor required. Producer tail and consumer head occupy separate lines. A bounded circular SPSC pointer recycler transfers detached nodes from consumer to producer.
- **Logical node order:** before first touch, a treatment-blind address seed defines a permutation `pi` of all `C+1` node indices. `pi[0]` is the sentinel and the recycler is initialized in FIFO order with the remaining indices. Returning each consumed old sentinel to the recycler makes zero-loss execution repeat the same `C+1` cycle. The mapping, permutation, and recycler contents persist across paired linked-off/one-hop and `H0`/`H1` runs within a temporal block.
- **Semantics:** operationally bounded FIFO. Empty means the acquired successor of the consumer head is null. Full means the producer cannot acquire a node from the recycler. The full return replaces the source's fallback allocation; this is a declared bounded adaptation.
- **Correctness/progress target:** the published link/unlink discipline is SPSC wait-free. The fixed-arena adaptation must show that replacing allocation fallback by an immediate full return preserves linearizable FIFO safety and terminating try-operations. This claim is blocked until the refinement and stress gates pass.
- **Memory order:** producer initializes node fields, then release-publishes the predecessor's successor link. Consumer acquire-loads that link before reading the successor. After advancing head and completing the last access, the consumer release-publishes the detached old sentinel into the recycler; the producer acquire-removes it before reuse. Head and tail are otherwise single-writer.
- **Allocation/reclamation:** setup places `C` available nodes into the recycler and retains one sentinel in the FIFO. During the run, the consumer returns the old sentinel after each successful dequeue. No general allocator, hazard-pointer scan, epoch, operating-system free, or unbounded retire list is present.
- **Resident footprint:** nodes, padding, sentinel, regular recycler ring, common event pool, and control lines are all included. The actual allocated byte count, not a source-level field sum, determines working-set class. The linked design is not described as a pure linked-only path.
- **Timed path:** logical-arrival handling and deterministic record-index lookup; recycler removal; node initialization and link publication; successor acquisition, immutable event index/payload loads, private rolling-checksum update, head advance, and recycler return.
- **Software-prefetch site:** after the consumer acquire-loads the immediate successor address, the `L1` package issues one retaining read-oriented hint for that successor's node-header line before demanding its event-pointer/header fields. The producer issues no Stage A linked hint; recycler storage and event records are not targets. There is no arbitrary distance parameter.
- **Excluded variants:** jump pointers, helper traversal, multi-hop metadata, node-layout replication, and speculative link chasing are new queue designs and cannot be labelled linked prefetch levels.
- **Invariants:** each arena node is in exactly one state—reachable FIFO, recycler, producer-local transient, consumer-local transient, or sentinel. No node is recycled while reachable; the chain is acyclic; tail is reachable from head; accepted sequence order is preserved; and a zero-loss run follows the frozen node cycle exactly.
- **Address-pattern gate:** a pre-run trace reports all successor-address deltas, the fraction of unit-stride transitions, the fraction of the modal nonzero signed delta, distinct lines/pages, detected period, ordered-index checksum, delta-vector checksum, and physical page-frame order where available. Acceptance requires `C+1` distinct node lines before repeat, no period shorter than `C+1`, at most 1% unit-stride transitions, at most 1% occurrences of any one nonzero signed delta, and exact paired checksum equality. If a seed fails, the next seed in the frozen treatment-blind seed stream is tried before the matrix is frozen. No reseeding follows treatment observation.

### 3.4 Matched-comparison limits

The two objects are matched on producer/consumer cardinality, immutable logical payload, actual event-record arena and sequence, admission rule, shared-data home, common logical capacity, working-set residency class, arrival schedule, and measurement boundaries. Their footprints are not byte-for-byte matched: `F_R(C;P)` and `F_L(C;P)` may differ, and node recycling and metadata are part of the linked package. The primary estimand compares complete queue-design and reuse policies. It must not attribute the full queue-family contrast to pointer dependence alone. A passing address-pattern gate and diagnostic counters/subpath timings provide supporting evidence, not causal isolation.

### 3.5 Queue implementation provenance contract

Before implementation architecture is accepted, each queue receives an immutable provenance record containing: the primary paper and algorithm/figure version; whether an official artifact exists; the exact license for any reused code; whether code is reused unchanged, adapted, or independently implemented from the paper; every semantic adaptation; the language memory-order mapping; required atomic width and alignment; the precise lock-free/wait-free/linearizable claim boundary; and the required refinement argument. The record also links generated-code review, unit/property tests, long stress tests, sanitizer results, and platform atomic-lock-freedom evidence. Unknown official-artifact or license status remains an explicit implementation decision and prohibits silent source reuse. No queue source code belongs in this repository.

## 4. Stage A factor matrix

### 4.1 Platform-relative levels

Let `B` denote measured cache-line bytes. For placement `P`, let `K2(P)` be the smaller usable L2 capacity of the selected producer and consumer. Let `K_home(P)` be the usable capacity of the single producer-home LLC domain after documented sharing: for near it is the one LLC domain shared by both workers, and for far it is the producer-node home LLC only. The consumer's remote LLC is never added. Let `F_q(C;P)` be measured shared hot bytes for package `q`, the common immutable `C`-record arena, recycler where applicable, and required padding at common logical capacity `C`. `F_R` and `F_L` may differ; both must satisfy the selected residency-class criterion.

| Factor | Confirmatory levels and resolution rule |
|---|---|
| Queue/software package | ring-off; ring-one-line; ring-latency-matched; linked-off; linked-one-hop |
| Hardware prefetch | `H0` platform default; `H1` one documented, read-back, behaviorally verified changed data-prefetch state |
| Placement | near distinct non-SMT cores in one NUMA node and the closest LLC-sharing domain; far producer and consumer on different NUMA nodes while shared data remain producer-local |
| Working-set residency | L2-resident; LLC-resident; beyond-LLC, using the capacity rules below |
| Offered load | 0.25, 0.50, 0.75 of conservative calibrated `mu_ref` |
| Event size | one measured cache line containing immutable record index, one aligned immutable 64-bit payload word, and inert padding |
| Cardinality | one producer, one consumer |
| Batch | one logical event per queue call |
| Arrival | pre-generated Poisson schedule |
| Data/page/order/background | producer-home shared data and worker-local private buffers; one verified base-page policy; primary release/acquire mapping; no intentional background load |

Logical capacity is a power of two and is common to both packages within a placement and working-set residency class:

- L2-resident is the largest `C` satisfying `4B < F_q(C;P) <= 0.5 K2(P)` for both packages.
- LLC-resident is the largest `C` satisfying `2 K2(P) < F_q(C;P) <= 0.5 K_home(P)` for both packages.
- Beyond-LLC is the smallest `C` satisfying `F_q(C;P) >= 2 K_home(P)` for both packages.

The rules are resolved separately for near and far. If no common logical capacity exists, the platform is ineligible for that confirmatory class. Capacity is not tuned using confirmatory outcomes. These are matched residency classifications, not claims of equal bytes or that every access hits the named level.

All shared queue storage, the node arena/recycler, and event records are allocated and first-touched by the producer on its NUMA node. Producer-private samples are producer-local; consumer-private samples are first-touched by the consumer and consumer-local. The immutable schedule is producer-local; its creation/checksum and all manifest I/O occur outside measurement, while reading the next deadline is common driver work. Actual CPUs, cache ancestry, allocation nodes, page residency, and migrations are verified before, monitored during, and checked after each run using a documented operating-system mechanism. A mismatch invalidates the run. A single-NUMA or otherwise structurally incomplete platform cannot support confirmatory RQ2; consumer-local, interleaved, replicated, migrated, and alternative-page policies are Stage C only.

### 4.2 Software-prefetch policies

For a pointer-sized ring slot of `b_s` bytes, one cache-line lookahead is `d1 = ceil(B / b_s)` slots. Ring-distance calibration uses the ring-off package and no confirmatory outcome. Producer and consumer slot-demand latencies are measured separately; `ell_star` is the larger frozen conservative value. Producer and consumer issue intervals are measured separately; `c_star` is the smaller frozen conservative value. The latency-matched distance rounds `ell_star/c_star` upward to a whole cache-line distance, is at least two cache lines, and is capped at one quarter of logical capacity. It is frozen separately for every platform, placement, and working-set capacity where the calibration quantities differ, and the same resolved distance is used by producer and consumer within `R2`. If the cap collapses `d2` to `d1`, the cell/platform is ineligible or capacity is revised before freeze. No distance may depend on the sign or magnitude of a treatment effect.

The ring policy applies at the producer and consumer slot-line sites as one bundle. The producer uses the documented retaining write-intent form or the explicitly named read fallback; the consumer uses a retaining read form. The linked policy is only off or a consumer retaining read hint for the immediate successor node-header line. No Stage A policy targets event records or the linked recycler. Numeric ring distances are never compared to “distance one” in the linked FIFO as a common continuous factor.

### 4.3 Hardware-prefetch whole plot

`H0` is the unmodified platform default. `H1` is selected before pilot from documented controllable data-prefetch engines. Each state change requires configuration readback and a separate behavioral probe that distinguishes the states for regular and, where possible, pointer-dependent access. The manifest enumerates engines known changed, known unchanged, and unknown. If the evidence supports only “changed documented subset,” that exact phrase is used; the state is never generalized to all speculative fetching.

Hardware state is a whole-plot factor. Within each temporal replication block, the two state orders are randomized and counterbalanced. All 90 queue/software/placement/working-set/load cells are randomized within a state. A cool-down and verification boundary separates whole plots.

### 4.4 Cell and run counts

There are five queue-nested software packages, two hardware states, two placements, three working-set residency classes, and three offered loads: 180 cells per complete block and platform.

Only after `delta_star` is frozen, the blinded pilot estimates prospective covariance and max-T critical values separately for the registered seven-contrast H1 family and twenty-contrast H2 family. `R_H1` is the smallest complete-block count of at least 20 for which the largest prospective two-sided H1 simultaneous half-width is no more than `delta_star/2`; `R_H2` is defined analogously for H2. Set `R12=max(R_H1,R_H2)`. There is no combined 27-contrast max-T family. A ceiling of 30 is a go/no-go limit for each H1/H2 requirement. If either needs more, H1/H2 do not start until the design, bound, or stand budget is revised without treatment outcomes. The expression is `180 * R12`; 3,600–5,400 is only a planning envelope conditional on the frozen bound and both precision calculations, not a final run count. Pilot, replacements for genuine invalidity, counters, and H3 blocks beyond `R12` are outside that envelope. Full-outcome runs are never replaced.

H3 has separately calculated training and validation counts and inherits no ceiling of 30. There is one common pool of complete confirmatory Stage A blocks. Before execution, each block is assigned exactly one immutable role: `H3_TRAIN`, `H3_VALIDATION`, or `H1H2_SUPPLEMENTAL`. Train and validation use disjoint role-specific block and seed subspaces; there is no separate H1-H2 confirmatory seed namespace. If `R12 > Rtrain + Rval`, exactly the difference is supplemental. If `Rtrain + Rval >= R12`, the train and validation blocks suffice for H1/H2 after the access chronology permits them. The pre-freeze total therefore remains `Rtotal = max(R12, Rtrain + Rval)` and `Nruns = 180 * Rtotal` per platform. Section 10.6 defines the deterministic selection, sealing, unsealing, and analysis-access sequence; none of these counts is final while `delta_star` is unfrozen.

### 4.5 Duration-feasibility gate

The pilot must freeze a wall-clock estimate for each component `s` using the manuscript's parameterized duration model: number of runs multiplied by setup, warm-up, measurement, drain, and recovery time, plus hardware-state-change time. Separate records are required for pilot/calibration, H1/H2 primary runs, additional H3 blocks, each matched counter group, Stage B, and Stage C. The estimate contains measured pilot durations but no fabricated placeholder values.

A documented stand-budget review occurs before Stage A. If the plan exceeds the available budget, optional counter groups and Stages B/C are narrowed first. H1/H2 cells are not dropped selectively. An infeasible H3 is narrowed by a treatment-blind protocol amendment before confirmatory outcomes are opened or is reported exploratory/unresolved. No unfavorable cell may be removed after observation.

## 5. Workload and queue-full semantics

### 5.1 Logical arrival schedule

Before each run, a seeded generator creates all logical arrival times for the applicable horizon. Stage A uses independent exponential interarrival intervals. Matched treatments in a temporal block use the intended common seed family and hence the same logical schedule. Schedule creation is outside the hot path and cannot depend on measured operation completion.

Every schedule envelope records schedule kind, arrival family, namespace and parent namespace, RNG/seed derivation, integer time unit, absolute- or delta-tick encoding, origin, horizon in ticks, exact rational nominal rate as integer event numerator over integer-tick denominator, offered count, overflow-rule record, decoded-deadline checksum, immutable ordering, and either an external immutable deadline artifact or an inline test-only representation. Measurement and warm-up inclusion use the half-open interval `[origin_ticks, origin_ticks+horizon_ticks)`: the origin is included and the end is excluded. The physical deadline encoding remains a pre-pilot implementation decision.

The implementation-side semantic validator must decode the artifact and prove that deadlines are nondecreasing, the decoded count equals `offered_count` and the storage row count, every included deadline lies in the frozen half-open horizon, no deadline depends on queue completion, warm-up and confirmatory namespaces are disjoint, and matched treatments use the predeclared common schedule family. JSON Schema alone cannot prove these cross-item and cross-record invariants.

A logical event exists at scheduled time `a_i`. The producer handles it and makes its single attempt as soon as it can. It selects an immutable record pointer by deterministic lookup in the frozen cyclic index sequence; no payload is materialized or rewritten. If deadlines accumulate, it processes all due sequence numbers in order without moving later deadlines. The original `a_i`, handling-start, pointer-lookup, enqueue-invocation, queue-linearization where accepted, and attempt-completion boundaries are retained in producer-private observation storage. Producer lateness is part of admission delay rather than hidden as generator overhead.

### 5.2 Admission, full, and drain

The Stage A admission policy is exactly one try-enqueue attempt. Success increments accepted count. Full increments full/drop count. There is no retry, wait, or backpressure. Full is an observed outcome, not a correctness or measurement failure: the run remains in the immutable dataset, receives no automatic replacement, and reports accepted-event latency plus mandatory full/drop count and rate. Calibration and pilot runs retain their full outcomes and select capacities and `mu_ref`, before matrix freeze, so strict zero loss is plausible in every required Stage A cell.

The primary Stage A operating regime is strict zero loss (`N_full = 0`); no nonzero acceptable threshold is introduced. If a required confirmatory run has `N_full > 0` with correct reconciliation, the run remains valid and reported but its cell is marked outside the predeclared regime. Every H1/H2 contrast requiring that cell is non-estimable under the confirmatory estimand. A required H3 training or validation cell outside the regime makes H3 unresolved. No candidate or cell is removed and no favorable replacement is substituted.

After the fixed arrival horizon, no new logical arrivals are created. All events scheduled within the horizon are attempted, and accepted events are consumed while the queue drains. Immutable event records require no drain or return. Completion after the horizon remains part of an admitted event's response, eliminating right censoring.

Counts must satisfy offered equals attempted; attempted equals accepted plus full; and, after drain, accepted equals consumed with zero final occupancy. A mismatch is a protocol failure, distinct from a correctly counted full outcome. Producer and consumer ordered observations are joined by run identity plus accepted ordinal as defined in Section 8.4. Record index validates the repeating pointer sequence but is not the logical join key. A count mismatch, unexpected pointer, record-index mismatch, duplicate, mutation, corruption, omission, or forbidden reordering is a correctness failure.

### 5.3 Calibrated offered load

Service-rate calibration reproduces the Stage A queue implementation, consumer checksum action, placement, logical capacity, working-set class, hardware state, and software policy for every required cell. Its sole workload difference is a continuously ready producer used to estimate transfer capacity. It uses fixed-duration independent calibration runs; both duration and repetition count remain freeze outputs. The response for one calibration run is consumed-event throughput over its calibrated interval. For each required package/state/context, `mu_cell` is a one-sided 95% lower confidence bound computed over independent run-level throughput values using a treatment-blind estimator frozen before the calibration results are opened. `mu_ref` is the minimum valid `mu_cell` lower bound over all required Stage A cells.

The initial confirmatory candidate rates are 0.25, 0.50, and 0.75 times `mu_ref`. A separate open-loop feasibility probe replays the actual one-attempt/drop workload at those rates and retains all full outcomes. The decision is matrix-level rather than a collection of zero-observation anecdotes. Before confirmatory outcomes, freeze a treatment-blind estimator, one-sided confidence level, dependence/clustering treatment, minimum acceptable whole-matrix completion probability `pi_matrix`, and global load-reduction rule. For required cell `c`, let `p_U,c` be the simultaneous one-sided upper confidence bound on per-offered-event full probability from pilot/calibration evidence and let `E_c=Rtotal*N_sched,c` be its planned exposure. Without assuming independent event outcomes, the union bound gives the conservative lower bound

`P_L(no FULL in the planned Stage A matrix) = max(0, 1 - sum_c E_c * p_U,c)`.

The pre-confirmatory record stores `Rtotal`, `Nruns=180*Rtotal`, every planned `N_sched,c`, the `p_U,c` inputs and uncertainty method, the simultaneous exposure sum, and the comparison with the still-to-be-justified `pi_matrix`. Observing zero pilot full events does not make `p_U,c` zero. If the bound is insufficient, the project must apply the predeclared global treatment-blind load reduction to all cells, revise capacity before freeze, declare the platform/design infeasible, or leave confirmation unresolved. No nonzero acceptable confirmatory full-rate threshold is introduced. No cell-specific favorable rate, no adjustment after confirmatory outcomes, no confirmatory tuning, no repetition after a correctly reconciled full outcome, and no use of achieved throughput as offered load is permitted. Calibration repeats after any material platform, build, queue, action, capacity, or policy change; that change invalidates the previous freeze.

### 5.4 Warm-up and fixed horizon

Warm-up uses a dedicated seed namespace that is disjoint from calibration, pilot, confirmatory roles, diagnostics, and extensions; warm-up observations never enter inference. It uses the same queue package, software-prefetch policy, hardware-prefetch state, placement, persistent arena mappings, and consumer action as the immediately following measured run. Let `h_max` be the largest valid pilot tail-indicator correlation horizon in event lags and `rho_min` the slowest valid pilot accepted-event rate in events per unit time. Define `tau_corr = h_max / rho_min`; its dimension is time. Warm-up lasts at least `max(5 seconds, 10 * tau_corr)`. No rounding convention or larger duration is chosen from confirmatory behavior.

Warm-up termination and reset follow one state machine:

1. stop creating warm-up arrivals;
2. drain all accepted warm-up events;
3. stop both workers at a barrier;
4. retain allocated and first-touched arenas, virtual mappings, and data homes;
5. restore ring slots empty and producer/consumer cursors zero;
6. restore linked sentinel to `pi[0]` and recycler FIFO order to `pi[1]...pi[C]`;
7. restore event-record sequence position, run counters, and sample indices to zero and verify occupancy zero with no accepted warm-up event present;
8. synchronize both workers at a start barrier and derive measurement `t0` using the frozen clock protocol.

Reset performs no reallocation, remapping, schedule/permutation regeneration, or broad event-payload retouch. Hardware-prefetch and cache history are not explicitly cleared; this is a controlled warm-start with a deterministic logical reset. Randomized/counterbalanced whole-plot order, persistent paired mappings, identical reset code, and a separately frozen recovery interval control carryover. Measurement-only address, count, phase, and checksum reports start at the deterministic origin and exclude warm-up activity.

The pilot freezes the applicable measurement horizon before confirmatory execution using the slowest valid pilot cell. Every applicable confirmatory run uses that horizon. No run stops early, extends, or repeats after observing its treatment-dependent effective count.

### 5.5 Worker waiting and termination

The producer waits for each pre-generated deadline in a tight clock-poll loop using the platform's non-sleeping processor-relax hint. It never calls sleep, yield, or a scheduler API in Stage A. The consumer repeatedly invokes `try_dequeue`; after an empty result it executes the same processor-relax hint and immediately retries. Neither worker uses adaptive backoff or treatment-specific polling. The common driver is specialized before measurement so package selection introduces no virtual dispatch or treatment-dependent branch in the measured hot path. Generated machine code for every package must pass review.

After attempting the final scheduled arrival, the producer release-publishes `arrivals_finished` on a dedicated control cache line. The consumer continues polling until it acquire-observes that flag and the queue is empty, completes the drain condition, and exits. Termination, barriers, and other control fields share no cache line with queue hot metadata. The exact state transitions and memory-order mapping are part of the generated-code and language-model review.

## 6. Stage B contention extension

### 6.1 Queue and eligibility

Stage B uses the tagged-pointer NBLFQ algorithm from Denis and Goedefroit, IPDPS 2025, not an unspecified “MPSC ring.” It is a bounded array queue proved lock-free by its source and instantiated with multiple producers and one consumer. The capacity is a power of two, non-null pointer payloads are used, and the source's modular-counter size relationship must hold. The tagged representation is eligible only when canonical virtual addresses leave the required tag bits and the implementation can validate that assumption. If not, Stage B is omitted; the DWCAS variant requires a separately revised protocol.

Allocation is static. Full and empty returns follow the source algorithm. Memory ordering and atomic width reproduce a reviewed source/artifact mapping and pass the language-level correctness gates; they are not guessed from pseudocode.

### 6.2 Factors and diagnostics

Producer counts are 2, 4, and `Pmax`, where `Pmax` is the largest power of two no greater than eight and no greater than the number of eligible producer cores; duplicate levels are removed. There is one consumer. Producer cores are spread before sharing according to a frozen topology rule, and the exact placement is recorded.

Batch size is one or `B / pointer_size` events. Batching means the application attempts that many consecutive individually timestamped queue operations when scheduled events are ready; NBLFQ's individual queue semantics and linearization points are unchanged. Each event retains its own scheduled arrival and completion. No combined batch atomic or unpublished queue method is introduced.

Stage B uses the LLC-resident and beyond-LLC classes, near and far placements, and 0.50 and 0.75 loads relative to a Stage B calibration. It records per-operation CAS failures, head/tail scan distance, full/empty returns, producer fairness, per-producer admitted/consumed counts, cache-line transfer proxies, and batch-induced visibility delay. These are exploratory families with their own multiplicity control.

## 7. Stage C robustness ablations

Each Stage C ablation starts from a small, predeclared subset of Stage A cells selected without using favorable effects; it varies one robustness dimension at a time.

- **Bursty arrivals:** a documented two-state or batch-arrival process whose mean rate matches the corresponding Stage A load. Burst parameters are frozen before observation.
- **Background cache pressure:** a separate pinned actor with working sets targeting private cache or LLC. It cannot access queue/event memory.
- **Background bandwidth pressure:** a separate actor with a declared memory footprint and access pattern, pinned outside worker cores where topology permits.
- **Page policy:** verified base-page and huge-page/alternative placement levels, if both are available.
- **Ordering sensitivity:** only mappings independently proved semantically equivalent to the Stage A object.
- **SMT:** producer and consumer on sibling hardware contexts of one physical core, reported as a distinct topology rather than “near.”
- **Overload:** rates above calibrated capacity with drop, retry, and backpressure treated as separate workload semantics and separate denominators.

Stage C keeps scheduled arrivals independent of completions unless the treatment is explicitly a backpressure system. Closed-loop or retry experiments are labelled accordingly and never compared as though their offered-arrival process were identical to Stage A.

## 8. Timing protocol and response definitions

### 8.1 Timestamp boundaries

For logical arrival `i`, the producer records `a_i`, the pre-generated scheduled arrival; `b_i`, the first timestamp after leaving the deadline wait and beginning handling of this due arrival; `c_i`, completion of deterministic record/pointer lookup; `u_i`, invocation of the single `try_enqueue`; and `r_i^e`, its response/completion for either `ACCEPTED` or `FULL`. An accepted row additionally records `p_i`, the queue-specific successful enqueue linearization/publication boundary, and its accepted ordinal. A `FULL` row has no `p_i` and no accepted ordinal.

For each successful dequeue, the consumer records `v_i`, invocation of that successful `try_dequeue`; `q_i`, its queue-specific removal/linearization boundary; `r_i^d`, response/completion of the dequeue call; and `f_i`, completion of the immutable index/payload loads and consumer-private rolling-checksum update. Every logical row carries `run_id`; identity is never inherited only from a path or enclosing file.

The exact derived quantities are:

- producer lateness `L_i^prod = b_i-a_i`;
- pointer-lookup interval `S_i^lookup = c_i-b_i`;
- enqueue invocation-response service `S_i^enq = r_i^e-u_i`;
- admission delay `D_i^adm = p_i-a_i` for accepted events;
- queue residence `D_i^res = q_i-p_i`;
- successful dequeue invocation-response service `S_i^deq = r_i^d-v_i`;
- post-dequeue delivery interval `D_i^delivery = f_i-q_i`;
- consumer action interval `S_i^action = f_i-r_i^d`;
- end-to-end latency `L_i = f_i-a_i = D_i^adm + D_i^res + D_i^delivery`.

The three `D` intervals in the final identity are the only additive partition. Producer lateness, pointer lookup, and enqueue service are nested diagnostics within or overlapping admission; dequeue service and consumer action are nested within the post-publication path, and consumer action is a proper suffix of delivery. They are never added again. Recording queue-specific linearization boundaries prevents enqueue and dequeue response overlap from producing a false negative residence interval. The semantic validator checks every timestamp order and equation exactly in integer ticks.

For one run, include every accepted event whose scheduled arrival lies in the post-warm-up measurement horizon and whose fixed action finishes either in that horizon or during drain. If these `N` observed latencies sorted nondecreasingly are `X_(1),...,X_(N)`, every run quantile uses the non-interpolated inverse empirical CDF `Qhat_p = X_(ceil(pN))`. Repeated equal values remain separate order-statistic observations, so ties require no interpolation. Events are never pooled across runs. A dropped event retains `a_i`, `b_i`, `c_i`, `u_i`, and `r_i^e` and contributes to lateness, lookup, enqueue-service, and full/drop diagnostics. It has no accepted ordinal, consumer row, admission/residence/end-to-end latency, or joined-derived row.

The primary run response is `Y_r = log(Qhat_0.999)`. Secondary responses use the same estimator for p50, p90, p99, and qualifying p99.99, and include maximum with sample count and horizon, operation service quantiles, throughput, occupancy, producer lateness, and mandatory full/drop counts and rates.

### 8.2 Clock requirements

The clock must be monotonic on both worker cores, have a documented or calibrated conversion to time, and pass cross-core offset and drift checks before each temporal block. Timestamp boundaries must prevent compiler motion and provide platform-required read serialization without changing queue memory order. The overhead distribution is calibrated for the exact boundary sequence and build.

If overhead correction is used, the correction rule is frozen from calibration and both corrected and uncorrected values are retained. A negative corrected interval, clock regression, excessive drift, or failed skew bound invalidates the run. The clock and queue synchronization roles remain separate.

### 8.3 Sample storage

Every pilot, calibration, and confirmatory Stage A latency run stores ordered per-event observations in preallocated thread-private buffers. Producer and consumer never share a writable observation buffer during measurement. Buffer capacity is frozen for the full scheduled horizon and drain; overflow is a measurement failure rather than a signal to aggregate or overwrite. Raw observations become immutable after run completion and may be compressed only afterward with a frozen lossless format. Histograms, quantiles, CCDFs, and other summaries are derived artifacts and never substitute for ordered primary data. Hot-path aggregation, dynamic growth, locks, file I/O, and formatted output are prohibited. Counter-only diagnostic runs may emit smaller products only if the corresponding primary latency run already exists and their diagnostic contract does not require ordered event analysis.

The normative contract separates logical rows from physical storage. `raw-observation.schema.json` is a small envelope that names the logical-row schema version and later-frozen physical-format record, encoding, integer time unit, endianness, compression, row count, byte count, artifact SHA-256, immutable ordering, and integrity-artifact reference. Production envelopes reference an external immutable artifact; inline JSON rows are permitted only for validation fixtures and examples. For an external artifact, the semantic validator must decode exactly `row_count` records under the frozen physical-format record, validate every decoded record against the stream-kind logical-row definition, and prove that each row's `run_id` equals the envelope identity. The exact binary or columnar encoding, alignment, and lossless compression remain blocked before pilot and may be selected in the implementation repository without changing the logical scientific fields.

Storage feasibility is symbolic until physical row sizes and schedules are frozen. Let `N_sched,r` be scheduled producer rows and `N_acc,r` accepted consumer/joined rows in run `r`; let `b_P`, `b_C`, and `b_J` be bytes per physical producer, consumer, and joined row. The measured-path buffer requirement is

`B_hot,r >= N_sched,r*b_P + N_acc,r*b_C`,

with the conservative allocation `N_sched,r*(b_P+b_C)` because `N_acc,r <= N_sched,r`. Since effective count cannot exceed accepted raw count, an estimable primary tail also requires `N_acc,r >= N_eff,r >= 200000`. If `m_tmp` temporary copies and `m_dur` durable copies are frozen, uncompressed storage planning is

`B_total >= sum_r [(m_tmp+m_dur)*(N_sched,r*b_P + N_acc,r*b_C) + m_dur*N_acc,r*b_J]`,

where the Stage A sum contains `Nruns=180*Rtotal` runs. Compression is applied only after measurement and receives no credit in the hot-buffer bound. No numerical estimate is valid until row sizes, schedules, copy policy, and compression format are frozen.

### 8.4 Producer/consumer observation join

Producer-private rows contain every field and boundary in Section 8.1 for every logical arrival. Consumer-private rows contain every Section 8.1 consumer boundary for successful dequeues. Post-run processing filters producer rows to the accepted sequence and assigns accepted ordinals in logical-arrival order. Consumer row `k` must match producer-accepted row `k`; the join key is `(run_id, accepted_ordinal)`. Record index is a required validation field but is not globally unique because the immutable record cycle repeats. Every physical row carries `run_id`, even though the envelope also carries it; envelope/row disagreement is a semantic failure.

The join fails on any count mismatch, unexpected pointer, record-index mismatch, duplicate, omission, forbidden reordering, timestamp-order violation, or derived-equation violation. A join-audit artifact is produced for every attempted join and records `PASSED` or `FAILED`; no latency is computed before it passes. Only a passed audit permits a joined-derived stream. Each joined row names producer and consumer source-row ordinals and contains every source timestamp and every derived interval in Section 8.1. Its envelope names both source artifact IDs and SHA-256 hashes. Raw source rows are append-only; correction creates a new derived record and never mutates them.

### 8.5 Matched subpath diagnostics

Primary latency runs contain only the timestamp boundaries required for the primary and ordinary enqueue/dequeue intervals. Separate matched diagnostic builds/runs may add a boundary for deterministic immutable-record pointer lookup and, for the linked package, recycler obtain, node initialization, link publication, unlink/head advance, and recycler return. There is no Stage A event-pool obtain/return boundary. Diagnostic runs must use the same cell, arrival/node/event seeds, arenas, and validation gates. Their observations are never substituted for primary end-to-end response.

## 9. Performance-counter protocol

Primary latency runs do not multiplex large counter sets. Matched counter runs use the same immutable cell, block, schedule seed family, and validation gates, with one counter group at a time.

| Group | Intended observables | Interpretation limit |
|---|---|---|
| Demand hierarchy | retired demand loads, L1/L2/LLC misses/fills | model-specific attribution; not individual-event delay |
| Prefetch | HW/SW requests, useful hits/fills, unused or late activity where exposed | engines may be aggregated; “useful” definitions differ |
| Stall/MLP | stalled cycles, outstanding misses, fill-buffer pressure | overlap prevents additive conversion to time |
| Coherence | cache-to-cache, modified-line, snoop/directory, ownership proxies | event coverage and source domain vary by CPU |
| Local/remote memory | local/remote reads, controller traffic, interconnect and bandwidth | NUMA attribution may be sampled or indirect |
| Contention | CAS attempts/failures, scan/retry counts for Stage B | software counts and PMU events must be distinguished |
| Disturbance | frequency, cycles, migrations, switches, interrupts, thermal indicators | validity and sensitivity, not treatment response |

Where address filtering, data-source attribution, or sampled addresses permit, diagnostic groups distinguish ring-slot or linked-node metadata, linked recycler, and common event-record ranges. Unavailable attribution is recorded rather than inferred. For every event, record processor manual source, encoding, privilege level, core/uncore domain, counting interval, multiplex fraction, sampling/skid behavior, overflow handling, and known errata. Counter correlations can corroborate a randomized contrast but cannot by themselves establish that a mechanism caused a tail change.

## 10. Statistical analysis contract

### 10.1 Units, pairing, and model

One complete run is the independent experimental unit. Millions of events within that run estimate its quantile; they are not millions of replications. Runs are paired within temporal block by platform, arrival-seed family, placement, working set, and load. Hardware state remains a whole-plot factor.

The five package rows use explicit full-rank columns: `R0=(q=0,xR1=0,xR2=0,xL1=0)`, `R1=(0,1,0,0)`, `R2=(0,0,1,0)`, `L0=(1,0,0,0)`, and `L1=(1,0,0,1)`. Hardware is centered at `-1/2,+1/2`; placement, working set, and load use full-rank sum-to-zero columns. The confirmatory model contains package baseline columns; hardware and context main effects; queue-by-context; queue-by-hardware; hardware-by-each-software-column; hardware-by-context; and each software-column by context. It preserves platform, temporal-block, hardware whole-plot, and run error.

The hardware-by-software columns are mandatory. No hardware-by-software-by-context term is confirmatory. Hardware context effects are package-averaged and software context effects are hardware-averaged. Any condition-specific higher-order fit is exploratory. Platform is random only with at least three independently sampled platforms; otherwise it is fixed and conclusions are platform-conditioned.

Before confirmatory analysis, the frozen design matrix must have exact full column rank, no empty cells, no aliases with build or seed families, and an estimable row for every identifier in Sections 10.2 and 10.3. Failure blocks that hypothesis family. Missing cells and aliased terms are not imputed or silently removed.

### 10.2 Confidence, practical bounds, and multiplicity

All primary intervals are 95%. The practical bound `delta_star` is not frozen because no application latency budget or authorized engineering decision exists in the repository. The candidate `delta0=log(1.05)` is a sensitivity value only. Before confirmatory execution, a treatment-blind engineering record must select one bound after accounting for extra hint instructions, hardware-state complexity, clock resolution, blinded baseline variation, and deployment/maintenance cost. It must use an application latency budget and cannot inspect treatment labels or effects. The selected bound, rationale, and reviewers are frozen, and all H1/H2 and H3 precision calculations and final repetition counts are recomputed. Confirmatory execution and H3 validation cannot start earlier.

H1 and H2 use separate standardized complete-block bootstrap max-T simultaneous intervals, not Holm-adjusted ordinary intervals. Before analysis, freeze a bootstrap replicate count `B_boot` and RNG seed. Let `C_hat` be one family's original complete contrast vector. For each replicate, resample complete temporal blocks with replacement within platform while preserving both hardware whole plots, all cells, paired arrival/node/event seeds, and the split-plot structure; refit the frozen model; and store the complete `C_hat^(b)` vector. The sample covariance of those vectors is `Sigma_hat`, with `s_j = sqrt(Sigma_hat[j,j])`. For each replicate compute `T_b = max_j abs(C_hat_j^(b)-C_hat_j)/s_j`; the empirical 95th percentile is `c_0.95`. The simultaneous interval is `C_hat_j +/- c_0.95 s_j`. Practical difference requires a whole adjusted interval beyond a bound; practical equivalence requires the whole adjusted interval inside both bounds; other outcomes are inconclusive. No event-level bootstrap is nested as another primary variance layer.

Prospective sizing preserves this separation. Using blinded pilot covariance, calculate `R_H1` from the seven-member H1 max-T family and `R_H2` from the twenty-member H2 max-T family, each against the `delta_star/2` half-width criterion and each with its own critical value. Set `R12=max(R_H1,R_H2)`. No 27-member union is used for sizing or inference.

Tail amplification relative to median is the difference of log-ratios: the named treatment `t` versus its predeclared baseline `0` for p99.9, minus the same treatment/baseline log ratio for p50. All quantiles use the inverse empirical-CDF order statistic defined in Section 8.1; ratios computed from pooled event samples are not permitted.

### 10.3 Exact H1/H2 contrast registry

Let `DeltaH(g,c)` be changed-minus-default hardware effect for package `g` in context `c=(P,W,A)`. Let `ER1`, `ER2`, and `EL1` be the hardware-averaged within-family software effects defined in the manuscript. H1 contains exactly seven two-sided contrasts, all averaged equally over the 18 contexts and controlled together:

| Stable ID | Definition and fixed treatment |
|---|---|
| H1-SW-R1 | `average_c[ER1(c)-EL1(c)]` |
| H1-SW-R2 | `average_c[ER2(c)-EL1(c)]` |
| H1-HQ | `average_c[DeltaH(L0,c)-DeltaH(R0,c)]` |
| H1-HS-R1 | `average_c[DeltaH(R1,c)-DeltaH(R0,c)]` |
| H1-HS-R2 | `average_c[DeltaH(R2,c)-DeltaH(R0,c)]` |
| H1-HS-L1 | `average_c[DeltaH(L1,c)-DeltaH(L0,c)]` |
| H1-R12 | `average_c[ER2(c)-ER1(c)]` |

For H2, define `EH(c)` as the changed-minus-default hardware effect averaged equally over all five packages. Define context operators `P` (far minus near), `W12` (LLC minus L2), `W23` (beyond minus LLC), `A12` (0.50 minus 0.25), and `A23` (0.75 minus 0.50); each averages the two context axes not named. H2 contains exactly these 20 two-sided contrasts in one max-T family:

| Operator | Hardware effect | Ring one-line effect | Ring matched effect | Linked one-hop effect |
|---|---|---|---|---|
| P | H2-P-H | H2-P-R1 | H2-P-R2 | H2-P-L1 |
| W12 | H2-W12-H | H2-W12-R1 | H2-W12-R2 | H2-W12-L1 |
| W23 | H2-W23-H | H2-W23-R1 | H2-W23-R2 | H2-W23-L1 |
| A12 | H2-A12-H | H2-A12-R1 | H2-A12-R2 | H2-A12-L1 |
| A23 | H2-A23-H | H2-A23-R1 | H2-A23-R2 | H2-A23-L1 |

Each H2 ID applies its row operator to `EH`, `ER1`, `ER2`, or `EL1` according to its final suffix. Every H1/H2 ID is non-directional, uses `[-delta_star,+delta_star]`, and has the exact averaging rule above. No raw ring-on mean is contrasted with a raw linked-on mean as if their software policies or numeric distances were common.

### 10.4 Event dependence and time blocks

The pilot computes the autocorrelation of the indicator that event latency exceeds the pilot p99.9. The correlation horizon is the first lag after which absolute autocorrelation stays below `1.96 / sqrt(N)` for ten consecutive lags. The moving-block length is twice the largest horizon over valid pilot cells, rounded upward to an event. The rule, selected length, and horizon are frozen before confirmation.

Moving event blocks are used only to estimate effective tail count, choose the measurement horizon, check stability of the run-level inverse-ECDF quantile, and perform half/double-length sensitivity analysis. They are not an inner variance component in H1/H2/H3 inference. The only primary resampling unit is the complete temporal block described in Section 10.2; no bootstrap treats event samples as independent runs.

### 10.5 Effective tail count

Effective count uses a positive-sequence estimate of integrated autocorrelation time for the tail indicator. Primary p99.9 requires at least 200 expected effective observations beyond the quantile: `N_eff >= 200,000`. p99.99 is reported only with `N_eff >= 2,000,000`. Maximum latency is always accompanied by run duration and effective/raw sample counts and is not used as a stable population quantile.

The treatment-blind pilot freezes a horizon satisfying these rules for the slowest valid pilot cell, and every applicable confirmatory run uses it. If a genuine, correctly recorded confirmatory run has `N_eff < 200,000`, the run remains retained and is not automatically repeated or extended. It fails the effective-tail estimability gate; the affected p99.9 cell and every dependent confirmatory contrast become non-estimable, and the failure is reported as an observed precision/regime outcome. Genuine high autocorrelation or low accepted count is not sample loss or measurement failure. Only actual sample loss, buffer overflow, process interruption, corrupt output, or another measurement failure may invalidate a run. Insufficient p99.99 suppresses only that secondary estimate.

### 10.6 H3 training and validation

H3 is conditionally confirmatory only for the six predeclared contexts formed by both placements and all three working-set residency classes at offered load 0.50. The frozen candidate order is `(R0,H0)`, `(R0,H1)`, `(R1,H0)`, `(R1,H1)`, `(R2,H0)`, `(R2,H1)`, `(L0,H0)`, `(L0,H1)`, `(L1,H0)`, `(L1,H1)`. Selection is independent for each context.

For every candidate/context, compute the arithmetic mean of training-block responses `Y_r = log(Qhat_0.999)`. Select the smallest mean; this is equivalent to selecting the smallest geometric mean of the run-level p99.9 estimates. Exact ties use the listed candidate order. Validation data, adaptive features, counters, and treatment-dependent removal are forbidden. A missing, invalid, zero-loss-regime-failed, or effective-tail-inestimable required training cell makes H3 unresolved; no value is imputed and no candidate is removed.

`Rtrain` is at least 12 and is sized before selection from the complete candidate set. In each of the six contexts, evaluate prospective standard errors for all `choose(10,2)=45` unordered candidate differences, giving 270 differences. `Rtrain` is the smallest full-rank count for which the largest prospective standard error over all 270 is no greater than `delta_star/2`.

`Rval` is at least 8 and is also sized before selection. Construct every ordered candidate-minus-alternative comparison in every context: `6*10*9=540`. Using blinded pilot covariance and the one-sided max-T critical value for that complete pre-selection family, choose the smallest count for which the largest prospective simultaneous half-width over all 540 comparisons is no greater than `delta_star/2`. The later validation report contains only the 54 selected-minus-alternative comparisons implied by the frozen six selections. Validation is never resized using training effects, selected identities, or validation outcomes, and validation remains sealed during sizing. This conservative rule is independent of every possible selected-candidate vector. Any replacement rule must be mathematically proved selection-independent and at least as conservative for all possible selections before a protocol amendment. `Rval` is not capped at the H1/H2 limit of 30. Neither count is final while `delta_star` remains unresolved.

`H3_TRAIN` and `H3_VALIDATION` are disjoint, preassigned role subspaces within the common Stage A namespace. Held-out artifacts remain sealed until block roles, rule, tie break, candidates, six contexts, `B_boot`, bootstrap seed, `delta_star`, `Rtrain`, `Rval`, the 270/540 prospective sizing records, and input hashes are immutable. Access then follows this exact chronology: (1) open training only; (2) select independently in six contexts; (3) write and sign/checksum the immutable selection record containing exactly one candidate for each stable context key, all training artifact IDs/hashes, rule version, authority, and transition to `SELECTION_FROZEN`; (4) record authorized validation unsealing with selection ID/hash, validation namespace ID, validation artifact ID/hash, nonempty affected validation blocks, and transition to `VALIDATION_UNSEALED`; (5) open validation and evaluate H3, storing the selection, namespace, validation, unseal-record, and evaluation artifact hashes with the transition to `H3_EVALUATED`; (6) seal the H3 analysis/access record; and only then (7) create the authorized `H1H2_RELEASED` record and permit H1/H2 to use all complete `H3_TRAIN`, `H3_VALIDATION`, and `H1H2_SUPPLEMENTAL` blocks. H1/H2 access before step 7 is a leakage failure. The freeze schema enforces required record shape; the semantic validator verifies referenced hashes, chronology, block roles, namespace membership, authority identity, and append-only lineage.

After selection, form paired validation-block differences `selected - alternative` against each of the other nine candidates. Resample complete validation blocks and use the standardized one-sided statistic `T_b+ = max_j (D_hat_j^(b)-D_hat_j)/s_j`; the upper limit is `D_hat_j + c_0.95,+ s_j`. H3 passes only if every one of the at most 54 upper limits is below `delta_star`. A missing, invalid, zero-loss-regime-failed, or effective-tail-inestimable required training or validation cell makes H3 unresolved. If precision or stand budget fails, H3 is narrowed only by a treatment-blind amendment before outcomes or remains unresolved. Leave-one-training-block-out selection frequency is supplementary only.

### 10.7 Exclusions and sensitivity

Predeclared correctness or measurement invalidity reasons are:

- lost, duplicate, corrupted, or forbidden-reordered event;
- failed count reconciliation or nonzero final occupancy;
- affinity, actual-CPU, NUMA, HW-PF, or clock verification failure;
- producer-home shared-data, worker-local private-buffer, node-order, or event-order verification failure;
- unit/modal-stride threshold, period, distinct-line/page, or paired address-checksum failure;
- migration of a pinned worker;
- sample loss or ordered-buffer overflow;
- process interruption or corrupt raw output;
- frequency, thermal, interrupt, context-switch, or other disturbance beyond pilot-frozen limits;
- build/manifest mismatch or incomplete raw data.

A correctly reconciled full return, genuine effective-tail insufficiency, and an extreme valid latency are never exclusion reasons. Full-outcome and low-`N_eff` runs are not automatically repeated. They retain ordered observations and derived summaries but fail their separate zero-loss or effective-tail gate. Sensitivity analyses restore runs excluded only for environmental disturbance, use half and double the moving-block length to check the fixed inverse-ECDF quantile, report uncorrected timestamps, and show per-block effects. Pilot, calibration, confirmatory, and exploratory observations remain in disjoint namespaces.

### 10.8 Complete-block replacement

One invalid required run makes its original confirmatory 180-cell temporal block incomplete for primary H1/H2 bootstrap inference. No single cell is rerun into that block. The complete original block plan, every valid and invalid run, and all failure records remain append-only. If the pre-frozen `R_replacement_max` budget and named replacement authority permit, schedule a new complete 180-cell block with a new block ID, the same immutable role as the failed block, a new role-compatible seed subspace, and a new randomized hardware whole-plot and within-plot cell order. The failed identity and seeds are never reused.

An original block records both `replaces_block_id` and `replacement_authorization_id` explicitly as null and has null replacement lineage. A replacement records both as nonempty strings and includes the replaced ordinal, role, and seed subspace. Schema validation checks those combinations. The implementation semantic validator additionally proves different block IDs and ordinals, different role-compatible seed subspaces, equal immutable roles, exactly 180 unique cell ordinals, one occurrence of every Cartesian-product cell, exactly one `H0` and one `H1` whole plot, and role/package-compliant seed references. Array `uniqueItems` is not accepted as proof of factorial completeness.

An incomplete original block may enter only a predeclared diagnostic or sensitivity record, never the primary complete-block bootstrap. Correctly reconciled full outcomes and genuine effective-tail insufficiency do not make a block invalid and never authorize replacement. When the number of replacement blocks reaches `R_replacement_max`, confirmatory collection stops and the affected study remains unresolved rather than repeating until a complete favorable dataset appears.

## 11. Correctness and validation gates

### 11.1 Object-level gates

Both mandatory queues must pass:

- single-thread abstract FIFO and boundary tests;
- long concurrent sequence tests with delayed producer and consumer;
- empty, full, wraparound, and repeated reuse stress;
- exact first/final/internal sequence reconciliation;
- no duplicates, corruption, or forbidden reordering;
- language-model data-race and undefined-behavior analysis;
- confirmation that required atomics are lock-free;
- generated-code review for publication/observation boundaries;
- progress tests in which either thread is suspended at relevant phases.

The linked FIFO additionally requires a written refinement argument for fixed-arena full semantics, a node-state ownership audit, and stress that forces repeated transfer through FIFO and recycler. No node may appear in two states or be recycled while reachable.

It also requires exact reproduction of the frozen `C+1` node permutation; the full successor-delta distribution; unit-stride and modal signed-delta fractions within the 1% limits; `C+1` distinct node lines; page count; no detected period shorter than `C+1`; and matching ordered-index and delta-vector checksums across paired treatments. The physical page-frame order is retained where the operating system exposes it. Failure before freeze advances to the next treatment-blind seed; failure after freeze invalidates the run and blocks the affected cell.

The common immutable record arena must reproduce the same index order, aligned payload words, rolling-checksum operation, distinct line/page counts, and address-delta checksum across ring and linked packages and paired treatments. Every record's pre/post-horizon content checksum must match. Generated-code/data-race review must establish the expected record loads and private checksum update, that the producer writes no record field during Stage A, and that no virtual dispatch or treatment-dependent hot-path branch was introduced. The producer and consumer streams must join exactly by accepted ordinal; unexpected pointers, index mismatches, duplicates, loss, or reordering are correctness failures. Queue metadata, termination control, and event-record address ranges must not overlap hot cache lines.

Stage B additionally validates NBLFQ's tagged-address assumption, counter-size/capacity relationship, modular wrap behavior, CAS atomicity, MPSC FIFO/linearizability requirements, and per-producer sequence accounting.

### 11.2 Run-level gates

Before each run, verify platform identity, build hash, affinity, actual CPUs, shared-cache relationship, producer-home shared-data pages, worker-local private buffers, hardware-prefetch state, clock, persistent arena identities, node/event address checksums, record immutability checksum, and arrival schedule checksum. Monitor memory-node residency or migration with a documented operating-system mechanism during the run and recheck it afterward. Then verify count equations, drain, producer/consumer index audits, node state, sample integrity, record checksum, disturbance thresholds, and manifest completeness.

Run disposition has independent fields for lifecycle, join status, run validity, count reconciliation, zero-loss status, effective-tail status, confirmatory estimability, and block completeness. A pre-run failure is validly represented by its manifest and failure evidence without producer, consumer, join, or integrity artifacts that never existed. A measurement or drain failure retains every artifact actually produced. A failed join has a failed join audit but no successful joined stream. A completed valid Stage A run must have complete counts, both raw stream envelopes, passed join audit, joined stream, provenance, and phase/integrity evidence. A correctness or measurement failure invalidates a run and makes the original block incomplete; a count-identity mismatch is a protocol failure; a correctly reconciled full return is an observed valid outcome; and `N_full > 0` separately fails the strict zero-loss regime. Genuine low `N_eff` is also retained and separately fails effective-tail estimability. Every record retains its primary category and warnings. Full and low-effective-count runs are neither discarded nor repeated and block dependent confirmation rather than being selectively removed.

## 12. Reproducibility requirements

The later implementation phase must preserve:

- source and build provenance sufficient to recreate the binary;
- immutable human-readable run manifests and a factor dictionary;
- exact randomization and arrival seeds;
- exact node-order and event-record-order seeds, index sequences, address-delta checksums, and persistent arena identities;
- complete topology and platform characterization;
- ordered producer and consumer raw observations, their accepted-ordinal join record, full/drop outcomes, and rolling-checksum/index audits;
- lifecycle-aware partial-run manifests; logical-row schema and physical-format record IDs; raw envelopes with encoding, time unit, endianness, compression, row/byte counts, ordering, URI, and SHA-256; and separate join-audit versus successful joined data;
- phase/integrity artifacts containing the final rolling checksum, pre/post event-record checksums, ordered-index checksum, address-delta checksum, and every checksum algorithm/version identifier;
- counter group records and unavailable-event notes;
- calibration, pilot, common Stage A block role, replacement-block lineage, diagnostic, and exploratory labels;
- checksums for manifests, schedules, raw observations, and derived tables;
- analysis provenance linking every derived value to run identifiers;
- all failures and replacements, not only accepted runs.

Reproduction material must state which hardware controls require privilege and which platform features could not be verified. No generic label such as “prefetch disabled” or “NUMA local” is accepted without the corresponding evidence record.

## 13. Planned result presentation

No plot contains synthetic or placeholder measurements. The later analysis phase must produce:

| Presentation | Independent variable | Response | Grouping/scale | Research use |
|---|---|---|---|---|
| Latency CCDF | end-to-end latency | exceedance probability | queue/PF policy; log time | distribution shape and tail diagnostics, RQ1 |
| Percentile–load curves | offered-load fraction | inverse-ECDF p50, p99, p99.9 with intervals plus full/drop rate | queue, HW, family SW; log latency | RQ1/RQ2 and zero-loss gate |
| Ring distance curves | off, one-line, latency-matched | paired log-p99.9 effect | placement and working set | useful arithmetic lookahead, RQ2 |
| Linked policy contrasts | off versus one-hop | paired log-p99.9 effect | HW, placement, working set, load | feasible linked treatment, RQ1/RQ2 |
| Interaction forest plot | 27 stable H1/H2 identifiers | log ratio and 95% max-T simultaneous interval | seven H1 and twenty H2 contrasts; equivalence band | practical and statistical decision |
| Occupancy/lateness/drop panel | load and treatment | occupancy, producer-lateness quantiles, full/drop count and rate | queue and placement | mediators, open-loop validity, and regime gate |
| Counter diagnostic panel | randomized PF contrast | normalized counter differences | demand, PF, stalls, coherence, NUMA | mechanism consistency only |
| Stage B contention curves | producer count/batch | p99.9, CAS failure, fairness | placement/load | exploratory contention |
| Held-out validation table | six fixed contexts and deterministically selected policy | selected-minus-candidate max-T upper intervals, zero-loss status, supplementary stability | platform | conditional RQ3 gate |

A final condition-to-policy decision table is allowed only if H3 passes its precision, zero-loss, completeness, and simultaneous-upper-bound gates. If it fails, the presentation reports the unresolved reason and heterogeneous effects without a recommendation.

## 14. Implementation readiness and stopping point

Protocol `2.0.0-pre.1` is detailed enough to guide architecture planning, but it is a pre-freeze draft and is not ready for pilot or confirmatory execution. Every mandatory item in `PROTOCOL_FREEZE_CHECKLIST.md` and the platform questions in `research/OPEN_QUESTIONS.md` must first be resolved. It does not authorize an experiment implementation in this repository task. The later coding phase must return for protocol review if it changes an algorithm, record immutability, logical row, physical format record after freeze, memory policy, timestamp or linearization boundary, workload/full semantics, factor level, quantile estimator, bootstrap rule, H3 selection rule, prospective precision rule, or correctness gate.
