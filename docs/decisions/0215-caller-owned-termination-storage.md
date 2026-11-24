# ADR-0215: Caller-owned termination publication storage

- Status: ACCEPTED — engineering implementation authorized by the owner on 2026-11-03
- Scope: storage ownership of the existing release/acquire termination word
- Scientific method change: none
- Execution authority: none

The D210 persistent service session accepts two existing `TerminationControl`
objects. Their original constructors privately allocate dedicated cache lines.
A native factory cannot place those private allocations in its declared mapped
control region. Constructing only the C++ objects in that region is insufficient.

Add a pure checked `TerminationControl::storage_requirements(CacheLineBytes)`
function and a constructor taking the caller's exact-sized `span<byte>`. Both
constructors use the same atomic initialization and publication implementation.
The borrowed constructor validates the supplied cache-line geometry, exact
extent, alignment, address arithmetic, and non-overlap with its own object before
constructing the atomic. The caller must provide disjoint lines for independent
controls, construct them before releasing workers, and keep their storage alive
until destruction after worker join. Destruction ends the atomic's lifetime and
never frees borrowed bytes. The original owned constructor remains supported.

This preserves the `ARRIVALS-FINISHED-U32-RELEASE-ACQUIRE-v1` policy, the atomic
width, memory orders, parked reset precondition, worker stop/drain behavior, and
experimental endpoints. Requested cache-line size remains explicit; no hardware
size is inferred or defaulted. Native placement, prefaulting, locking, residency,
and control monitoring remain the native factory's separate obligations.
Successful construction and the existing layout evidence establish only the
local storage geometry and atomic properties.

Targeted verification covers exact sizes, invalid geometry/alignment/overlap,
owned and borrowed behavior, destructor ownership and padding, release/acquire
publication through two parked reset phases, and no borrowed-constructor
allocation under the supported test instrumentation. Relevant sanitizer runs
and strict static checks are required. Software checks grant no qualification
or experiment authority; evidence is retained separately by the integration
owner. Queue sources and their provenance are unchanged by this decision.
