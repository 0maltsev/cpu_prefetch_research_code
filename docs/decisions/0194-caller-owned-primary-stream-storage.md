# ADR-0194: Place primary observation streams in caller-owned storage

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-194
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: primary stream placement for the live discovery backend

Existing primary streams allocate their raw buffers through the general heap.
Add explicit caller-owned buffer constructors and exact checked byte
requirements for both stream kinds. The caller owns the buffer and stream
object, places their storage, constructs/prepares them on their worker, and
keeps both alive throughout capture and publication. Constructor success
verifies geometry only; the backend must separately bind and observe actual
worker-local residency and reject overlap between workers' regions.

Require exact logical buffer bytes, the existing 64-byte alignment, checked
address ranges, and no overlap with the stream object's own metadata before
writing external bytes. Preserve the existing zero-capacity behavior. Keep
ownership bookkeeping in existing padding before the aligned control block
so hot member offsets, object size in supported ABIs, and append operations
remain unchanged. Never free caller-owned bytes.

Use the same owner preparation, literal per-row run-ID prefixes, raw codec,
row identities, append/seal behavior, overflow failure and immutable snapshots
for both storage modes. No new raw format, inference, compression or summary
substitution is introduced. Mapped/rounded resource bytes remain distinct from
logical raw bytes. No buffer growth, replacement or allocation is allowed
between warmup and measurement.

Verify exact golden producer/FULL/consumer bytes and decoding for both modes,
invalid-size/alignment and overflow rejection before mutation, caller lifetime,
zero capacity and exhausted-buffer retention. Verify owner preparation,
append, snapshot and sealing without allocation in supported hook matrices,
run relevant sanitizers and the strict storage/other codegen gates, and bind
the new source in the eventual qualified release before any stand capture.
