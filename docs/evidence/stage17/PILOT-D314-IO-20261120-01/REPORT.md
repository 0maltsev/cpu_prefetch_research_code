# S180 sealed source and complete publication helpers verified

The approved S180 native capture now has a cold sealed-source loader/owner and
its own complete artifact publisher. Real original sealed schedule files flow
through mapped capture and independent raw-stream publication in software tests.
[D314 engineering contract](../../../decisions/0314-s180-sealed-sources-and-publication.md).
This completes the transport/publication helper step; the production full-family
authenticated session route is still pending. No stand action was performed.

## Behavior now verified

- Exact selected original artifacts are checked for membership, size, SHA256,
  immutable read-only seals, source ordering/windows and physical FD identity.
  Reserved FD aliases and same-file phase aliases are rejected before loading.
  Borrowed file offsets/descriptors stay untouched.
- Both original source arrays and an independent MSR prestate remain owned across
  copies/moves through native execution/publication. Aggregate retained plus
  transient vector memory and a common deadline are enforced. Only the frozen
  five-second warmup/one-second measurement profile is accepted by the loader.
- The publisher emits four original primary streams, node order, two prepared
  source arrays and a separate S180 control document. It retains the supplied
  nine-region observations and separate prepared/released/completed statuses.
  Original u64BE source provenance remains distinct from prepared u64LE output.
- Completed warmup survives a failed measurement. Sink failure leaves the
  published prefix and returns failure without publishing a complete document.
  Unknown shared-data observations remain null, with no false measured zeros.
- Shared mapping lifetime and final family cleanup remain separate from private
  capture cleanup. No archive custody, scientific validity, inferential result,
  covariance estimate or Stage18 authority is inferred from publication.
- The existing Q16c serialization seam retains its previous schema/roles/result
  semantics; no fixed-action worker entry or legacy acceptance gate changed.

## Fresh verification

| Check | Result |
|---|---|
| New S180 I/O cases | 7 passed |
| Original sealed source cases | 5 passed |
| Complete runner regression binary | 139 passed |
| Focused CTest | 12 passed (7 S180 +5 original sources) |
| GCC16.1 ASan + UBSan | 7 passed |
| GCC16.1 TSan | 7 passed |
| Clang22.1/libc++ ASan + UBSan | 7 passed |
| Clang22.1/libc++ TSan | 7 passed, no allocator-hook exclusion needed in this suite |
| Targeted clang-tidy | PASS; one local suppression tests the explicit moved-from API rejection |
| Targeted and repository-wide format-check | PASS |
| Protocol / schema fixtures / canonicalization / queue provenance | PASS |
| CTest registration | All7 new cases have actual runner, pilot and synthetic labels |

The tests use real sealed memfds and exact hashes, mmap/mprotect, worker stacks,
TLS discovery, queues and independent raw streams. Clocks and selected memory
placement/locking observations are explicitly synthetic. They do not invoke the
native monitor, MSRs or a stand experiment. Both primary byte arrays are compared
exactly; schedule BE-to-LE expectations are computed independently of production
serialization. Both successful and failed measurement paths preserve evidence.

The dedicated unknown-observation regression first failed against zero-valued
pattern output, then passed after the unavailable pattern became null. That
expected failure is retained as a software regression demonstration. Initial
compiler checks also caught an unsupported enum formatter and a test declaration
syntax error; both were corrected. Static analysis removed an ineffective move
into Result's const-reference API and explicitly documented the intentional
moved-from rejection test. Final regression, four sanitizer runs and tidy cover
the resulting source. No failed scientific run or automatic retry occurred.

Verification reuses provisioned GCC16.1.1/CMake4.3.3, Clang22.1.6/libc++ and the
pinned Python dependencies without network fetching. ASan disables LeakSanitizer
under the existing managed-ptrace convention. Source hashes, final logs, the
expected regression failure and matrix runner are retained alongside this report.

## Remaining before stand execution

Bind the helpers into a separately scoped full-family authenticated pilot
session/parser, preserving six persistent contexts,36 common phase-source
artifacts, frozen180-cell temporal order, actual control/recovery and complete
archive/attempt/failure/family-cleanup records. The selected-source helper does
not replace full family membership, accepted-generator/seed provenance or
namespace reservation. Exact EXT008/009/010 admission, release codegen, clean
qualification/compatibility and a presented all-inclusive duration/storage
budget remain required. No generic readiness flag is promoted by this result.

EXT007 remains complete with708/120/180 preserved calibration captures. No
measurement, raw validation or qualification was repeated. The approved single
24h operational window has not started. Full Stage17 remains incomplete and
Stage18 is deferred. [Updated ordered plan](../../../STAGE17_PILOT_PREPARATION.md).
