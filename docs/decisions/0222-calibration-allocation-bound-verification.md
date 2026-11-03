# ADR-0222: Calibration allocation-bound verification repair

- Status: `ACCEPTED` — narrow software correctness repair during EXT007 checks
- Date: 2026-11-03
- Scope: cold calibration helper declarations and legacy owned trace capacity
- Execution authority: none

Strict Clang/libc++ analysis of the D212 numerical entry point found three
private cold helpers incorrectly declared `noexcept` despite constructing
sets or vectors. Remove that exception specification from `valid_governance`,
`expected_service_key` and `expected_ring_key`. Their calculations, public
interfaces and ordinary results are unchanged. Allocation failure can now
propagate to the existing cold caller instead of terminating within a private
helper. No helper is used by a measured worker loop.

The same check flagged `RingDemandTrace::record` because `vector::push_back`
can grow. Its normal constructor reserves the prospective capacity, but an
implicitly copied or moved-from trace need not retain that reserve. Check
actual vector capacity before either append, as well as the existing logical
attempt limit. Reject the call without modifying either series if an append
would grow. Preserve its `noexcept` and no-allocation contract. A narrow lint
annotation records the proof: both capacities are checked, and constructing
an unsigned 64-bit element cannot throw. It does not suppress a reachable
allocation path.

A targeted copy-capacity regression verifies rejection without growth or
partial issue/demand mutation; the existing trace, caller-owned comparison
and calibration model tests remain required. Relevant sanitizers and strict
checks cover the changed translation unit. This repair changes neither the
already archived qualified D207 release nor its running retained-data analysis.
The new formal D212 collector uses its separate caller-owned raw codec.
