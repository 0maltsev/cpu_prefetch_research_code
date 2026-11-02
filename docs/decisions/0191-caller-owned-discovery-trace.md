# ADR-0191: Keep discovery demand traces in caller-owned worker storage

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-191
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: storage preparation and integration seams for the live diagnostic backend

The vector-backed trace reserves storage on the controller's general heap.
Owner prefaulting alone cannot establish dedicated worker-local mappings for
both samples and mutable trace metadata. Add caller-owned typed sample spans
and independently stored worker state, with a facade that validates all six
address ranges for overlap and overflow before buffer preparation. The caller
must construct and prepare each state on its worker, preserve object lifetimes,
and separately verify actual mapping residency. Construction is no residency
proof or execution authority.

Preserve the accepted demand and advancing-issue definitions: retain every
successful demand bracket including FULL/empty; form an issue interval only
between successive advancing demand starts. Keep finite capacity, partial
evidence, wrong-role rejection, and no allocation or I/O during capture.
Zero intervals remain retained and fail the existing later validity checks.
Preparation touches every supplied sample element once on its owner and may
not be repeated after capture starts. No silent growth or top-up is allowed.

Use an own-worker view of samples and nonadvancing count in the prepared
worker and quiescent validation helpers. It must never copy a peer's mutable
counts while that peer is active. Generalize the existing producer demand
observer and discovery consumer helper over this trace interface; preserve
the exact queue acquire and clock brackets. Leave the legacy formal consumer
helper and old sample-count execution path unchanged.

Verify parity with the existing trace on deterministic sequences, independent
counts, rejection without sample mutation, capacity and preparation guards,
real queue/event/checksum capture, and concurrent worker recording under the
supported sanitizers. Qualify the final backend and a new source policy before
any diagnostic execution. No duration, estimator, capacity, warmup, or resource
budget is selected by this engineering decision.
