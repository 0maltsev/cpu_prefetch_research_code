# ADR-0024: Stage 5 queue representation and refinement

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Queue representation / concurrency correctness
- Decision owners: Queue owner; correctness owner; provenance owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 5 implementation; passed

## Context and scientific constraints

The protocol fixes a contiguous-slot bounded SPSC ring and a dSPSC linked FIFO
with bounded SPSC recycler and fixed-arena full adaptation. ADR-0013 requires an
independent implementation without FastFlow source use. ADR-0014 fixes
release/acquire handoffs while requiring exact width, alignment, lock-free, and
refinement evidence in Stage 5. The implementation must not invent a target
cache-line value or introduce retries, fallback allocation, blocking, dispatch,
or new scientific outcomes.

## Options considered

1. Import or adapt current FastFlow source.
2. Replace the declared algorithms with a sequence-number ring or generic
   reclamation library.
3. Independently map the protocol algorithms to ABI-width C++ atomic pointers,
   explicit runtime line layout, and distinct concrete adapters.

## Decision

Select option 3. Ring slots are contiguous ABI-pointer-width atomics; producer
and consumer modulo cursors are thread-owned and occupy separate supplied-line
regions. Slot publication and clearing are release stores observed by acquire
loads.

Linked storage contains exactly one sentinel plus `C` supplied-line-strided
nodes. The main FIFO publishes successor links release/acquire. A separate
contiguous atomic-pointer recycler uses consumer-release/producer-acquire node
return and producer-release/consumer-acquire slot reuse. Recycler exhaustion
returns full immediately; no allocation fallback exists. The caller supplies a
validated `C+1` permutation; its generation is not selected here.

Adapters are distinct final concrete types with direct `noexcept` operations.
Construction and quiescent audit are outside the data plane. Operations contain
no exception, allocation, retry, wait, logging, or virtual dispatch. An internal
recycler invariant signal is a correctness stop, not an additional queue
treatment outcome.

Compilation requires pointer atomics to be ABI-width and always lock-free;
construction and platform qualification require runtime lock-free and layout
checks. Cache-line bytes are explicit with no default. Exact proofs and
linearization boundaries are recorded in `docs/QUEUE_CORRECTNESS.md`.

## Evidence

- Imported implementation specification Sections 3.2, 3.3, 3.5, and 11.1.
- ADR-0003, ADR-0012 through ADR-0014, ADR-0016, ADR-0017, and ADR-0021.
- Independent queue provenance records and Stage 5 unit/property/refinement,
  phase-suspension, stress, layout, and sanitizer results.
- GNU Binutils 2.46 and LLVM 22.1.6 generated-code reports, reviewed operation
  bodies, bound hashes, and independently detected negative mutant.

## Consequences and compatibility

Scientific effect: this is the accepted C++ mapping of the fixed queue cores;
it does not implement prefetch treatments or measurement. Compatibility effect:
targets with non-pointer-width or non-lock-free pointer atomics, incompatible
alignment, or unverified line size are rejected. A sequence-number algorithm,
allocator fallback, normalized adapter, weaker ordering, or different full
semantics is not API-compatible merely because FIFO tests pass.

## Verification and acceptance tests

Both compiler/library families must pass FIFO/model, capacity, wrap, repeated
reuse, rollover-assumption, phase suspension, one-attempt, fault-detection,
ownership, concurrent stress, ASan/UBSan, and TSan checks. Every required atomic
must pass compile-time and runtime lock-free checks. ADR-0016 requires GNU and
LLVM disassembly plus a detected negative mutant; both Stage 5 tool views pass
and were reviewed. Changed source, flags, toolchain, or release boundaries must
regenerate and requalify the evidence.

## Rollback or supersession

Representation, layout, or ordering changes require a superseding ADR and the
full proof/test/sanitizer/generated-code matrix. A changed scientific algorithm,
full policy, or memory-order contract requires protocol review and normally an
amendment.

## Protocol-amendment assessment

No amendment is required. The fixed-arena immediate-full behavior is the
adaptation already declared by protocol `2.0.0-pre.1`.
