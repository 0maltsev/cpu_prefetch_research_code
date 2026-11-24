# ADR-0226: Q16c native input and retention boundary

- Status: ACCEPTED (engineering implementation within accepted D036/D210/D219 scope)
- Date: 2026-11-03
- Classification: Typed input, ownership and cold artifact publication
- Scientific method: `MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1`
- Execution authority: None

## Decision

The scheduled parser accepts one explicitly bounded capture with the existing
five-package geometry, persistent arena identity, phase run identities, resources,
monitoring and supplied hardware prestate. Its versioned schema is
`config/schemas/stage17-formal-scheduled-native-input-v1.schema.json`.

The 180-cell identity is package-major: `service_cell = cell_ordinal / 3` and
`load = cell_ordinal % 3`, with the existing 60-cell service context and load
labels L025, L050, L075. Capture ordinal is independent of cell identity. The
outer family contract can therefore enumerate H0 then H1 without altering cell
meaning. Scale ordinal identifies one of D036's five prospective candidates;
the single-capture parser does not select a candidate or assert family coverage.

Both source schedules are explicit serialized unsigned integer vectors. Each
binds a schedule ID, seed ID, seed hex, namespace, source origin, source horizon
endpoint, offered count and source artifact ID/SHA-256. The parser checks exact
field sets, identity separation, finite counts, half-open source endpoints,
nondecreasing deadlines and correspondence between horizon length and declared
phase duration. Measurement must offer at least one arrival under D036. Warmup
has the accepted five-second schedule horizon; no new warmup offered-count
minimum or active-wall-time claim is introduced. Mandatory native observations
remain required even for sparse schedules.

Source artifacts and schedule generation provenance require independent outer
admission. Hash syntax alone does not prove source identity or schedule
reproduction. The arena's reserved warmup namespace remains nonrandom; schedule
seeds are separate explicit inputs and do not change the immutable arena order.

The parsed value owns immutable deadline vectors through shared const storage.
This supports the existing copy-only `protocol::Result` factory without changing
its shared API. `plan()` returns a native value with spans rebound to that
storage; a parsed owner must remain live through synchronous native execution.
Environment paths and hardware prestate still borrow the supplied inputs.
The native owner copies source schedules into its declared immutable mapping
before readiness. No parent-owned JSON vector is executed in the measurement loop.

Pure description recomputes layout without mappings or hardware access, permitting
placeholder declared layout sizes while applying the explicit memory ceiling.
Execution parsing requires exact layout sizes. These bounds cover mapped storage;
outer process/publication budgets must also cover parsed JSON, owned source
vectors, transient copies and analysis scratch. No platform value is defaulted.

## Retained evidence

Cold publication emits four original phase/owner primary streams, two actual
prepared schedule vectors, node order and a control document. Primary codecs
remain `RAW-OBS-U64LE-LP-RUNID-v1`; schedule vectors use
`SCHEDULE-DEADLINES-U64LE-v1`: contiguous unsigned 64-bit little-endian source
clock ticks, with count/origin/horizon and provenance in control metadata.
Schedule metadata identifies picoseconds and distinguishes source coordinates
from the actual phase-origin translation retained in native lifecycle evidence.

Unavailable owners or schedule arrays yield empty artifacts with explicit absent
snapshots or availability, not fabricated observations. An available prepared
schedule does not establish that its phase was released, attempted or completed.
Those facts come separately from the actual lifecycle and scheduled result.
Failure prefixes, current capture failures, checksums, joins, native control
readbacks and actual timestamps remain retained without D211 interval filtering.

The publisher reuses private raw/control helpers with role selection and omits
only the Q16b-specific completion-interval member for Q16c. Existing discovery,
ring and service shapes remain unchanged. It publishes one payload copy at a
time; the prospective budget must include the largest copy plus control JSON
construction/canonicalization. Sink failure is terminal, retains earlier
artifacts and is not an automatic retry.

Publication precedes final stack/mapping cleanup. Its control record explicitly
states that scope; the separately serialized returned native result supplies
final cleanup evidence. Publication grants no execution authority, scientific
validity, zero-loss result, family feasibility or Stage 18 authority.

This count-oriented calibration publisher does not create joined-derived
latency products. The immutable Stage A joined-derived requirement remains in
force for a completed valid Stage A run. A different governing artifact contract
requiring such a product must provide it through separately budgeted cold analysis.

## Verification

Targeted parser tests cover all 180 contexts, phase/seed/source errors, count and
endpoint bounds, zero measurement exposure, stale layouts, unsupported package
settings, memory ceilings and deadline lifetime across parsed copies/moves.
Publication tests cover exact original primary bytes, little-endian schedule
vectors, prepared-versus-executed state, partial failures, sink failure and final
cleanup separation. Existing publisher regressions and relevant sanitizer runs
remain required before integrated release qualification. Synthetic verification
provides no stand or empirical performance evidence.
