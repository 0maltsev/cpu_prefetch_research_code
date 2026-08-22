# Stage 17 entry implementation decision bundle

Status: **AWAITING Q13 OWNER ACCEPTANCE; PILOT PROHIBITED**

Date: 2026-08-22

Protocol: `2.0.0-pre.2`

Affected decisions: D-006, D-008, D-009, D-015, D-018, D-019, D-020, D-034

Owners: repository, platform, controller, timing, queue-correctness, storage,
security, and custody owners

This bundle proposes only the smallest choices needed to continue production
path implementation. Acceptance would not authorize privileged controls,
calibration, Stage 17 pilot execution, or confirmatory work. Items in the
unresolved section cannot be accepted by approving this bundle.

## Evidence boundary

The clean stand bundle
`cpu-prefetch-stand-bundle-2.0.0-1b0a7f5-clean-32ab349ee5e2.tar.gz`
has SHA-256
`e8eb9150d252d38f72b56884b0bcb5026480aee00b969c736fdc124783cb6eac`.
It passed its external hash, 72-file internal manifest, smoke binary, and
preflight self-test on the candidate stand. The current clean inventory is
[`STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02`](evidence/stage16/STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02/README.md).

The independent topology set
[`STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01`](evidence/stage16/STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01/README.md)
proves the static CPU relationships used below. The read-only storage set
[`STAND-STORAGE-XEON-CPU-FETCH-20260822-01`](evidence/stage16/STAND-STORAGE-XEON-CPU-FETCH-20260822-01/README.md)
proves that only one suitable mounted durable namespace is presently visible.
No outcome, performance comparison, calibration, platform mutation, or pilot
record informed these recommendations.

## Q13-A: exact candidate worker pairs

| Field | Classification | Options considered | Recommended selection | Evidence | Scientific effect | Compatibility effect | Owner | Deadline/gate | Supersession |
|---|---|---|---|---|---|---|---|---|---|
| Near/far pair | Platform placement | `(0,1)` near and `(0,26)` far; reverse the producer home to package 1; choose other eligible cores; leave unselected | Producer CPU 0 for both placements; near consumer CPU 1; far consumer CPU 26 | Direct sysfs and complete `lscpu` topology in the hashed topology set | Fixes which physical transfer contexts the placement factors mean; does not claim a latency property | Bound to this stand identity, topology, online set, release, and later qualifications | Repository and platform owners | Accept before pair-specific clock/control/runner qualification | New prospective pair record; re-run all pair-bound qualification and preserve old evidence |

The recommended pair keeps the producer and producer-home memory node fixed at
CPU/node 0 while changing only the consumer placement. CPU 0 and CPU 1 are
different non-SMT cores in NUMA/package/LLC domain 0. CPU 26 is in NUMA/package/
LLC domain 1 and is not CPU 0's sibling. Runtime actual-CPU and residency
readback remain mandatory; this static selection is not qualification.

## Q13-B: processor-relax mapping

| Field | Classification | Options considered | Recommended selection | Evidence | Scientific effect | Compatibility effect | Owner | Deadline/gate | Supersession |
|---|---|---|---|---|---|---|---|---|---|
| Producer/consumer relax | Measured-path platform mapping | no instruction/compiler barrier; x86 `PAUSE`; scheduler yield/sleep; adaptive backoff | One `_mm_pause()` at every protocol relax site, compiling to one `F3 90` `PAUSE`; no other wait call or adaptive count | Imported tight-poll rule; Intel x86 instruction and spin-loop guidance | Adds the same finite architectural hint after each not-due/empty poll; changes no queue operation, timestamp, deadline, or retry rule | Mapping ID and exact generated instruction become release identity | Controller, platform, and code-generation owners | Accept before production worker implementation; audit every release specialization | New mapping ID, superseding ADR, and full worker/codegen requalification |

