# ADR-0203: Caller-owned linked queue storage

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-203
- Classification: Engineering implementation and storage ownership
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: linked Stage A queue preparation; no collection or service-phase authority

## Requirement

Protocol Sections 5.3 and 5.4 and D-035 require service calibration to reproduce
the applicable queue, software policy, consumer action, placement, and persistent
warm-up/measurement mappings. The existing linked queue allocates its node arena,
recycler, ownership fields, and retained initial permutation internally. Those
allocations cannot be composed into the controller's exact owner-mapping layout
through its current constructor. The ring already supports caller-owned storage.

## Decision

Add a pure checked `LinkedSpscQueue::storage_requirements` calculation and a
borrowed-storage constructor. Inputs remain explicit capacity, cache-line size,
arena alignment, and the caller's immutable node permutation. The result gives
exact node, recycler and ownership byte extents, node stride, retained order
element count, and permutation-validation scratch byte count. It checks both
individual arithmetic and the combined addressable storage extent before any
allocation or construction. This is compiled-type geometry, not an inferred
hardware cache-line or page size.

`LinkedStorageView` supplies five disjoint ranges: node bytes, recycler bytes,
ownership bytes, retained `size_t` order elements, and temporary byte scratch.
The node range uses the requested arena alignment; recycler and ownership ranges
use the requested line alignment. Retained order elements use their actual type
alignment. All extents must be exact. Reject null, misaligned, overflowing or
overlapping ranges, including overlap with the queue object and input order,
before writing any supplied range. Validate the permutation in caller scratch,
then copy it into the retained order range before constructing queue objects.
An invalid permutation can modify scratch, but cannot construct nodes or mutate
the other supplied regions.

Successful borrowed construction, queue operations, logical reset, and destruction
perform no allocation or deallocation. The caller retains ownership and must keep
the four persistent ranges alive through destruction; it must not mutate the
saved order while the queue exists. Input order and validation scratch may be
reused immediately after construction. Invalid preparation throws the existing
`QueueSetupError`; exception construction is outside the allocation-free success
contract. The existing allocating quiescent audit remains a cold diagnostic API.

Keep the existing owned constructor and its lifetime behavior. Both constructors
use the same validation and typed-object initialization. Destruction ends node,
recycler and ownership-object lifetimes in either mode; only the owned constructor's
allocation members free backing memory. Preserve the prior meaning of
`LayoutEvidence::storage_bytes`: node, recycler and ownership storage. External
layout callers additionally reserve the retained order and temporary scratch
using the explicit requirements, as well as the queue object and their own padding.

Do not change the enqueue/dequeue algorithm, release/acquire orders, sentinel and
FIFO recycler cycle, immediate FULL outcome, failure boundary, logical-reset
algorithm, or successor-header prefetch seam. The same saved original permutation
drives reset in both storage modes. Caller ownership establishes neither physical
residency nor successful NUMA/page-policy requests; native preparation and actual
observations remain separately required.

## Verification and integration

Targeted software checks compare owned and borrowed state against an independent
FIFO model for small capacities, all drained cycle rotations, pending/corrupt
reset rejection, constructor/destructor reuse, allocation/free instrumentation,
invalid geometry/alignment/overlap/size/permutation, concurrent FIFO transfer, and
L1 successor targets. Existing queue and workload suites and dual-disassembler
queue/workload/combined-package checks remain required. These checks provide no
stand or empirical performance evidence.

The new allocation-instrumented test file must be registered as its own executable;
it replaces global allocation functions and must not be linked with another such
test file. For Clang TSan only, `CPU_PREFETCH_LINKED_ALLOCATION_HOOK=0` disables
the conflicting replacements. That configuration explicitly skips the dedicated
allocation/free-count test, keeps the other functional tests, and makes no
allocation-count claim. The other configurations use the default enabled hooks.
Main integration owns CMake registration, source-provenance updates,
applicability records, and a fresh qualified release. Earlier releases and their
evidence remain bound to their original source and binary identities. This change
is a prerequisite only: formal Q16b interval counting, warm-up execution, admission,
five-package native composition, and independent validation still require their
separate implementation and qualification before collection.

The integrated verification record is
[`native-diagnostic-checks.json`](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261103-01/native-diagnostic-checks.json).
The linked enqueue/dequeue codegen probe and all four operation-body digests
remain byte-identical to their pinned evidence; the current dual-disassembler
checks confirm this after the storage-constructor change.
