# ADR-0189: Verify and restore the linked warm-start state without allocation

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-189
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: implementation correctness against the existing logical-reset contract

The lifecycle validator requires `allocation_count_delta == 0` during logical
reset. The existing linked reset calls the allocating general-purpose audit
twice and constructs temporary comparison vectors. Fresh allocation-counter
regressions observe eight allocations on each successful reset and three on
rejection of a nonempty queue. A third regression exposes that the reset also
silently normalizes an out-of-order recycler that remains unique and full.

Replace those audits inside reset with a bounded allocation-free verification
of the frozen cycle. A drained queue has one valid sentinel equal to its tail,
no successor, and a full recycler containing the other nodes in the original
seeded cycle's rotation after that sentinel. Check both cursor ranges and their
equality, validate stored order bounds, locate the sentinel in the retained
permutation, and compare every recycler pointer in FIFO order. The constructor
already establishes that retained permutation's uniqueness; reset never changes
it. No auxiliary bitmap or newly allocated scratch array is required.

Reject a nonempty, missing-node, duplicated, or out-of-order state before any
mutation. An out-of-order cycle violates the fixed node-order contract; this
is a correctness failure, not a new statistical exclusion or a FULL-outcome
filter. Do not repair and hide corrupted warm-up state. Then clear node links
and event fields, restore sentinel `pi[0]`, recycler `pi[1]..pi[C]`, and zero
cursors in the original allocations. Verify the resulting empty cycle through
the same bounded check. Keep the allocating detailed audit available for
separate post-run analysis; it is no longer called by logical reset.

Preserve all measured queue operations, memory orders, object layout, mappings,
initial permutation, and event-record payloads. This implements the existing
warm-start rule; it changes no scientific method or protocol snapshot. New
source provenance and prospective release/policy qualification remain required.

The three new tests first fail on the old implementation. Verify zero allocation
for rotated and already-reset valid states, rejection without allocation or
mutation for pending events and a corrupted cycle, preserved storage identity,
and exact reset order. Run queue/workload/calibration regressions, relevant
sanitizers, and strict codegen/provenance checks before qualification.

The existing CMake policy excludes global `operator new` interception under
Clang TSan, which owns the same interceptors. Preserve that exclusion. Run
functional queue reset/corruption coverage under Clang TSan without allocation
hooks, and retain actual allocation-counter checks in the supported matrices.
Do not report an observed allocation delta for a configuration without its
counter test. Exhaustive small-capacity checks cover every cursor/sentinel
rotation for capacities one and eight without relying on timing thresholds.

Verification: both development compilers pass the integrated 424-entry CTest
suite. All five allocation-hook workload cases and 18 queue cases plus stress
pass the supported sanitizer configurations. Clang TSan passes the 18 queue
cases (including reset/corruption coverage) and stress without allocation hooks.
Formatting, focused strict static analysis, source provenance, and all six
strict dual-disassembler codegen gates pass. The measured queue probe binary
is unchanged. The
[bound evidence](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261102-01/linked-reset-checks.json)
and [actual failing reproduction](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261102-01/linked-reset-before-fix.txt)
record the scope. No calibration or pilot capture ran on the stand.
