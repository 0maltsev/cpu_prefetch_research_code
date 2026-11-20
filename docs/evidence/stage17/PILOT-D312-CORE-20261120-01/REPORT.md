# S180 native capture core verified; stand integration remains

The new native core retains both original phases in independent caller-owned
streams and uses the accepted scheduled-session lifecycle, instead of running
separate warmup and measurement captures. It binds six placement/working-set
contexts shared across packages, hardware states and loads, with unchanged
queue/workload/capture primitives. [Engineering decision D312](../../../decisions/0312-s180-persistent-capture-core.md).
The approved scientific profile remains180 settings, one repetition,5s warmup
and1s measurement. No empirical pilot data or new qualification was collected.

## Implemented behavior

- All five statically selected packages use the same context's arena and queue
  objects. A context registry rejects replacement and partially overlapping
  event/node arenas. It has no load/package/hardware key.
- The same two workers execute warmup, parked drain/reset and measurement.
  Both phases' producer/consumer raw storage is present before warmup. Reset
  changes neither the allocated data mappings nor the original raw storage.
- The controller checks and resets the drained selected queue before warmup.
  Undrained prior events block release and remain intact. Source, owner or
  observation failures never become a successful capture.
- Completed warmup primary bytes remain available when reset or measurement
  observation fails. Incomplete phases retain their actual incomplete status.
  No warmup summary substitutes for its original raw producer/consumer streams.
- FULL is retained and reconciled independently in each phase. No zero-loss,
  confidence, final feasibility, covariance or Stage18 claim is promoted.
- Alias, unaligned/invalid source, incompatible R2 geometry and reused-session
  checks prevent unsafe/repeated capture. Reusing session storage starts no
  additional worker and cannot reset/discard later queue contents.

The returned raw views borrow the caller's storage; all objects and buffers must
remain alive through synchronous publication. The caller serializes access to
each context. Native mapped ownership, original source/seed provenance and
platform observation are separate mandatory gates; this core supplies no
synthetic replacement for those facts.

## Fresh verification

| Check | Result |
|---|---|
| New adapter correctness suite, GCC16.1 | 12 passed |
| Related CTest selection | 47 passed:12 new plus35 existing scheduled/service/mapped lifecycle cases |
| GCC ASan + UBSan | 12 passed |
| GCC TSan | 12 passed |
| Clang22.1/libc++ ASan + UBSan | 12 passed |
| Clang22.1/libc++ TSan | 11 passed,1 allocator-hook test skipped under the existing interceptor convention |
| Allocation/free hook | Zero watched allocation/release during prepared-owner capture, reset and measurement in the supported matrices |
| Targeted clang-tidy and clang-format | PASS |
| CTest registration | All12 new cases discovered with calibration/pilot/synthetic labels |

All tests use synthetic clocks and explicit software-only owners/observers,
while exercising real queues, packages, row storage and exact reconciliation.
They establish software correctness only. The original missing-adapter compiler
failure is preserved; initial host GCC16.2/CMake4.4 were rejected by existing
version gates. Builds used the previously provisioned GCC16.1.1/CMake4.3.3 and
Clang22.1.6 prefixes without network fetching or weakening version constraints.
ASan disables LeakSanitizer under the documented managed-ptrace convention.
The matrix runner is retained under verification/.

New test registration uses TEST_PREFIX and verifies actual CTest labels. An
initial empty filter was detected and corrected; it contributes no passing
cases. The subsequent actual47-case result is in ctest-related-final.txt.
Static analysis caught exception-contract and unchecked-optional issues during
authoring; the final checked result has no actionable diagnostics. No existing
native worker source or calibration/hardware record was altered.

## Remaining before a stand run

The existing production pilot entry still uses the historical route. Connect
this tested core to actual monitored mapped owner/control storage, sealed
schedule transport and complete artifact publication/lossless custody. Then
complete the exact scoped pilot plan and EXT008/009/010 admission, native
codegen/correctness/qualification and calibration compatibility, exact buffers,
source/namespace provenance and an all-inclusive time/storage envelope.
These gates cannot be replaced by this unit-test result.

The signed EXT007 freeze and all708/120/180 calibration reports remain preserved.
No S180 experimental schedule preparation, native stand qualification or pilot
collection occurred, and the24h operational window has not started. The prior
6.39h Q16c collection/validation analogy remains an incomplete estimate; it is
not the verified total pilot ETA. Stage17 remains incomplete; Stage18 is deferred.
[Updated ordered plan](../../../STAGE17_PILOT_PREPARATION.md).
