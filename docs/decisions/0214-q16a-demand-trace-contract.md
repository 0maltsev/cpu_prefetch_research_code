# ADR-0214: D212 demand trace and independent decoding

- Status: `ACCEPTED` — engineering implementation of owner-approved D212
- Date: 2026-11-03
- Scope: new formal Q16a components and versioned contracts
- Scientific source: accepted D212; protocol snapshot unchanged
- Execution authority: none

D212 requires original demand-start evidence, including excluded drain, to
independently reconstruct its four sequences. Historical diagnostic vectors
contain elapsed demand values and issue differences without every original
bracket. They remain unchanged and cannot be relabeled as formal D212 traces.

Introduce `Q16A-DEMAND-U64LE-LP-RUNID-v1`. Each row uses the existing length-
prefixed UTF-8 run-ID header and zero padding to an eight-byte boundary,
followed by exactly nine unsigned little-endian 64-bit words:

| Word | Meaning |
|---|---|
| 0 | Zero-based attempt ordinal within this worker/phase demand stream |
| 1 | Actual queue outcome: advanced=0, FULL=1, empty=2 |
| 2 | Zero-based advancing ordinal when advanced; zero otherwise |
| 3 | Actual before-acquire `ClockReadStatus` |
| 4 | Before-acquire absolute nanoseconds |
| 5 | Before-acquire relative picoseconds |
| 6 | Actual after-acquire `ClockReadStatus` |
| 7 | After-acquire absolute nanoseconds |
| 8 | After-acquire relative picoseconds |

Role is explicit in the stream contract: FULL is producer-only, empty is
consumer-only. Advanced ordinal zero is distinguished from a nonadvancing
row by its outcome. Ordinals are contiguous in their respective sequences;
they do not use the repeating record index as event identity. Actual advancing
ordinals must be reconciled with the corresponding independent primary stream.

Record a demand row only when the queue/acquire operation actually occurred
and its actual outcome and both attempted clock reads are available. A failed
demand clock does not invent an outcome: the existing void acquire observer
still permits the actual queue operation, whose outcome and failed read status
remain retained. A failure before an acquire creates no demand row; preserve
the current capture's absent observations and mandatory stop in control
evidence. Never fabricate a successful demand to fill a partial prefix.

Storage is explicitly caller-owned, sized and owner-prepared before capture.
The measured path appends bounded observations without allocation, I/O,
filtering, quantiles or dynamic parsing. Publication uses the explicit codec
after quiescence. Overflow or a failed observation makes a retained incomplete
prefix, not a valid shorter run. Same-worker warmup and measurement storage
remain distinct and persist through the parked logical reset.

The independent per-stream contract is
`cpu-prefetch-stage17-q16a-demand-stream/1`, with exact fields:
`schema_version`, `method_id`, `physical_format`, `run_id`, `role`, `phase`,
`phase_window`, `minimum_observations_per_series`, and `stream`.
`method_id` is D212's `RING-D2-RUNTAIL-LTL95C95-WINDOW-v2`.
`stream` binds relative path, byte size, SHA256 and row count.
`phase_window` binds clock suite, unit, ticks per second, absolute clock origin,
`phase_origin` (absolute nanoseconds and relative picoseconds) and positive
`duration_ticks`. The actual released phase origin must later be cross-checked
against native execution evidence; an arbitrary well-formed envelope does not
establish it.

Both phases validate every retained row's grammar, run identity, clock status,
exact conversion, ordering and advancement. Pre-origin demands are invalid.
Warmup uses `phase=warmup`, a null minimum, no inferential quantiles and
`inferential_eligible=false`. Measurement uses `phase=measurement` and an
explicit positive minimum, applying D212's eligible-window positivity and
minimum-count rules. All drain rows remain subject to raw-integrity checks.
Neither a zero-length excluded drain bracket nor an excluded drain issue tie
alone makes an eligible sequence nonpositive.

Compute exact inverse-ECDF ranks with integer arithmetic. The independent
decoder validates and counts in a first hash-verified pass, then uses a second
hash-verified pass over the same file identity to retain only the smaller
extreme heap needed for each exact eligible rank. A software analysis
memory bound is not a scientific minimum; exceeding it must report an analysis
resource failure, not truncate observations or alter the estimator. Emit small
count/rank/summary records instead of reproducing the raw streams as JSON.

Expose a separate `evaluate_windowed_ring_distance` numerical entry point
requiring D212's method identity. The existing `evaluate_ring_distance` still
requires D037 v1. Both call the same unchanged checked quantile, run-plan,
extreme and distance arithmetic; neither changes or relabels its input plan.
The successor's caller must supply independently window-validated series and
bound original evidence. Numerical evaluation alone cannot establish raw
membership, integrity, hardware validity or execution authority.

Test the physical codec independently, malformed headers/ordinals/statuses,
clock conversion and overflow, all half-open endpoint and crossing cases,
FULL/empty advancement, warmup exclusion, valid excluded ties, eligible
nonpositive sequences, minimum-count failure, and exact ranks against a small
independent full-sort reference. Native tests cover bounded caller-owned
storage and actual queue/capture integration with relevant sanitizers.

These components grant no standalone run validity, hardware qualification or
experimental authority. Full primary reconciliation, persistent runtime
placement/monitoring, versioned formal input/output/admission and the later
finite prospective plan remain required before formal collection.
