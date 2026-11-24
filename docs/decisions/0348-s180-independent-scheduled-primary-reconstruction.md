# D348: independent S180 primary reconstruction core

Accepted engineering implementation of the existing immutable raw-row/join
contract and D310/D346. No scientific convention, sample count, duration,
source, rate, custody policy or native measurement code changes. This is one
offline component of the independent pilot validator, not full capture/family
validation, a qualified operator or execution authority.

The S180 native publication seals four original primary streams and no native
joined stream. Its two accepted scheduled phases use the same persistent arena,
retain FULL observations, and include normal-drain consumer actions. Reusing a
Q16b completion-window filter or treating the native join status as independent
evidence would be incorrect. Reconstruct each phase independently from its two
original producer/consumer streams and exact admitted source/arena values.

`stage17_s180_raw_join_v1.derive_phase` requires the exact versioned phase
contract, packed original deadline/order/payload arrays, original analysis
deadline and a caller-owned fresh private unpublished candidate file. Copy the
bounded arrays before use; validate the record order as a permutation. The
maximum measurement/warmup counts derive from the unchanged D334 rate ceiling:
ceil(2*5011713/4) and ceil(2*5011713/4*5), respectively. The caller must supply
the smaller authenticated per-source bound too. Exact5s/1s source horizons,
unsigned64 domains and clock resolution/conversion/endpoint bounds are checked.

Use the existing protected no-symlink primary opener and physical raw codec.
Distinct paths and actual input/output inodes are mandatory. Validate byte/row
extents, every embedded run identity/padding and the original SHA256 and file
stamps. Each offered deadline maps to exactly one producer logical row, even
when late. Check its deterministic repeating record index independently of the
join key. FULL forbids publication/accepted ordinal and consumes no consumer
row. Accepted producer ordinal matches the independently recorded consumer
ordinal and record; no record-index join or favorable filtering is permitted.

Check every absolute-nanosecond/relative-picosecond pair, per-owner local and
cross-row ordering, publication/removal brackets and strict drain endpoint.
Enqueue/dequeue responses may overlap; queue linearization boundaries define
residence. Recompute the full-drain consumer checksum over independently supplied
payloads. Require offered=attempted=accepted+FULL and accepted=consumed.
Normal-drain completions stay in the measurement latency series. Warmup is fully
reconciled and gets joined rows, but supplies no measurement latency array.

Write the established24-word little-endian joined physical format, including
every timestamp, producer/consumer source ordinal and nine exact intervals.
Verify admission+residence+delivery=end-to-end; nested diagnostics are not added
again. Fsync and independently reread/hash the complete candidate before a
PASSED audit can return. Verify unchanged candidate identity, private mode,
single link, extent and readback stamps. Raw files are opened read-only.

The core never publishes, renames or deletes a file. It cannot make a completed
valid-run claim: source provenance, all controls, family lifetime, original
terminal metadata and custody remain separate mandatory outer checks. A caller
must retain original raw and any failed candidate, durably record JoinError's
FAILED audit, and stop. It may publish a successful joined envelope only after
all independent checks pass. A returned phase audit alone grants no such run
validity or operational authority. This implementation does not yet provide
that durable publication/aggregate-control wrapper.

Tests use disjoint manually constructed software rows, an explicit golden
24-word result, original raw codec and the approved numerical consumer. They
cover FULL/all-FULL/empty phases, repeating indices, warmup separation, normal
drain, response overlap, missing/extra/duplicate/reordered observations,
source translation/window, all clock checks, payload corruption, hash/padding/
identity/trailing bytes, symlink/physical aliases, changed primary stamps,
candidate freshness/readback, exact types/bounds and deadline failure. Initial
fixtures used anonymous temporary files with nlink0; these correctly failed
the durable-candidate contract. Corrected fixtures use named private files;
the original failure log is retained, without weakening the implementation.

No C++ production change or new native sanitizer path exists. Targeted Python
development/debug tests and related codec/numerical tests provide software
verification only. Frozen native34247ce hashes identically. No original raw
data was transferred or analyzed, and no stand preparation, qualification,
admission or operational window started.

Evidence: [verification report](../evidence/stage17/PILOT-D348-RAW-JOIN-20261123-01/REPORT.md).
