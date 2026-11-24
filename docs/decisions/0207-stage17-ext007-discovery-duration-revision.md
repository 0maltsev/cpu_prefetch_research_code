# ADR-0207: Prospective discovery duration revision after R2 monitoring failure

- Status: `ACCEPTED` — explicit owner approval recorded on 2026-11-03
- Date: 2026-11-03
- Amendment ID: `AMEND-2.0.0-pre.3-EXT007-DISCOVERY-DURATION-v2`
- Scope: EXT007 diagnostic duration discovery only
- Supersedes on acceptance: D-178's candidate durations, and R2's measurement
  attempt capacities and resource ceilings for a new prospective family only
- Protocol: `2.0.0-pre.3/` remains immutable; this versioned amendment records
  the proposed change separately. D-037's formal method remains unchanged.

## Evidence and reason

The retained R2 family stopped at capture 9. Mandatory region-5 monitoring
started 25.005774 ms into its 100 ms measurement, took 163.531831 ms, and ended
after both workers reached their fixed deadlines. Independent validation
reconciles warmup and measurement raw events, but full-capture validation
rejects the mandatory session stop. The combined observation does not isolate
which syscall or file dominates its cost.

See the [stand-side diagnosis and phase validation](../evidence/stage17/STAND-CUSTODY-D206-20261103-01/README.md).
R1 and R2 remain failed diagnostic families. Their authority is consumed;
neither their successful prefixes nor their counts select a formal duration.

## Proposed scientific decision

1. Enumerate one new family of **36 captures**: all 12 existing H0/H1 ×
   near/far × working-set contexts, each at **1 s, 2 s and 5 s**, in that
   prospective order. Preserve the existing context ordering. No 100 ms
   capture is included. These are requested controls, not measured hardware
   properties or a guarantee that monitoring fits.
2. Retain 5 s warmup and the accepted full-footprint capacities
   512 / 65,536 / 1,048,576 under the accepted nominal-cache interpretation.
   Freeze **30,000,000 attempts per worker for each phase**, including every
   measurement duration. Keep bounded drain, verified reset, fresh phase
   origins, and fixed time termination. Preserve the existing distinction:
   exhausting warmup capacity is a mandatory session failure; measurement
   `TRACE_CAPACITY` is retained as insufficient and does not alone become a
   mandatory study failure. Neither permits extension, resize or retry.
3. Retain all 86 monitoring sources and all six required observation groups,
   including the existing before/during/after checks. During observations
   start at 2.5 s of warmup and one quarter of the measurement duration.
   Preserve the existing page coverage, hardware, clock, fault, residency,
   integrity and restoration gates. Do not omit monitoring to make a short
   candidate pass.
4. Retain D-178's count-only selection: at least **100,000 observations in
   each of four sequences**, independently counted, in every required context;
   select the shortest common candidate satisfying every frozen gate. No
   quantile, treatment-effect, package or candidate comparison enters the
   selection. A complete valid family is required; if none qualifies, leave
   selection unresolved. No adaptive top-up, favorable-prefix selection,
   retrospective duration change, or automatic retry.
5. Use fresh identities, seeds, action/output namespaces and an explicit
   history-collision audit. All data remain diagnostic-only. Formal Q16a's
   708 captures and Q16b/Q16c require their own prospective plans and gates.
6. Apply accepted D206 custody: one authoritative uncompressed raw copy on
   the stand, analysis on the stand, small reports and provenance on the PC.
   Preserve failed raw evidence. Do not require a PC raw-data transfer.

## Prospective resource ceilings

The [resource report](../evidence/stage17/DISCOVERY-D207-PROPOSAL-20261103-01/resource-report.json)
is arithmetic preparation, not an executable plan or stand measurement.
Its hash is `99048602c37ae150d0a186f73bd266ac4dceab1a3d169a7ceb85247f999c7b22`.
It reuses 24 local cold layout queries covering the six geometries at 1 s
and 5 s with the proposed buffers. The intermediate 2 s allocation is derived
from the unchanged allocation formula; the current parser rejects 2 s.
The qualified successor must verify all exact layouts before admission.

