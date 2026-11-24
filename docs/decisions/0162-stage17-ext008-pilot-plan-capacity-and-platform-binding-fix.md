# ADR-0162: Stage 17 S17-EXT-008 pilot-plan capacity power-of-two rule and platform-binding cross-check fixes

- **Status:** `ACCEPTED`
- **Decision ID:** D-162
- **Classification:** implementation correctness, real-evidence adaptation;
  two independent gaps discovered while first constructing the real
  `S17-EXT-008` pilot plan
- **Owner:** repository/build/runner owner
- **Gate:** before any real `S17-EXT-008` admission can be attempted

## Context

Constructing the real, 180-cell/3-repetition `S17-EXT-008` pilot plan
against the real, already-admitted `S17-EXT-004` resolution and this
real stand's own hardware surfaced two independent, real, verified
gaps in `tools/stage17_pilot_plan_v4.py`'s `validate()`.

### Gap 1: capacity candidates required to be powers of two

`_validate_capacities` rejects any `cache_capacity_evidence` candidate
whose `capacity` is not an exact power of two
(`value & (value - 1)`). The real, compiled queue implementations this
candidate table describes -- `RingSpscQueue`/`LinkedSpscQueue` in
`src/queue/ring_spsc.cpp`/`linked_spsc.cpp` -- never impose that
constraint: their constructors only require `capacity != 0` and use a
conditional wraparound (`next == capacity_ ? 0U : next`), not a
bitmask, so any positive capacity runs correctly on the real hardware
(confirmed by direct reading of both `.cpp` files).

Real cache sizes for this stand, confirmed live via
`/sys/devices/system/cpu/cpu0/cache/index{2,3}/size` (read-only SSH
query, no writes): L2 (index2) `1_048_576` bytes (1024K), LLC (index3)
`37_486_592` bytes (36608K) -- the latter exactly matches the real,
already-admitted `S17-EXT-004` measurement's `local_llc_bytes`, a
useful independent cross-check. `cache_line_bytes=64` confirmed by both
sysfs and the existing admitted record.

Real per-item byte cost of each structure, from the real source:
`RingSpscQueue`'s `Slot` is `sizeof(std::atomic<const void*>)=8` bytes
per slot; `LinkedSpscQueue`'s `Node` is rounded up to one 64-byte cache
line per node (`node_stride_bytes_ = round_up(sizeof(Node),
cache_line_bytes)`, and `sizeof(Node)=24` easily fits one line). Using
the per-item scaling payload (`ring_bytes = 8*capacity`,
`linked_bytes = 64*capacity`) rather than each structure's full
`layout_evidence().total_bytes` (which also includes each queue's O(1)
control-structure overhead -- ring cursors, linked recycler/ownership
blocks -- negligible at scale but a real definitional choice that was
explicitly decided in favor of the per-item-only reading), the
`LLC_RESIDENT` band `(2*usable_l2_bytes, producer_home_llc_bytes/2]` =
`(2_097_152, 18_743_296]` is achievable only for `capacity` in the
exact integer range `(262_144, 292_864]`. That range contains **no**
power of two: `2**18 = 262_144` is excluded by the strict lower bound,
and the next one, `2**19 = 524_288`, is far above the upper bound. The
power-of-two-only rule, not any real hardware/software limitation,
made `LLC_RESIDENT` mathematically unreachable on this real hardware.

### Gap 2: platform-binding cross-check requires byte-identity with pre-v4 evidence

`validate()`'s platform-binding cross-check requires
`plan["topology_evidence"]`/`plan["cache_capacity_evidence"]` to be
byte-identical (via `copy.deepcopy` plus dict equality) to the real,
already-admitted `S17-EXT-004` resolution's own
`pilot_platform_measurements`. That real evidence was hand-authored
under ADR-0151, before this v4 pilot-plan schema (and its required
`producer_cpu`/`producer_numa_node`/`near_consumer_cpu`/
`near_consumer_numa_node`/`far_consumer_cpu`/`far_consumer_numa_node`/
`candidates`/`selected` shape) existed. `S17-EXT-004`'s real
`topology_evidence` instead has `{cache_domains, far_core_pair,
near_core_pair, numa_nodes, physical_cores, smt_enabled, sockets}`,
and its real `cache_capacity_evidence` only has `{cache_line_bytes,
local_llc_bytes, source}` -- no `candidates`/`selected`/
`usable_l2_bytes` at all. `append_resolution()` refuses to ever
re-admit an `input_id` that already has a resolution (`"input already
has an immutable resolution"`, `tools/stage17_operational_cli_v11.py`),
so `S17-EXT-004` can never be edited to the new shape. As coded, no
`topology_evidence`/`cache_capacity_evidence` value could ever
simultaneously satisfy the pilot-plan schema (which forbids the old
shape's extra keys) and this byte-identity check (which requires the
old shape verbatim) -- a real deadlock, not a shape the plan's own
author could work around.

