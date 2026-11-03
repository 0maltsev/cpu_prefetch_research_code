# ADR-0217: Explicit prospective formal native input

- Status: `ACCEPTED` — engineering implementation of D210–D212
- Date: 2026-11-03
- Scope: new formal capture input; historical contracts remain unchanged
- Execution authority: none

Formal Q16a must not enter the historical fixed-sample alternating handshake
or the diagnostic-only D207 lifecycle. Introduce a separate cold parser and
`cpu-prefetch-stage17-formal-ring-capture/1`, structurally described with its
resources and monitoring by `stage17-formal-ring-native-input-v1.schema.json`.
It requires D212's method identity and the R0 package explicitly.

The capture carries a context and repetition ordinal, the hardware state,
placement and working-set class, explicit geometry, five-second warmup and a
positive prospective measurement duration and minimum observations per series.
Each phase has explicit producer-attempt and consumer-poll watchdog limits and
drain duration. Each of its four primary/demand streams has an explicit row
capacity. No diagnostic count, duration, empirical rate or processor number is
an implicit formal default. The common native layout checks that capacities
cover the declared bounds. A necessary bound on the required issue count is
checked before mapping; it does not predict actual eligible observations.

Warmup and measurement retain distinct run IDs, seed IDs, namespaces and seed
values. The arena uses the exact measurement seed and namespace throughout;
warmup's reserved identity makes no extra arena draws. Both identities are
preserved in the input for later reservation and primary-stream reconciliation.
The parser rejects context/geometry contradictions and worker/controller CPU
collisions, without inventing a particular platform's CPU or NUMA node numbers.

Resource and monitoring records bind the same capture ordinal. The typed
native layout recalculates sizes using this binary; serialized sizes are
checked assertions, never an instruction to allocate arbitrary object memory.
The pure layout-description entry point permits placeholder declared sizes
but still applies the explicit memory ceiling. It creates no mappings and
accesses no hardware. Paths and prestate remain borrowed until the synchronous
native invocation returns.

This boundary validates one capture. The versioned family validator must still
bind the approved plan hash, complete context/repetition coverage, seed ledger,
fresh identities, qualified release and hardware evidence, finite family and
per-capture deadlines, resources, retention and explicit phase authority.
Successful parsing or prospective sizing grants none of those independently.

Targeted tests cover exact conversion, context and seed changes, wrong methods,
missing or extra fields, integer overflow, insufficient stream/watchdog bounds,
memory ceilings, stale layout declarations and actual platform CPU geometry.
Native execution and publication require separate integration verification.

The corresponding cold publisher retains eight unfiltered raw files: producer
and consumer primary and demand streams for both phases. A ninth control file
binds their exact bytes, independent stream identities/completeness, current
capture failures, native phase origins/windows, mappings, TLS, hardware,
environment and counters. A missing phase owner has an empty artifact and
explicit absent snapshot, never a fabricated successful observation. The D212
per-stream contract is embedded only when its actual clock origin and phase
window exist. Its minimum comes from the prospective input; warmup's is null.

Fourteen unchanged cold observation fields share an internal serialization
helper with the historical discovery publisher. Historical discovery shapes,
raw formats and public APIs remain unchanged. Targeted regression tests cover
both publishers. Formal publication performs no window filtering, quantile
calculation, acceptance or inference. Prior artifacts survive any sink failure;
publication is not retried. The control document precedes final unmapping and
stack cleanup; the returned native result is separately serialized after those
operations. A successful publication never substitutes for successful cleanup.

The layout ceiling bounds mappings only. A prospective process and retention
budget must additionally include the largest single raw publication copy,
JSON tree/canonical text/output copy, hashing and analysis scratch, stacks,
guard pages and other runtime extents. The mapping parser does not claim that
this larger budget has been admitted.
