# ADR-0014: C++ atomic and memory-order envelope

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Concurrency correctness / claim boundary
- Decision owners: Repository owner; queue correctness owner; platform owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 envelope; exact representation/proof due in Phase 5

## Context and scientific constraints

The protocol declares release/acquire pointer publication/reuse and termination relations. It permits relaxed operations only where single-writer ownership and a written proof justify them. Required atomics must actually be lock-free on the eligible build/platform, and layout cannot invent a cache-line size.

## Options considered

1. C++ `std::atomic` with the protocol release/acquire mapping.
2. Compiler/platform intrinsics.
3. Stronger sequential consistency.
4. Locks or hidden fallback synchronization.

## Decision

Use `std::atomic` pointer/control handoffs. Map the protocol's slot, link, recycler, and termination publication/observation to release stores and acquire loads; use relaxed operations only for proven thread-owned state. Pointer atomic width equals the selected ABI pointer width. The exact termination/control atomic type and width remain a Phase 5 representation decision. Align/separate ownership using verified platform line size, never a fabricated constant. Reject builds/platforms that fail compile-time and runtime required-atomic lock-free probes.

Claims are limited to the reviewed Stage A SPSC try operations and fixed-arena recycler. No broader lock-free/wait-free claim follows from this ADR.

## Evidence

The repository owner accepted Q2 on 2026-08-17. The C++ atomic model expresses the required order while defining lock freedom as implementation-dependent, which justifies mandatory target probes.

## Consequences and compatibility

Scientific effect: realizes the fixed order; weaker/alternative orders are not permitted Stage A choices. Compatibility effect: an otherwise supported target is ineligible if atomics/layout cannot satisfy the proof and probe gates.

## Verification and acceptance tests

Phase 5 requires a written happens-before/refinement argument, compile/runtime lock-free evidence, layout assertions/reports, deterministic histories, sanitizer/stress evidence, and generated-code inspection for every package/build.

## Rollback or supersession

Representation or order changes require a superseding ADR and renewed proofs/tests. A scientific memory-order change belongs to separately authorized Stage C or a protocol amendment.

## Protocol-amendment assessment

No amendment is required for this mapping envelope.