| Resource | Proposed ceiling / modeled requirement |
|---|---:|
| Worker address-space limit | 224 GiB |
| Worker memlock limit | 24 GiB |
| Maximum native mapping model | 16,916,905,984 bytes |
| Maximum active allocation model | 66,362,623,488 bytes |
| Controller allowance / stand memory reserve | 2 GiB / 16 GiB |
| Required available memory using full limits and reserve | 259,845,521,408 bytes |
| Raw output upper bound, 36 captures | 570,240,000,000 bytes |
| Metadata budget | 66,012,398,632 bytes |
| Total output budget | 636,252,398,632 bytes |
| Maximum temporary drain spool | 3,485,469,950 bytes |
| Additional free-disk reserve | 16 GiB |
| Required free stand space, one copy plus spool and reserve | 656,917,737,766 bytes |
| Capture watchdogs for 1 / 2 / 5 s | 2,106 / 2,107 / 2,110 seconds |
| Whole-family watchdog | 76,116 seconds (21 h 8 min 36 s) |

The watchdog includes 1,800 s publication allowance per capture and is a
maximum, not an expected runtime. Fixed warmup/measurement time totals only
276 s; preparation, monitoring, drain, publication and validation add time.
The approximately 7.15 TB previous free-space observation fits the disk model.
Memory and disk availability must be refreshed before admission; historical
availability is not a reservation. Allocation models do not prove peak RSS,
allocator retention, successful locking, or monitoring latency. If any exact
successor layout or required budget exceeds these bounds, stop before running
and amend the prospective plan; do not silently increase it.

## Implementation and qualification before collection

Acceptance permits the necessary versioned implementation: discovery design
and selector, schemas/contracts, native parsing, controller/admission and
retained validation dispatch, and a source-bound policy/release successor.
Preserve old contracts and failed evidence under their original versions;
do not reinterpret R2 with the new grid. Keep 36-capture structure and context
indexing. The measurement loop need not acquire new monitoring or analysis work.

Use targeted regression and rejection cases, relevant sanitizer suites,
required release/codegen/schema/policy checks, a clean local source commit,
and verified local/stand bundle hashes. Freeze exact layouts, source/worker
hashes, inputs, scripts, namespaces and finite signed authority before running.
Existing general permission to commit locally and author authorized owner
records persists; no push is proposed. A proposal or conversational approval
never substitutes for the exact operational admission record.

## Proposed finite execution scope upon acceptance

This section is inactive until the owner accepts this proposal. Acceptance
would authorize the following bounded sequence, conditional on every gate:

1. Prepare and qualify only the successor needed for this amendment. Verify
   boot/topology and original control prestate before any stand mutation.
   Reapply the same CPU isolation: reserve 0/1/2/8/16/17/18/24, nodes 0/1;
   verify effective/exclusive partition controls. Do not change governor,
   turbo, IRQ routing, boot settings or clock source.
2. If successor qualification requires fresh clocks, allow **at most one
   near 0/1 invocation and then one far 0/8 invocation only if near passes**.
   Retain the [v2 numerical controls](../STAGE17_CLOCK_REQUALIFICATION_PLAN_V2.md):
   100,000 prime reads, 10,000,000 deltas per CPU, three windows of 100,000
   exchanges per direction, prescribed span, p99.9 ≤ 1 us and p99.999 ≤ 10 us,
   all other gates, 8 GiB address space, 8 MiB memlock, 600 s per invocation.
   Use fresh exact successor-bound records and retain these small clock
   artifacts on stand and PC. This is new finite authority, not reuse of the
   consumed v2 allowance. A failed near invocation precludes far and discovery.
3. If fresh Q15 qualification is required, allow at most one read action and
   one write action, using the already approved controls and fresh finite
   signed records. Require each prerequisite to pass before its dependent
   action. Stop on the first qualification failure, restore and verify the
   prestate, and do not retry under a new request. Discovery requires all
   qualification gates to pass.
4. After all release, readiness, resource, identity and signing checks pass,
   execute the new 36-capture diagnostic family **once**. Stop at the first
   mandatory failure, retain the partial evidence, and restore/verify the
   recorded prestate; quarantine if restoration cannot be proved. No second
   family, extra capture, clock retry or drift substitution is authorized.
5. Analyze the retained family on the stand and report either a valid
   count-only duration selection or explicit unresolved status. Report each
   completed roadmap state. This grants no formal calibration, pilot or
   Stage 18 invocation and makes no EXT007 completion claim.

## Acceptance

The owner replied **“i approve”** to the D207 proposal and its finite execution
scope. The [original proposal and exact acceptance](../evidence/stage17/DISCOVERY-D207-ACCEPTANCE-20261103-01/owner-acceptance.json)
are retained separately. Original proposal SHA-256:
`a1accac3f8683a74a5744c676da907666b95a7b908fe725b0fca2725c8a2e559`.
This accepts the decision and conditional finite scope above; all exact
release, qualification, resource and signed admission gates remain required.
