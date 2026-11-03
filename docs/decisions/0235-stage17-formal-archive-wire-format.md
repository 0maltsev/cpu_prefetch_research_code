# ADR-0235: D233 bounded cold archive representation

- Status: ACCEPTED — engineering implementation under the owner's D233 acceptance
- Scientific method change: none
- Execution and qualification authority: none
- Scope: prospective formal EXT007 policy `EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1`

D233's exact proposal SHA256 is
`e0afc7010b7c0ee84adccf25eaf00679dbc79f51d1970fce3f42f8223ab91c02`.
Its owner acceptance is retained in
`../evidence/stage17/FORMAL-STORAGE-D233-PROPOSAL-20261103-01/owner-acceptance.json`.
This decision fixes the previously unspecified wire grammar and implementation
boundary. Historical canonical files and their policies remain unchanged.
No encoder result establishes scientific validity, capture authority, or source
release authority.

## Exact physical grammar

All framing integers are unsigned 64-bit little endian. SHA256 fields in binary
framing contain 32 digest bytes, not hexadecimal text. Concatenation is exact:

1. Eight ASCII bytes `CPFA2331`, header byte length, then the canonical UTF-8
   JCS-I64-v1 header without a line terminator. The header obeys
   `stage17-formal-archive-header-v1.schema.json`; unknown fields reject.
2. Exactly the declared number of blocks, in order. Each has a 64-byte prefix:
   ordinal, canonical offset, decoded length, compressed length, compressed-frame
   SHA256; then exactly that frame's bytes. Each block is one independent zstd
   frame, with no dictionary or previous-frame history.
3. A 56-byte footer: eight ASCII bytes `CPFAEND1`, block count, complete original
   byte size, complete original SHA256. Exact EOF follows.

Header geometry and identity come from the admitted external role/profile,
not from trusting the archive's assertions. Known raw LP run-ID geometry is
`align8(4 + UTF8_run_id_bytes)` plus 120 producer, 80 consumer, or 72 demand bytes.
The header retains the worker separately from the artifact role. Explicit
node-order and schedule vector formats may use eight-byte rows; even a canonical
big-endian vector undergoes the same opaque LE-word transform and exact inverse.
For raw rows the encoder checks actual length, run-ID prefix and zero padding.
Malformed rows fail without deleting source or partial archive. The parent may
choose only an explicitly bound whole-file byte fallback with a retained reason;
the encoder never silently changes codec or repairs bytes.

Rows use exactly 8192 rows per block, with a shorter last block. Every word is
transposed column-first and differenced modulo 2^64, previous zero at each column
and block. Bytes use exactly 4 MiB blocks, with a shorter last block and no
transform. Empty sources have no frames and still have a header/footer and the
SHA256 of zero bytes. The footer means complete representation, never complete
native capture or durable custody. A separate receipt binds the entire physical
archive size/SHA256, avoiding a self-hash.

## Options, dependency and finite resources

The accepted implementation uses provisioned zstd 1.5.7 level 3, no dictionary,
checksum enabled, content-size enabled, dictionary-ID emission disabled, and an
explicit frozen window log. `ZSTD_c_nbWorkers=0` uses the one calling thread with
no background worker. This realizes one-thread compression; it is not a claim
that the shared-library call is bit-for-bit equivalent to the CLI's `-T1` framing.
Each block uses `ZSTD_compress2` to emit an independent complete frame. No adaptive
codec/level choice is permitted.

Use the stable shared-library API. The provisioned shared image does not justify
using interfaces documented for static linking only. Caller-owned scratch has
checked finite canonical, transformed and compressed extents; all three are
mutually disjoint. Cold JSON, hashes and the zstd context allocate separately.
`ZSTD_sizeof_CCtx` is retained as an observation and checked against a caller limit;
it is not a bound on transient allocation. The standalone encoder requires an
already finite RLIMIT_AS of at most 2 GiB. It changes no process permissions or
limits. A separately enforced finite process watchdog remains necessary because
an individual blocking Linux I/O call cannot enforce its own wall deadline.

Every plan supplies header, decoded-block, encoded-block, physical-output,
observed-context, I/O-piece, I/O-call and absolute CLOCK_MONOTONIC deadline bounds.
Positive short I/O advances the exact offset within the finite call allowance.
Zero progress, EINTR and other errors stop without retry. The call allowance
counts operations-interface calls; inspect retains both its actual fstat and
fcntl results. Source/output identity and access checks precede output; output
must be an empty distinct regular file without O_APPEND. Exclusive creation is
an owning-parent obligation, not something an already-open fd can prove.

The fd-only tool bounds its canonical plan input and result output separately
with required `--plan-byte-limit` and `--result-byte-limit` arguments, and checks
actual running executable and dladdr-resolved zstd image SHA256 against the
profile. Each dependency scan has the plan's finite I/O-call allowance and the
same absolute deadline; these scans precede the separately reported encoder I/O
count. A source-qualified launcher must also bind all other runtime dependencies.
The source/library hashes supplied to the library API alone are declared external
bindings; only the standalone tool performs the actual image checks.

The encoder retains actual source stat observations, original/output byte counts,
observed hashes and failure call/offset. It checks source size/hash and unchanged
stat facts before the completion footer. It fsyncs staging and returns
`COMPLETE_STAGING_SYNCED`; this is deliberately insufficient for source deletion.
A parent captures exit/stderr even if failure occurs before result-fd publication.
The finite result write is one attempt, then fsync; partial/failure remains an
incomplete result for the parent to retain.

## Provenance and license

No dependency is downloaded. The accepted runtime supplies:

