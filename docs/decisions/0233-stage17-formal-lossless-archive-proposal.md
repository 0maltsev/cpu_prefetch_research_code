# ADR-0233: Future EXT007 formal lossless archival custody

- Status: **ACCEPTED by the owner on 2026-11-03; implementation and qualification required before use**
- Date: 2026-11-03
- Proposed policy ID: `EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1`
- Scope: Future explicitly admitted Stage 17 EXT007 Q16a/Q16b/Q16c families only
- Supersedes if accepted: D033/D206 compression and physical representation
  requirements only within that prospective scope
- Execution authority: **None**

## Decision requested and unchanged obligations

Approve a prospective, bounded lossless archive representation of every future
formal canonical raw/control artifact, with one authoritative stand copy under
D206's accepted storage-domain risk. After independent archive readback and
exact inverse reconstruction verification, the now-redundant uncompressed
working representation may be released through the narrowly specified ledgered
transition below. This is a **new storage-policy permission**, not something
already authorized by D206 or by ordinary software-development authorization.

Historical R1/R2/R3 raw, controls, failed prefixes, identities and custody remain
unchanged. This proposal authorizes no historical deletion, recompression,
relabelling or replacement. No experiment, capture, retry, stand operation or
production implementation follows from a PROPOSED ADR. Even acceptance of this
storage policy alone would not authorize a formal experiment.

Canonical observation formats, every byte of their original encoding, original
artifact IDs, row order, run identity, timestamps, statuses, padding, count
equations and original SHA256 remain unchanged. Control JSON, including raw
environmental bytes and all preparation/readback/cleanup facts, is preserved
byte-for-byte, not reparsed and rewritten. Failed and partial future captures
receive the same lossless retention, with their actual failure status preserved.
No field dropping, quantization, aggregation, hot-path compression, invented
zero, favorable filtering or replacement is permitted.

Five-second bootstrap warmup, accepted repetition/minimum requirements, fixed
prospective measurement durations, D212 windows, D211 completions and D036
statistics remain unchanged. No attempt/poll cap or measurement duration is
chosen here. Complete D224 and the applicable independent formal prerequisites
before freezing those inputs. Compression receives **no hot-memory credit**.

## Why a storage successor is needed

The owner reports no additional storage. Current D206 requires uncompressed
raw/control. Conditional equal 30m-row capacities for minimum Q16a/Q16b families
would reserve 33,304,320,000,000 canonical warmup bytes alone, or
66,608,640,000,000 for both phases, before other artifacts. These are capacity
examples, not newly approved caps or expected formal output. Current stand free
space is approximately 6.927 TB decimal; actual admission requires fresh exact
evidence. Reducing declared row maxima cannot silently shorten warmup or omit
required raw observations.

Protocol 2.0.0-pre.3 section 8.3 permits frozen lossless **post-measurement**
compression. D033's rollback section expressly requires a new policy ID,
superseding decision, dependency/license review, resource updates and prospective
requalification. D206 changes durability count, not compression. This proposal
uses that allowed storage-policy route; it does not introduce a new experiment
method or claim that sample compression ratios guarantee family completion.

## Proposed exact reversible payload transform

Proposed codec IDs:

* Fixed-row raw: `RAW-U64LE-COLUMN-MODDELTA8192-ZSTD157-L3-v1`.
* Byte-oriented controls/other metadata: `BYTES-4MIB-ZSTD157-L3-v1`.

Use the provisioned Zstandard **1.5.7**, level **3**, one compression worker
(`-3 -T1` equivalent). Freeze the actual encoder/decoder binary SHA256,
dependency/license provenance, complete options and bounded decoder-window
configuration in the qualified implementation profile before use. No dictionary,
training, adaptive level, cross-artifact frame history or content-driven codec
choice is permitted. The physical framing/header grammar still needs a pinned
engineering format specification and tests before qualification; these payload
rules do not claim an existing production archive implementation.

For a known fixed-row canonical format with an eight-byte-multiple row width R:

1. Validate/bind R from the canonical physical format and actual LP run-ID
   geometry. Partition the original artifact into blocks of **8192 complete
   rows**, except the last shorter block. Every original word, including LP
   prefix/run-ID bytes, padding and all status/timestamp words, participates.
