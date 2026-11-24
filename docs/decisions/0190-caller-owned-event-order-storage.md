# ADR-0190: Keep the active event order in caller-owned producer-local storage

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-190
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: explicit memory preparation for the live discovery backend

An external immutable event arena alone does not control placement of its
active cyclic lookup permutation: the existing vector allocates that order
through the general heap. The backend needs dedicated producer-local mappings
whose identity and residency can be checked without binding unrelated heap
pages.

Add an arena constructor accepting caller-owned record bytes and a caller-owned
typed order span. Require exact sizes, natural order alignment, checked address
ranges, and no overlap before initializing either region. Use the existing
seeded permutation and payload initialization unchanged; copy the prepared
permutation into the supplied order span and release temporary generation
scratch during preparation. The caller owns the order elements and both regions
and keeps them alive through arena destruction.

All constructors use one active order view for lookup and order/delta checksums.
Keep its pointer beside the existing hot metadata, ahead of cold ownership
bookkeeping. No per-event allocation, selection between storage modes, new
permutation algorithm, payload mutation, or changed consumer action is added.
The owned and external forms must give identical index/payload sequences and
all existing checksums for identical configuration. No storage is freed or
regenerated between warm-up and measurement.

This establishes storage ownership only. The backend must bind, owner-prepare,
and verify actual producer-local pages before execution. Constructor success
does not verify residency or authorize a capture. A prospective source policy
and release must bind the changed arena implementation.

Verify deterministic parity, repeated lookup and checksum action, nonmutation
on invalid/overlapping storage, and caller ownership after destruction. Run
affected unit/no-allocation checks, relevant sanitizers, and generated-code
checks before qualification.
