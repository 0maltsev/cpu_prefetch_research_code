# ADR-0197: Retain prospective discovery residency observations

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-197
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: controller-side R0 diagnostic monitoring, not run admission

Compose D-192's prepared page queries with D-196's controller hooks. Callers
provide the complete declared worker-region inventory, expected nodes, verified
page size, finite polling budget and ordered observation requests. Callers own
all descriptors, query objects, address/status scratch and output rows. Expose
the prepared query's immutable page-address view without changing its layout or
sampling implementation. Freeze the plan and lifetimes before capture.

Require exhaustive before/after queries for every declared region in both
warmup and measurement, and at least one explicit during request per region
and phase. During queries may cover declared contiguous page subranges; retain
the exact queried addresses and do not infer complete-region residency from a
partial sample. This is not approval of any particular coverage, schedule,
numeric resource budget or operating-system control mechanism. Live admission
must bind the actual complete footprint, appropriate coverage/schedule and all
other mandatory controls before the study. Do not silently adopt a default
schedule or choose one from observed tails or treatment effects.

Validate whole-page geometry, node representability, exact prepared addresses,
coverage, finite in-horizon offsets and request ordering. Reject duplicated or
reused rows and aliased status snapshots. Immutable address scratch may be
shared; each retained status vector is distinct. Keep controller observer,
descriptors, output and query scratch outside worker target regions, without
touching queue ownership/data bytes. Reject query scratch that can overwrite
another query's metadata. Validation performs no observation or output reset.

Record actual query return/errno, page status vectors, start/end clock results,
wait first/last clocks and poll counts, and the observed completion mask around
during queries. Unread clocks and unattempted queries remain absent. Retain
clock failures/regression witnesses, wrong nodes, page errors and partial
writes; D-192 resets query status before each call so earlier success cannot
leak into a later snapshot. Keep earlier/later independent snapshots unchanged
after failure. Queries are not instantaneous observations; their brackets are
part of the evidence.

Use the actual released origin/duration supplied by the session. Before querying
during capture, wait only to the registered offset within the finite polling
budget. Reject clocks outside the horizon, exhausted waits, or worker completion
observed before/during the query. A query ending at/after the phase deadline is
retained invalid evidence, never relabeled as a during observation. A duplicate
or out-of-order hook is rejected without rewriting earlier evidence. After a
failed during hook, the session can still obtain separate quiescent observations
and bounded drain; it cannot reset/release measurement or report valid completion
contrary to D-196. No retry, top-up or duration extension is introduced.

Verify independent retained snapshots, explicit partial coverage, complete
declared-region coverage, malformed/aliased/reused requests, raw syscall/page
failure, clock failure/regression, missed deadlines, finite waits and worker
completion. Compose a rejected real page observation with the actual
arena/ring/primary-stream session and require zero queue attempts before failed
initial readback. Check controller hooks allocate nothing after preparation;
run relevant sanitizer/compiler checks. These software tests use injected page
results and do not establish stand residency or qualify the clock boundaries.

Complete mapped owner object/stack preparation, actual retained platform facts,
durable publication, watchdog, source-bound admission/release and fresh dependent
qualification remain prerequisites. This decision changes neither D-178's study
nor D-037's estimator or formal collection requirements.