2. Treat each eight-byte word as an **opaque little-endian uint64**, without
   interpreting scientific fields. In each block, visit columns in original
   word order. For each column initialize `previous=0`; visit rows in original
   order and emit `(word-previous) mod 2^64` as little-endian uint64, then update
   previous to the original word. Concatenate columns in that order.
3. Encode that transformed block as an independent zstd level-3 frame. Reset
   delta state at every block; no dependency on a previous block is allowed.
4. The inverse decompresses the bounded frame, accumulates each column modulo
   `2^64` from zero, and restores original row-major little-endian words. Exact
   byte identity, not a field-equivalence comparison, is the acceptance rule.

Apply the fixed-row codec to primary producer/consumer and D214 formal demand
rows. A complete canonical u64 schedule/node-order vector may use the same
codec with R=8 if its prospective artifact-role profile explicitly declares it.
Unknown formats never receive a guessed row width. An incomplete/malformed
failed-prefix artifact that cannot be proven to consist of complete fixed rows
must use the byte codec for its **entire actual file**, with the reason retained;
no bytes are padded, discarded or repaired. This fallback is mechanical and
does not alter the recorded scientific invalidity.

For control JSON, manifests, failure records and other byte-oriented artifacts,
partition exact original bytes into **4 MiB** blocks (last block shorter), apply
no transform, and encode independent zstd level-3 frames. Empty artifacts have
an explicitly represented zero-length original with its SHA256; they are never
silently omitted. Small authorities, inventories, validation results and ledger
records may remain uncompressed, counted in the same physical quota.

The archive header/index must bind at least format/policy/codec version, original
artifact identity and role, canonical codec, run/phase identity where present,
original size/SHA256, row width/count or exact byte-oriented length, fixed block
policy, ordered block ordinals/offsets and original lengths, per-block encoded
lengths/hashes and exact decoded lengths, zstd profile/binary identity, and
completion state. Reject unknown versions, missing/duplicate/reordered blocks,
length overflow, decoder-window expansion, trailing data and truncation. The
manifest/ledger separately binds the complete physical archive size/SHA256,
avoiding an ambiguous self-hash. Binding the whole archive also binds its header.

## Evidence for level 3, and its limits

Retained read-only reports:

* `build/stage17-step5-prep/formal-integration/storage-roundtrip-samples-1.jsonl`:
  96/96 plain-zstd roundtrips, 48 files, 12 contexts, first/last 4 MiB.
* `build/stage17-step5-prep/formal-integration/storage-column-roundtrip-samples-1.jsonl`:
  96/96 reversible-transform roundtrips, 24 primary files, 48 aligned blocks of
  up to 8192 rows. Original files unchanged; no archive custody was established.

The transformed primary samples total 45,613,056 bytes; level 3 produced
6,733,910 bytes and level 9 produced 6,514,819 bytes. Reported producer mean
fractions are .1380/.1311, consumer .1613/.1594 for levels 3/9; individual maxima
remain higher. Level 9 saves only about 3.25% of the level-3 aggregate encoded
bytes in these samples. Level 3 is proposed to limit cold processing cost while
retaining most of the observed transform benefit. This does not certify a
full-capture compression time, archive ratio, deadline or completion probability.

Discovery demand uses a different four-vector format. **Formal D214 demand
compression ratio has not been measured.** The generic opaque-word transform is
mathematically reversible for its rows, but that is not a ratio observation.
Likewise actual future formal primary/control distributions can differ from R3.
Equal sample bytes per role are not a full-family weighted ratio. No event-rate,
buffer horizon or full-family fit guarantee is inferred from these samples.

## Logical identity and one-copy physical custody

Retain two distinct bindings:

* Logical canonical binding: original artifact ID, exact canonical byte size and
  SHA256, original format, phase/run and published source references.
* Physical archive binding: new immutable archive ID/path, physical byte size
  and SHA256, codec/profile and block index, verified logical binding, verified
  timestamps and sole stand storage-domain ID.

An append-only representation ledger records creation, verification, publication,
working-copy release, failure and recovery transitions. The original producer
manifest and native result are never rewritten to pretend they directly emitted
compressed bytes. The archive is a new physical representation of those exact
bytes, not a replacement scientific observation. This remains one authoritative
stand domain, not an independent backup. Loss of that domain can lose evidence.

All future raw/control artifacts, including unsuccessful prefixes, must appear
in the inventory and ledger. Preserve original expected hashes and any actual
hash discrepancy as separate facts; do not manufacture a matching original
manifest for corrupted bytes. Archive actual failed bytes only with an explicit
failure binding. An unverified archive cannot justify releasing its source.