| Artifact | SHA256 |
| --- | --- |
| `zstd-1.5.7-3-x86_64.pkg.tar.zst` | `d4cf0049137124c8a025eedfad267a3e8a02310c9efb9d1ae4a61aa1d02789fc` |
| `/usr/lib/libzstd.so.1.5.7` | `f023d49e85fb22057bfdd21857263d2638b73356c06f3b342f678a75212379f8` |
| `/usr/include/zstd.h` | `9b4bc8245565c98ccfc61c07749928b57e7c0f6fddb0530c4f6aa1971893d88b` |
| `/usr/share/licenses/zstd/LICENSE` | `7055266497633c9025b777c78eb7235af13922117480ed5c674677adc381c9d8` |

The package inventory's combined license labels remain recorded. The linked
library's retained BSD-3-Clause license permits this use subject to its notice
and disclaimer conditions. `config/dependencies.json` now explicitly records
its direct cold-codec purpose; historical Stage 6 remains uncompressed. The
qualified release must retain the license, actual encoder/decoder/profile and
runtime image bindings. Development executable hashes are not release hashes.

## Custody boundary and verification

Compression runs only after native return, mandatory cleanup, durable original
per-capture final-result receipt and the separate live-quiescence gate. The
parent creates exclusive staging and owns quota/workspace/deadline reservation.
The independent Python reader rereads actual persisted frames, verifies physical
binding/options/windows/geometry, inverse-transforms all bytes and recomputes the
entire original hash. Only its complete proof plus durable no-overwrite archive
publication and ledger visibility can authorize the narrowly ledgered source
release. Native failures remain failures; an archive cannot authorize the next
capture or create observation credit.

Targeted tests cover row/block boundaries, opaque word wrap, actual LP geometry,
whole-file byte fallback, empty artifacts, partial I/O, source changes, aliases,
read/write/fsync errors, clocks, finite budgets and independent reconstruction.
An independent C++-encoder/Python-reader bridge checks actual wire compatibility.
Relevant sanitizers and strict checks are required before integration readiness.
This decision does not claim those checks or whole-release qualification merely
because the implementation exists. Main owns the checkpoint/broker integration;
Locke owns the independent decoder and custody ledger.

## Blocking checkpoint deadline

A cooperative clock check cannot bound a blocked checkpoint fsync or receipt
read. The native cold interval therefore owns one RAII process timer, armed
before checkpoint publication with the already admitted absolute monotonic
deadline. `timer_create(CLOCK_MONOTONIC, SIGEV_SIGNAL, SIGKILL)` and
`timer_settime(TIMER_ABSTIME)` provide the bound without a helper thread or signal
handler. Constructor failure aborts before publication. Scope exit deletes the
timer; inability to delete fails closed with SIGKILL (or `_exit` if delivery
itself fails), never continuing with an uncertain armed timer or generating a
core dump. Guards cannot be copied, moved, nested, or retained across fork.
The parent still owns finite waiting, process reaping, evidence retention and
restoration. No interval duration is selected here.

Fork tests inspect actual `/proc/self/task` counts, require a blocked pipe reader
to die by the timer's SIGKILL, and require a child to survive the original deadline
after deletion. A separate finite test watchdog records its own fallback kill
and cannot turn that fallback into a timer success. The channel test peer also
uses a bounded receive, so a denied sandbox socket operation fails instead of
hanging a join. Required socket credential checks are never bypassed for tests.

## Qualified package profile and runtime location

The unqualified v26/v22 draft bundles include the standalone encoder at
`release/bin/cpu_prefetch_stage17_archive_encoder`, the actual zstd 1.5.7 image
as a regular `release/runtime/lib/libzstd.so.1` file, and its license at
`licenses/zstd/LICENSE`. The SPDX dependency list records zstd. The creator
checks the explicitly supplied runtime library's version and copied byte hash.
A regular SONAME file avoids archive symlink extraction and duplicate images.
Sealed executable memfds do not retain an `$ORIGIN` directory: the broker's
closed launch environment therefore binds `LD_LIBRARY_PATH` to this exact
qualified library directory; the encoder checks the actually loaded image.

The generated canonical no-LF document is
`config/stage17/formal-archive-implementation-profile-v1.json`. It binds the
encoder, library, runtime-relative `usr/bin/python3.14`, codec options, and exact
local Python source closure. Both the runtime and the string-named broker are
explicit closure roots; statically named local imports include jobs, checkpoint,
custody and supervision dependencies. The profile contains no self hash, absolute
PC runtime path, or stand program scope. Its hash is externally admitted.

Package creation requires explicit `--archive-runtime-root` and
`--archive-window-log`. CMake exposes corresponding
`CPU_PREFETCH_ARCHIVE_RUNTIME_ROOT` and `CPU_PREFETCH_ARCHIVE_WINDOW_LOG` inputs
without empirical or host-path defaults. The stand's extracted-release receipt
builder independently requires `archive_runtime_root`; it checks that root's
actual Python bytes against the packaged relative binding. Archive-only
inspection verifies the packaged profile and members, and does not claim to
have observed a stand runtime. Existing hermetic-runtime qualification remains
necessary for Python's system libraries and standard library; this profile is
not a portable standalone Python distribution.

The v12 receipt verifier retains the exact verified runtime provenance on its
frozen extracted-release context. Its qualified-context helper revalidates that
receipt and compares manifest, source, worker, profile, inventory and SBOM
identity with the verified EXT003 release before returning the three archival
context fields. No runtime location is inferred from the authoring machine.
Historical profile recognition remains delegated unchanged. No new release
version or execution authority arises from these draft package changes.

The formal generated-code report additionally binds these cold dispatch,
checkpoint, channel and schedule-loader source files. Active worker acceptance
rules and prefetch vectors remain unchanged. Final clean-source generated-code
reports and complete release verification are still required; focused development
profile, broker and package tests establish software behavior only.