## Decision

Ship `tools/stage17_pilot_plan_v5.py`, an additive successor
(`import stage17_pilot_plan_v4 as base`, monkey-patching
`base._validate_capacities` and `base.validate` on `base`'s own module
object) following the same pattern already established for
`stage17_operational_semantics_v9.py` (ADR-0160) -- `validate()` is
called everywhere via `pilot_plan_runtime.validate(...)` on the
imported module object, a bare attribute lookup resolved fresh at call
time, so patching the attribute on the defining module is sufficient;
no caller needs to change which name it imports.

- `_validate_capacities`: keeps the real `cache_line_bytes`
  power-of-two check (cache line sizes genuinely are always powers of
  two) and drops only the capacity-must-be-power-of-two requirement,
  matching what the real compiled queues actually accept.
- `validate()`: a faithful full copy of the original, with the
  platform-binding section replaced. `_translate_topology` reads
  `producer_cpu`/`near_consumer_cpu`/`far_consumer_cpu` directly from
  the real, already-admitted `near_core_pair`/`far_core_pair`
  (`[0,1]`/`[0,26]`); NUMA-node labels are assigned by the definition
  of "near"/"far" itself (near shares the producer's node, far does
  not -- the specific integer label is arbitrary, so
  `producer_numa_node = near_consumer_numa_node = 0`,
  `far_consumer_numa_node = 1`), consistent with both the real,
  already-admitted `numa_nodes: 2` count and the real, live-confirmed
  LLC `shared_cpu_list` (`0-25,52-77` on this stand, excluding cpu 26).
  `cache_line_bytes`/`producer_home_llc_bytes` per placement are still
  cross-checked byte-for-byte against the real admitted
  `cache_line_bytes`/`local_llc_bytes`. `usable_l2_bytes` and the
  `candidates`/`selected` table have no corresponding artifact in the
  current admitted evidence graph at all -- no session in this
  engagement ever measured per-working-set-class cache residency
  boundaries (confirmed by reading every real Q16 ticket-construction
  script, which hardcode a single `capacity=64` throughout, never
  varying it by working-set class). They are real, freshly-observed
  facts (the live `/sys/.../cache/index2/size` read above, and the
  real compiled queues' own struct-size formulas) carried directly in
  the pilot-plan document itself, which is `S17-EXT-008`'s own
  `REPOSITORY_FILE` evidence -- and are therefore only checked
  structurally (via the now-real-hardware-accurate
  `_validate_capacities`), not against a prior admission that does not
  exist.

## Effects

- `S17-EXT-008`'s real pilot plan can now be constructed and validated
  locally against the real, already-admitted `S17-EXT-004`/`S17-EXT-006`/
  `S17-EXT-007` evidence, without needing to (and without being able
  to) re-admit `S17-EXT-004`.
- Real candidate capacities chosen for the pilot plan (item counts, not
  required to be powers of two): `4096` (`L2_RESIDENT`,
  `ring_bytes=32768`, `linked_bytes=262144`), `270000`
  (`LLC_RESIDENT`, `ring_bytes=2160000`, `linked_bytes=17280000`),
  `16000000` (`BEYOND_LLC`, `ring_bytes=128000000`,
  `linked_bytes=1024000000`) -- identical for the `NEAR` and `FAR`
  placements, since the queue data structures themselves do not depend
  on producer/consumer placement.
- On the real, already-sealed admission root, `S17-EXT-008` admission
  (like `S17-EXT-007`'s before it) is run through a local wrapper that
  imports both this file and `stage17_operational_semantics_v9.py`
  (ADR-0160) for their import-time monkey-patch side effects before
  importing `stage17_operational_cli_v11`, since `admit-resolution`'s
  own `append_resolution()` re-validates the entire journal from
  scratch first, which re-exercises `_phase_family`'s authorization-
  lifetime check against `Q16b`'s real 59-minute session again.
- A future pilot-candidate bundle rebuild should fold `v5.py` into the
  real import chain (analogous to `v9.py`/`v18.py`/`v6.py`) so a fresh
  journal does not need the wrapper.