Intel documents `PAUSE` as the x86 spin-loop hint and recommends it in tight
spin loops. The authoritative references are the current
[Intel SDM catalog](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
and the [PAUSE instruction reference](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2b-manual.pdf).
Approval selects an instruction prospectively, not because of observed speed.

## Q13-C: fail-closed production-runner profile

| Field | Classification | Options considered | Recommended selection | Evidence | Scientific effect | Compatibility effect | Owner | Deadline/gate | Supersession |
|---|---|---|---|---|---|---|---|---|---|
| Production path | Engineering integration | generic runtime-dispatch harness; duplicate per-package executables; one controller with five statically bound worker specializations; postpone all integration | One unprivileged controller executable with five compile-time package specializations and no measured-loop package dispatch | ADR-0001/0012/0031; existing queue, workload, timing, lifecycle, and storage seams | Preserves one-attempt admission, polling, timestamp, load/checksum, and private-stream semantics | Runner profile, required input contract, binary hash, specialization hashes, and codegen report are release identity | Repository, controller, queue, timing, storage, and build owners | Implement after Q13 acceptance; full clean/sanitizer/codegen pass before pilot | Superseding ADR and complete production-path requalification |

The runner must parse, allocate, initialize, validate, and open artifact targets
before worker release. Its timed specializations may call only the already
accepted clock, schedule lookup, record lookup, package operation, fixed-row
append, checksum action, termination, and selected relax operations. It must
refuse to arm measurement unless all external records are explicit, immutable,
hash-bound, current, and eligible. There are no default CPUs, nodes, limits,
capacities, distances, schedules, seeds, hardware states, storage paths, or
authorities. Finalization and reconciliation remain post-run. A buildable
executable that refuses incomplete inputs is not pilot authority.

## Unresolved inputs that remain hard blockers

These items need external authority or additional controlled evidence. This
bundle does not fill them:

1. **Watchdog/failure bounds.** All five `ExecutionLimits` values need an exact
   prospective record and justification from the controller/platform owners.
   Poll counts cannot be inferred from development tests or CPU frequency.
2. **Hardware-prefetch treatment.** The current Intel Volume 4 model table for
   CPUID model `06_55H` does not establish a safe experiment-specific
   `MSR_MISC_FEATURE_CONTROL` mapping. No MSR address, mask, write, or state
   label is accepted. Exact platform documentation, H0/H1 definition,
   per-core scope, whitelist, pre-state/readback, independent behavioral
   probes, and rollback are required.
3. **Named least-privilege authorities.** Root SSH permission is transfer and
   read-only collection authority, not the D-015/D-019 platform-control or
   validation-custody boundary. Named operator/controller/custodian/auditor
   principals and negative-access evidence remain absent.
4. **Clock qualification.** The accepted 10,000,000-call traced-vDSO and
   selected-pair three-window bidirectional evidence has not run. A dedicated
   qualification executable/artifact path must be implemented and audited
   after pair acceptance.
5. **Memory and storage.** Before/during/after page residency, exact run-buffer
   capacity, a second independent durable domain, custody/permissions, reserve,
   crash recovery, and hash readback are absent.
6. **Pilot inputs and authority.** Exact calibration/pilot durations, planned
   counts, capacities, seed namespaces/values, schedules, storage and stand
   budgets, environmental limits, access plan, and explicit Stage 17 execution
   authorization remain absent.

## Acceptance meaning and exact reply

If the three recommendations are acceptable, reply exactly:

```text
Q13 - accept the Stage 17 entry implementation bundle: select near producer/consumer CPUs 0/1 and far CPUs 0/26, select one x86 PAUSE per relax site, and authorize implementation of the fail-closed statically specialized production runner only. This does not authorize privileged controls, calibration, pilot, or confirmatory execution.
```

After Q13, the next safe implementation work is the runner, relax generated-code
probe, selected-pair qualification tooling, and exact input validators. Stage
17 remains prohibited until every unresolved item above has its own accepted,
hashed evidence and a separate pilot authorization.
