# ADR-0188: Construct the unchanged ring in caller-owned mapped storage

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-188
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: setup/storage ownership for producer-home discovery preparation

The ring's existing constructor always obtains its slot and cursor storage
through the general heap. The live discovery backend needs dedicated mappings
that can be bound to the producer's node before first touch and exhaustively
queried before/during/after capture. Binding arbitrary heap pages can affect
unrelated allocations, and observing event-arena placement alone is insufficient.

Add a constructor accepting two caller-owned raw byte spans for slots and
cursors. Require exact logical byte counts, verified-request cache-line base
alignment, nonoverlapping address ranges, and checked size/address arithmetic.
Reject invalid storage before constructing any queue objects. Both constructors
use the same object initialization. Destroy the queue objects normally; external
storage remains owned by the caller and must outlive the queue.
Expose checked storage requirements derived from the actual private slot and
cursor types; callers must not guess their ABI sizes. Check the combined byte
count as well as both products before accepting a geometry.

Keep queue member layout, slot representation, cursor separation, acquire/release
operations, one-attempt semantics, prefetch targets, and reset unchanged. Report
the same logical storage footprint for both constructors. Page-rounded mappings
and their resource/residency facts are separate caller evidence; do not relabel
mapping padding as active queue storage or claim a NUMA policy was verified just
because construction succeeded. The backend still must bind, first-touch, and
verify the actual mappings under its frozen plan.

Verify exact capacity/FIFO/wrap/FULL/reset behavior, caller storage survival and
reuse after destruction, and rejection of bad size/alignment/overlap/overflow.
Run relevant sanitizers and strict queue codegen/provenance checks. Re-pin
first-party implementation hashes and freshly reviewed codegen evidence through
the mutable engineering provenance records; preserve previous Git revisions and
every immutable scientific protocol/policy. No third-party code is reused.

This setup interface supplies neither a live calibration action nor execution
authority. A prospective policy/release must bind these changed source bytes.

The mandatory provenance check also reproduces stale linked header/source
hashes. The exact expected bytes are recoverable at Git revisions `6792b9e`
and `c17289c`; their differences from current source are the earlier initial
node-order retention and quiescent reset, not new measured queue operations.
Refresh those two engineering source identities without changing linked code.
Both disassemblers still match every existing binary/operation evidence hash.

That review separately exposes allocation in the existing linked reset through
`audit_quiescent` and temporary vectors. This conflicts with the fixed warm-start
reset requirement and remains a blocker for formal linked calibration. Repair
it in a separately tested slice before source qualification; a source-hash
refresh does not establish compliance with that lifecycle rule.

Verification: the integrated GCC CTest suite passes 419/419. Queue (17) and
calibration (50) cases plus queue stress pass in both compiler sanitizer
matrices; development Clang also passes six RapidCheck properties with 100
cases each. The five new storage cases include nonzero sentinel bytes to detect
writes on rejected spans. Global formatting, focused strict static analysis,
source provenance, and all six strict dual-disassembler codegen gates pass.
The queue probe binary and all four operation bodies remain byte-identical to
the preceding verified probe. See
[the bound verification record](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261102-01/external-ring-checks.json).
