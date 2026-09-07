# ADR-0030: Stage 8 clock and timestamp-boundary suite

- Status: `ACCEPTED`
- Date: 2026-08-20
- Classification: Timing / platform mapping / measured-path instrumentation
- Decision owners: Repository owner; timing owner; platform owner; queue-correctness owner; code-generation reviewer
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Q7 accepted before Stage 8 implementation; implementation and qualification evidence remain required

## Context and scientific constraints

The protocol fixes exact producer and consumer timestamp meanings and equations
but leaves the platform clock, conversion, serialization, overhead rule,
linearization-boundary mapping, and acceptance limits open. The accepted Stage
7 schedule uses picoseconds as a representation unit and explicitly delegates
clock qualification to Stage 8.

The published stand archive establishes a bare-metal dual-socket Intel x86-64
platform, kernel TSC clocksource, invariant/constant/nonstop TSC capabilities,
and `CLOCK_MONOTONIC_RAW` availability. It does not prove direct cross-socket
TSC synchronization or qualify any source.

## Options considered

1. Direct invariant TSC with `RDTSCP`.
2. Linux `CLOCK_MONOTONIC_RAW` through the x86-64 vDSO.
3. Adjusted `CLOCK_MONOTONIC`.
4. A `clock_gettime` syscall fallback.
5. Another separately proved HPET, ACPI PM, or PTP source.

## Decision

Select option 2 and the exact suite
`LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1`, boundary policy
`TIMESTAMP-BOUNDARIES-BRACKETED-LMRV1`, qualification policy
`CLOCK-QUAL-LMRV1`, and overhead policy
`CLOCK-OVERHEAD-UNCORRECTED-v1`, all exactly as specified in
[`docs/STAGE8_CLOCK_DECISION_BUNDLE.md`](../STAGE8_CLOCK_DECISION_BUNDLE.md).

The production reader uses `clock_gettime(CLOCK_MONOTONIC_RAW)`, proves vDSO
rather than syscall execution, surrounds the call with compiler-only
`atomic_signal_fence` boundaries, and converts returned integer nanoseconds to
relative picoseconds by exact multiplication by 1000. It adds no hardware fence
or direct TSC instruction to the wrapper and does not change queue C++ memory
orders.

Successful enqueue publication is bracketed by a final clock read immediately
before its release store; successful dequeue observation is bracketed by the
first read immediately after its acquire observation. All other protocol
boundaries use the exact points in the bundle. Raw values are primary and no
overhead correction is applied.

The bundle's exact static, per-core, cross-core, read-cost, drift, migration,
generated-code, identity, failure, and supersession gates are part of this
decision. No worker CPU placement is selected or inferred.

## Evidence

- Protocol implementation specification Sections 5.4, 5.5, 8.1, and 8.2;
  timestamp data dictionary; protocol freeze checklist.
- ADR-0003, ADR-0008, ADR-0012, ADR-0014, ADR-0016, ADR-0018, ADR-0024, and
  ADR-0029.
- Published Stage 8 capability archive and verified SHA-256/internal manifest.
- Repository-owner acceptance `Q7 - accept the bundle` on 2026-08-20.
- Official Linux clock, vDSO, clocksource, and x86 timekeeping documentation;
  Intel architecture manuals; C++ compiler-only fence specification.
- Stage 8 implementation evidence in [`docs/TIMING.md`](../TIMING.md): checked
  conversion/boundary/equation/failure/qualification tests and strict
  GCC/Clang release GNU+LLVM source/disassembly audits with required mutants.

## Consequences and compatibility

Scientific effect: timestamps have nanosecond sampling granularity represented
exactly as picoseconds; queue handoff timestamps bracket the linearization
operations and retain instrumentation cost. The mapping is prospective and was
not selected from queue or performance outcomes.

Compatibility effect: clock ID/path, conversion, origin, boundary points,
limits, and all identity fields are suite-defining. A syscall, direct-TSC
reader, different boundary point, corrected value, changed limit, or source
switch is incompatible and fails closed.

## Verification and acceptance tests

Stage 8 implements the software/evaluator portion of every exact check in the bundle, including
same-core monotonicity/read-cost samples, three-window bidirectional offset and
drift qualification, singleton-affinity/migration checks, conversion and
overflow goldens, timestamp-order/equation tests, partial-failure handling,
dual-disassembler rules and mutants, both accepted compiler/library matrices,
and applicable sanitizers. The software and generated-code checks pass locally.
Static capability evidence, a short development smoke, or a synthetic
qualification vector is not a platform pass; explicit selected-core,
full-count, traced-vDSO, three-window, and before-block evidence remains
mandatory at Phase 9/16.

## Rollback or supersession

Failure makes the build, platform, pair, block, or run ineligible at the stated
gate. There is no automatic fallback. Any source, boundary, correction, limit,
or identity change requires a new suite/policy ID, superseding ADR, and full
prospective requalification; existing artifacts remain immutable.

## Protocol-amendment assessment

No amendment is expected because the imported decisions explicitly leave the
clock and linearization-boundary protocol to the implementation repository.
If protocol review finds that bracketing or nanosecond sampling changes a fixed
timestamp meaning, stop Stage 8 and obtain a versioned protocol amendment
instead of accepting or implementing this ADR.
