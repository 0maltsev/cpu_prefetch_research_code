# S180 mapped native capture verified; production routing remains

The pilot capture now has family-owned mapped event/queue data, private mapped
phase/source storage and native monitoring of both persistent mappings. The
approved S180 design is unchanged. [D313 implementation decision](../../../decisions/0313-s180-mapped-native-capture.md).

## Completed step

- One prepared context retains event records and both queue implementations
  across package/state/load captures. Its records are read-only and its actual
  mapping/cleanup evidence remains separate from requested placement.
- Per-capture preparation copies both original source arrays into owner-prepared
  read-only storage and constructs independent original warmup/measurement
  producer/consumer streams. The same two workers execute both phases.
- Capture closure releases only private mappings/stacks. It preserves the shared
  data and both phases' observations through synchronous publication, including
  completed warmup when measurement fails.
- The new native pilot uses nine observed regions and54 per-phase/moment query
  records across the two phases. Shared data is observed before/during/after
  each phase. Existing native service/calibration paths retain seven regions.
- Cold checks reject changed seed/layout/owner, stale shared mappings, incomplete
  residency coverage, model/emitter mismatch and unmet node-pattern admission.

## Fresh software verification

| Check | Result |
|---|---|
| Pilot suite | 22 passed:12 existing core,5 mapped-data,3 mapped-runtime,2 native-layout cases |
| Related CTest selection | 61 passed; includes scheduled/service/mapped and legacy native-ring regression |
| GCC16.1 ASan + UBSan | 22 passed |
| GCC16.1 TSan | 22 passed |
| Clang22.1/libc++ ASan + UBSan | 22 passed |
| Clang22.1/libc++ TSan | 21 passed,1 allocator-hook case skipped under existing interceptor convention |
| Targeted clang-format / clang-tidy | PASS |
| Protocol / schema fixtures / canonicalization / queue provenance | PASS |
| Registration | All22 pilot cases have calibration, pilot and synthetic labels |

The tests use synthetic clocks and explicitly simulated NUMA/memory owner or
locking observations, with actual mmap/mprotect, worker stacks/TLS and native
queue/raw/reconciliation code. They establish software correctness only, with
no empirical timing, residency or qualification claim. The ten-capture test uses
all five packages twice on the same shared context without regenerating data.
The native tests perform cold sizing/rejection only; they do not access MSRs or
invoke a stand capture. Legacy Q16c fixed-action entry bytes are unchanged.

Provisioned GCC16.1.1, CMake4.3.3 and Clang22.1.6 dependencies were reused without
network fetch. ASan disables LeakSanitizer under the managed-ptrace convention.
The first broad protocol check correctly rejected the host's newer rpds-py;
rerunning with the existing pinned2026.5.1 dependency prefix passed all four
checks. During test authoring, an incomplete synthetic MSR fixture and a test
macro brace warning were fixed. Static analysis caught unchecked optional
accesses and ambiguous same-type monitor arguments; final checked source uses
explicit guards and a compile-time region count. The61-case final regression
and all four final sanitizer results cover the resulting source. Logs, matrix
runner and source hashes are retained under verification/ and the manifest.

## Next required steps

The production fixed-action pilot still uses its historical entry. Connect the
new native capture to authenticated sealed sources and a separately versioned
publisher retaining both phases, nine-region observations and separate final
family cleanup. Then finish exact scoped EXT008/009/010 inputs/admission,
release codegen, clean-release qualification/compatibility and the presented
all-inclusive duration/storage budget. Working-set classification must account
for the real full footprint, including both retained queue types and all six
contexts. No current geometry or time/storage admission is inferred here.

EXT007 and all708 Q16a /120 Q16b /180 Q16c calibration results remain complete
and preserved. No completed calibration/validation/qualification was repeated.
No stand preparation, qualification or pilot was started; the24h operational
window has not started. Stage17 remains incomplete and Stage18 is deferred.
[Ordered plan](../../../STAGE17_PILOT_PREPARATION.md).
