# ADR-0212: Prospective Q16a demand-window membership

- Status: `PROPOSED` — affected formal implementation awaits owner acceptance
- Date: 2026-11-03
- Amendment ID: `AMEND-2.0.0-pre.3-Q16A-DEMAND-WINDOW-v1`
- Proposed method ID: `RING-D2-RUNTAIL-LTL95C95-WINDOW-v2`
- Scope: fresh formal EXT007 Q16a captures only
- Supersedes: D037 v1 only for this prospective formal capture population; historical artifacts remain unchanged
- Immutable protocol: `protocol/2.0.0-pre.3/` remains unchanged
- Execution authority: none; no new collection, qualification, retry or extension

## Missing decision and alternatives

[D037](0037-stage13-ring-distance-calibration.md) and the
[accepted calibration bundle](../STAGE13_CALIBRATION_DECISION_BUNDLE.md)
define the acquire-load bracket, advancing-demand issue intervals, exact
quantiles and run-level extremes. They require a prospective duration but do
not define demand membership at its endpoint or whether drain demands and
issue pairs crossing that endpoint enter those four sequences.

[Specification](../../protocol/2.0.0-pre.3/EXPERIMENT_IMPLEMENTATION_SPEC.md)
section 5.5 requires consumer drain. Section 8.1's inclusion of accepted-event
latencies completed during drain is defined by scheduled arrival time; it
does not determine membership for FULL/empty acquire demands or demand-start
pairs. D207 is diagnostic-only and cannot silently supply a formal rule.

Counting all demands through drain and counting only demands beginning in
the fixed measurement interval produce different statistical populations.
Requiring both bracket endpoints inside the interval also differs from
including a demand that begins before the end and finishes after it.
These are scientific choices. D037 requires a new method identity for a
boundary change; this proposal therefore names a versioned successor.

## Proposed rule

Use independent, continuously ready ring-off workers with the same immutable
record action and acquire/release mapping. After the required five-second
bootstrap warmup, drain, parked logical reset and start barrier, let `t0`
be the actual released measurement origin and `T > 0` the prospectively
frozen duration, in the accepted exact integer clock domain.

The producer stops initiating new attempts when its clock reaches `t0+T`.
The consumer continues normally, without an intermediate park, until it
observes producer completion and an empty queue under the accepted drain
protocol. Frozen resource and drain limits remain mandatory failure gates.

For each worker separately:

1. Retain every acquire-demand bracket and actual outcome through the end
   of drain, including FULL and empty attempts, with run identity, worker,
   attempt ordinal, start/end clock samples and advancement identity.
2. A demand enters the latency sequence exactly when its immediately-before-
   acquire timestamp `s` satisfies `t0 <= s < t0+T`. Include the complete
   bracket latency even if its immediately-after timestamp reaches or
   exceeds the endpoint. A demand starting exactly at `t0` is included;
   a demand starting exactly at `t0+T` is excluded.
   The loop's earlier deadline check, event arrival, dequeue completion and
   consumer-action completion do not substitute for this demand-start time.
3. Form the issue sequence from successive advancing demands in that same
   eligible window: producer ACCEPTED, consumer successful dequeue. Include
   their demand-start difference only when both adjacent advancing demands
   are eligible. FULL/empty attempts do not advance or break the succession.
   Never bridge warmup or the measurement-to-drain endpoint. Thus `k`
   eligible advancing demands supply `max(k-1, 0)` issue observations.
4. Perform membership selection and summary calculation after collection.
   Retain all excluded drain observations and all primary streams for
   reconciliation; do not discard malformed observations as out of window.
   Validate clock-domain conversions, ordering, actual origin, duration and
   checked endpoint arithmetic independently from original raw evidence.
   A measurement-phase demand beginning before the released origin is a
   barrier/clock inconsistency and invalidates the run; it is not an eligible
   observation that may merely be excluded.

Preserve D037's existing per-sequence validity and minimum-count checks,
noninterpolated p99.9/p0.1 ranks, at least 59 valid independent runs per
state/context from a fixed prospective plan, conservative H0/H1 and worker
merge, checked distance arithmetic and capacity cap. Positivity and minimum
counts apply to the four eligible sequences. A clock tie in an excluded drain
demand does not, by itself, make an eligible sequence nonpositive; clock,
ordering, raw-integrity and reconciliation checks still cover every retained
observation. Do not silently remove zero/nonpositive or otherwise invalid
eligible observations, top up an insufficient
family, repeat an unfavorable run, or tune duration using its quantiles.
FULL remains retained data and a separate zero-loss failure.

The accepted D207 study still contributes zero formal runs. Its count-only
selection may supply the prospective common duration, but it does not prove
that every fresh formal run meets this successor's four minimum counts.
Each formal run must satisfy those checks independently.

## Acceptance and verification boundary

This proposal chooses no actual duration, buffer capacity, seed, namespace,
recovery interval, storage budget or execution deadline. Those must be
explicitly frozen in the later formal plan using qualified source and
verified stand resources. No current D207 input, binary or output changes.

After exact owner acceptance, implement versioned native trace, output,
independent decoder, estimator-method and admission contracts. Verify exact
start/end ties, brackets crossing the end, empty/FULL attempts, advancing
pairs crossing the endpoint, retained drain, insufficient and nonpositive
series, clock failures, overflow, actual persistent warmup/reset and bounded
termination. Require the relevant sanitizers and generated-code gates before
any later qualification or formal execution authorization.