## Per-capture lifecycle, no overlap with measurement

1. Finish the native capture and mandatory worker cleanup. Before compression,
   durably retain its original final-result receipt, actual control/primary
   bindings and native completion/failure facts, bound into the metadata ledger.
   Stop before starting the next capture. A later family summary is not a
   substitute for this original per-capture receipt.
2. Verify exact source identities, sizes, SHA256 bindings and retained native
   failure facts. These source-byte checks and the full archive inverse/hash
   checks below establish archival byte identity; **independent scientific
   per-capture validation is not an archival prerequisite**. Preserve all valid,
   invalid, failed and not-yet-scientifically-validated evidence. Scientific
   validation may occur later using bounded one-capture decoding, or bounded
   parallel decoding after the family under a separate prospective analysis
   plan. It remains mandatory before any calibration credit. Do not assert raw
   scientific validity merely because lossless storage succeeds.
3. Encode to exclusive no-overwrite staging objects under finite memory, disk
   and time limits. No native worker measurement runs during analysis/archive.
4. Sync data, independently reread physical archive bytes, verify their SHA256,
   decode/invert every block, and recompute **the complete original byte size
   and SHA256**. Validate block/frame boundaries and full input consumption.
   Streaming hash verification needs no second full decoded disk image.
5. Sync and atomically publish the new immutable archive and its ledger receipt;
   verify durable manifest/ledger visibility. Only then may the exact scoped
   uncompressed working representation be released, with a separate receipt.
   Failure before this transition preserves every source and records incomplete
   custody. No destructive repair, overwrite, implicit measurement retry or
   favourable replacement is allowed.
6. Check archive quota, fresh available space, the next capture's worst-case
   workspace and all remaining time/authority gates before continuing. A native
   mandatory failure still stops the family; archiving its prefix cannot turn
   it into a successful run or authorize the next run. When the native capture
   is complete and the existing collection gates pass, pending independent
   scientific validation alone does not block the next capture. Cold compression
   and custody verification finish at this checkpoint; neither analysis nor
   archiving runs during measurements. No new serial scientific-validation gate
   is added to the authorized collection family.

The current `src/runner/stage17_fixed_action.cpp::formal_family_action` proceeds
from capture publication to the next capture, retaining final results in memory
until family-end publication. It does **not** already implement this checkpoint.
A versioned cold checkpoint/final-result receipt and bounded acknowledgement
must be implemented and qualified before using this policy. Background archiving
while the next measured capture runs is not a substitute. No hot-loop or native
canonical observation codec change is proposed.

Later validation resolves a logical artifact through its bound archive, using
a verified streaming decoder or at most one explicitly bounded capture spool
per analysis process. An after-family parallel analysis plan must prospectively
bound process count, aggregate memory, simultaneous capture spools, total scratch
and deadlines within the available resources. It grants no new capture authority.
Current path-based validators/retention admission need a versioned integration;
missing uncompressed paths must not be silently treated as valid originals.
This ADR does not claim that compatibility already exists.

## Physical quota and bounded peak space

Proposed whole-program future-formal physical archive quota: **6,000,000,000,000
bytes (6 TB decimal)**, shared across Q16a/Q16b/Q16c, successful and failed future
captures and their retained metadata. It is not reset to 6 TB for each family.

Reserve separately:

* Capture/publication/archive workspace W = **512 GiB = 549,755,813,888 bytes**.
* Independent analysis/decode scratch S = **256 GiB = 274,877,906,944 bytes**.
* Untouchable operator/failure reserve R = **16 GiB = 17,179,869,184 bytes**.

With the explicitly rounded reference F=6,927,000,000,000 available bytes:

```
Q = floor((F-W-S-R) / 1,000,000,000,000) * 1,000,000,000,000
  = 6,000,000,000,000
F-Q-W-S-R = 85,186,409,984 bytes
```

The last figure is reference rounding headroom, **not an observed exact free
balance**. Historical raw has already reduced F and must not be subtracted again.
Actual initial admission must bind fresh exact filesystem/inode free space,
unrelated concurrent use and existing task reservations. It must support Q+W+S+R;
otherwise reject rather than silently reduce reserve or increase quota. Later
checks distinguish already used archive bytes from remaining quota.

