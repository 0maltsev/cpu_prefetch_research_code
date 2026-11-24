# D252: Accelerate cold archival without changing Q16 measurements

- Status: ACCEPTED engineering work by the owner; implemented, verified and deployed; owner-authorized restarted collection running
- Date: 2026-11-15
- Scope: prospective Q16b restart and subsequent EXT007 cold archive readback only
- Native workload, scientific method, repetition count and Stage18 authority: unchanged

The owner instructed “optimize arhive as much as possible” and explicitly added
“we can run the current step again as it is only the beginning”. This authorizes
one planned Q16b restart after verified archive optimization, preserving the
original attempt and all evidence. It does not authorize an automatic retry
following a new failure in the optimized attempt. Completed Q16a, clocks and Q15
are retained; none receives repeat measurement or fresh scientific credit here.

At the retained checkpoint, a capture cycle took633.498303seconds;505.489524seconds
were between native publication and durable custody. The verifier reconstructs
raw words in Python and independently reconstructs again before working-copy
release. These are cold operations with the native worker parked, not timed
queue operations. A software-only Python scan prototype preserved21 independent
cases but improved the inverse only about1.7x on the development PC.

Introduce a small native cold inverse for the exact D233 modulo-2^64 column
transform, bounded to8192rows and4MiB per call. It does no allocation, I/O,
configuration, field interpretation or scientific calculation. Validate geometry,
pointer overflow and nonoverlap before writing. Preserve all bytes, including
identity, padding and timestamps. The Python caller authenticates the complete
ELF image, snapshots it into a sealed memfd and loads only that image. Fail
closed on any bad image, shape, deadline or native status; no fallback execution.

The original framing parser, zstd1.5.7 options, encoder, physical/canonical hashes,
footer and stable-file checks, both complete custody readbacks, publication,
fsync, quota accounting and working-copy release rules remain unchanged. The
new cold source closure is the original qualified closure plus the separately
bound native wrapper/generated image, with only an explicit inverse binding
appended to its separate archive-verifier copy. Historical source/bundles are
not rewritten. The implementation profile binds the generated source containing
exact ELF bytes; its new SHA256 is frozen in the new signed storage plan.

An explicitly authenticated administrative overlay admits this new profile
against the original EXT006 context. It first re-verifies the original qualified
profile/native release, then requires exact old source bodies and unchanged
encoder, Python, zstd and options. The only permitted source delta is the known
inverse hook and its exact two-module closure. Existing signature, owner, UTC,
journal, hardware, namespace, resource and one-attempt gates still apply. The
archive helper is separate from the qualified native measurement executable;
its ABI and bytes require cold correctness/sanitizer/integration qualification,
not repeated clocks/Q15 merely for a cold decoder change.

Before switching, demonstrate independent known vectors, wraparound, unaligned
buffers, empty/partial/full block boundaries, invalid inputs and output safety;
ASan/UBSan native checks; Python-reference parity; actual old/native-encoder
archive roundtrips and corruption rejection; both readbacks under sealed source
execution; profile/source/cache substitution rejection; and bounded synthetic
benchmarks. Development results establish software behavior only. Report actual
stand throughput separately, without projecting kernel speedup onto the whole
experiment.

Stop the old attempt through the existing owned-worker cleanup/restoration path
under a recorded OWNER_REQUESTED_ARCHIVE_UPGRADE intent. Retain original failure
or interruption receipts verbatim. A new plan must use fresh identities/seeds,
the same60cells,59repetitions,5-second warmup,1-second measurement and all original
limits/statistics. Register a new family under the existing shared6TB program;
never reset quota or delete old raw. Old partial data contributes zero runs to
the restarted family. Reuse authenticated Q16a handoff and existing qualification.
Reapply and verify isolation only after old workers are reaped and hardware/OS
restoration passes. Sign the exact new request, then launch once with stop on
first new experimental failure. Stage17 exit, independent validation and Q16c
remain required; this engineering decision grants no Stage18 authority.

## Additional measured cold metadata bottleneck

A read-only stand profile over59578ledger records spent42.6seconds replaying
under cProfile, including21.9seconds canonicalizing JSON (3.64million separate
JSON string encoder calls). These are profiler timings, not an uninstrumented
capture estimate. Retain full record replay, chain/transition validation,
integer domain checks and path/hash/identity verification.

Add an exact canonical-byte fast path for builtin JSON trees with ASCII keys,
integer leaves in the existing signed64/unsigned64 domain, strings, booleans
and nulls. One C JSON encoder call replaces repeated per-field calls. Floats,
non-ASCII keys (including UTF-16/codepoint-order differences), subclasses,
shared/cyclic containers, deep trees and unsupported/out-of-domain values use
the original canonicalizer with its original formatting/error behavior.
This changes no canonical format or accepted result. Archive source copies
append one explicit canonical binding in addition to the inverse binding.

For controller metadata replay, privately clone the original ProgramStore and
executor function bodies with this exact-byte canonicalizer. Preserve all
original global modules, functions, classes and sys.modules identities. All
records remain read and validated; no checkpoint cache, skipped prefix or
reduced custody check is introduced. The new administrative packet authenticates
the canonicalizer and clone factory, and its profile admits only the exact
known source additions. Fresh parity, malformed-input, chain/custody and private
namespace tests are required before stand use.

## Preserve live quota scans while reducing directory traversal overhead

Each bounded ledger/metadata/archive write invokes physical accounting; the
stand profile traversed76118objects in one inventory call. Replace only the
private store's traversal implementation with os.scandir/DirEntry.stat, retaining
every current stat and all root/directory/regular-file checks, working namespace
and inventory limits, hardlink identity deduplication, allocated/logical-byte
arithmetic, retained receipt accounting and actual pre-write capacity checks.
No inventory cache, immutable-file assumption or skipped object is introduced.
Both controller and sealed broker use this separately authenticated private
class. The broker source copy appends the exact known class binding; original
custody source bodies remain byte-identical. Compare complete inventory results
against the original on real files, hardlinks, sparse allocations, symlinks,
invalid names and exhausted limits, and exercise the real sealed two-readback
custody path before activation.
