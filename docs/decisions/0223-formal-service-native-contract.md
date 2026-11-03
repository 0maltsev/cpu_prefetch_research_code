# ADR-0223: Typed formal service input and original evidence publication

- Status: `ACCEPTED` — engineering implementation of D035/D210/D211
- Date: 2026-11-03
- Scope: Q16b native input and publication; no experiment authority

Introduce a separate `cpu-prefetch-stage17-formal-service-capture/1` input
for the five admitted packages. Its sixty cell ordinals bind package, hardware
state, placement and working-set class. All phase durations, watchdog counts,
primary capacities, geometry, seed identities, monitoring and memory ceilings
are explicit. Actual five-second continuous-service warmup, persistent workers,
drain/reset and measurement use D210; D211 determines the cold completion count.

R0 has no distance or linked order. R1 requires the registered one-line distance
and an empty calibration-evidence ID. R2 requires an explicit distance and an
accepted-prior-evidence reference, whose admission remains an outer gate.
L0/L1 require an explicit deterministic linked-order seed/namespace and arena
alignment, with no ring distance. The native layout enforces these alternatives
and the accepted model-specific software-prefetch mapping. Package/emitter
dispatch occurs before capture; no package branch enters an event loop.

The Q16a and Q16b cold parsers share only identical field/type, identity,
owner-control and declared-layout checks in a private helper header. They
retain separate method identities, exact field sets and native typed plans;
neither relabels another action to reuse its scientific checks.

The cold service publisher retains four original primary streams, the explicit
linked node order as unsigned little-endian u64 values (empty for ring), and
one control document. It preserves missing owners, incomplete prefixes, exact
current timing-capture failures and unknown observations without fabricating
operation outcomes. Warmup and measurement remain separate. The measurement
completion-interval result retains its actual clock window, interval count,
outside count and full drain total; failed or absent results remain explicit.
Independent validation must join the original streams and recompute D211.
Publication itself establishes neither scientific validity nor final cleanup.

The immutable specification section 2 and run-manifest schema require a
joined-derived dataset for completed valid `STAGE_A` latency runs. D035's
`CALIBRATION` service-rate runs do not impose that dataset requirement; original
primary streams, exact join audit, integrity/provenance and independently checked
counts suffice. Section 8.4 still requires an audit for every attempted join.
The later analysis/admission artifact set must include that audit and bindings;
the native publisher does not alone complete the set. This decision creates
no exception for Stage A latency runs or another contract that requires a
joined-derived artifact.

Tests cover all sixty package/context combinations, both phase bounds, wrong
prefetch mappings, missing or incompatible linked/distance inputs, phase
identity reuse, stale layouts, capacity/window failures, all four raw payloads,
node-order bytes, separate interval/drain counts, missing owners, failure
retention and final cleanup. Existing Q16a and discovery publication regressions,
strict checks and relevant sanitizers remain required before qualification.