Before each capture, W must cover its exact canonical raw **plus control/final
metadata** maximum, publication/staging disk extents, and the archive staging
maximum for the chosen sequential publication design. S must cover the actual
validator/decode-spool bound. The 512/256 GiB values are finite ceilings, not
proof that any unexamined capture/analysis fits. Exact prospective resource
validation can reject a capture larger than either ceiling. Native mapping,
MEMLOCK and owned-vector/JSON publication heap still require their separate
current-runtime bounds and live-memory checks.

Archive coding uses one bounded block at a time and one compression worker.
The implementation must enforce explicit codec-window and block-output limits,
checked arithmetic and bounded controller/child address spaces. Proposed cold
archive/inverse-verification address-space ceiling is 2 GiB per active codec
process, with at most one such child at a time; independent capture analysis
uses its separately frozen bound, provisionally no more than 8 GiB for one
analysis process. After-family parallel analysis requires an explicitly bounded
process count and aggregate admission, not an implicit multiplication of the
8 GiB per-process allowance or the shared 256 GiB scratch reserve. These are
failure limits, not measured memory guarantees.
Archive and analysis timeouts are mandatory finite prospective inputs with no
implicit extension; they are not set from sample throughput or invented here.

Track quota against actual encoded bytes, ledger/index/header bytes, retained
uncompressed small metadata and all in-flight archive writes. Check before
bounded writes, not only after a filesystem-full error. Reserve raw workspace
so a quota/codec/time/readback failure can retain the current uncompressed
capture and terminate safely. Frame-overhead/encoder expansion maxima must be
proved for the frozen implementation or bounded by an enforced output ceiling;
a sampled ratio is never an admission maximum.

**This is a finite-quota, possibly incomplete-family policy, not guaranteed
whole-family fit.** A full guarantee would need the sum of proved archive maxima
plus workspace/scratch/reserve to fit. Ordinary lossless compression has no
universal beneficial ratio. If quota/space/time admission fails, stop before the
next capture, retain all attempted results/receipts and mark the unexecuted
prospective identities MISSING/UNRESOLVED. Do not select a favourable subset,
reduce the plan, extend the family, rerun failures or delete prior data.

Current formal plan contracts sum canonical raw output maxima into retained-disk
requirements. This policy needs an explicit successor distinguishing cumulative
canonical emitted bytes from concurrent physical retained bytes and the quota
stop condition. Do not satisfy old admission by lying about row size, cap,
canonical output length or free space. Owner approval must encompass this
incomplete-family risk, not merely the choice of compression software.

## Required implementation/qualification before activation

After explicit owner acceptance, complete only the storage successor: pinned
format/header/ledger/profile, bounded encoder and independently implemented
inverse, artifact resolver, per-capture cold checkpoint, quota/deadline and
crash/recovery controls, source/physical hash binding and exact readback proof.
Preserve all existing canonical codecs and historical qualified artifacts.

Tests must cover all original byte values including LP padding, uint64 wraps,
empty/one/8191/8192/8193 rows, partial trailing bytes through the byte fallback,
full/partial metadata blocks, missing/duplicate/reordered/truncated/corrupted
frames, wrong row width/codec/run identity, forged lengths/hashes, decompression
bombs, deterministic output under the frozen profile, quota/time/process exits,
disk-full/partial-write/fsync/readback failures and crash at each ledger/release
transition. Original-source release is forbidden until durable verified archive
and ledger exist. Test both actual C++ publisher byte fixtures and independent
format goldens; no hardware performance claim follows from these tests.

Qualify the exact integrated source/release/controller/storage profiles and
retain current stand recovery/readback evidence before any formal admission.
No additional experimental invocation or source deletion is authorized by this
proposal, the sample reports, or the software tests.

## Recorded owner acceptance

The owner explicitly replied “Approve D233 smaller-storage plan” to the complete
proposal on 2026-11-03. The [original proposed bytes](../evidence/stage17/FORMAL-STORAGE-D233-PROPOSAL-20261103-01/proposal.md)
(SHA256 `e0afc7010b7c0ee84adccf25eaf00679dbc79f51d1970fce3f42f8223ab91c02`)
and [acceptance receipt](../evidence/stage17/FORMAL-STORAGE-D233-PROPOSAL-20261103-01/owner-acceptance.json)
are retained. The proposal text above records the exact accepted policy; its
prospective implementation, finite resource checks and release qualification
remain mandatory. This acceptance grants no experiment or historical deletion.
