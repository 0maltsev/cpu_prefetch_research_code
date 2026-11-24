# D261: Plan-sized bounded reading for retained Q16b control metadata

- Status: ACCEPTED engineering correction for the owner's “continue” after the D260 validation stop
- Date: 2026-11-16
- Scope: offline Q16b control reader; no new measurements or changed scientific rule

Original signed E26 plan53ef4b requires more packed page-array capacity than
the256MiB ceiling in the existing discovery JsonReader. Independent raw
validation stopped before establishing scientific validity. Preserve that
failure, original raw/archives, original validator sources and every earlier
qualification. The owner's new continuation instruction permits one bounded
resume of retained-data validation after this correction is tested; a new
validation failure stops dependent work without automatic retry.

Use a separate `stage17_formal_control_reader_v1` to derive the exact rounded
packed capacity from each authenticated, validated capture's seven declared
residency regions and DURING page counts. Charge every64KiB allocation before
allocation. The two phases have four full BEFORE/AFTER snapshots and two DURING
snapshots; addresses and statuses each receive independent block slack. Reject
invalid geometry, out-of-region counts and requested capacity over512MiB.

The prior diagnostic appended the four stack/core regions to region_bytes,
which already includes them. Its estimate was conservatively high by2MiB.
Correct exact capacity is475,791,360 or477,364,224bytes (453.75–455.25MiB) for
the retained prefix, still above256MiB. Keep the old report unchanged and
record the corrected calculation explicitly.

Reuse the original packed-parser bytecode and PackedPages type in a private
function namespace with only MAX_PACKED_PAGE_BYTES rebound to this finite
capture-specific limit. Do not modify qualified module globals, grammar,
integer ranges, node/string/depth limits, checksums, page observations or their
validation. The formal reader retains the existing prohibition on drain_rows.
Scientific capture validation and its report schema/bytes remain unchanged;
the outer process report separately identifies the new reader and its limit.

Use the authenticated original D254 child body with only its control-reader
callback selected privately. Keep actual CPU pinning, independent profile-bound
archive reconstruction, raw hashes,900s capture limits,2GiB decoder/16GiB
scientific-worker address-space bounds, original16GiB reserve and256GiB
aggregate scratch admission. Eight16GiB workers plus2GiB parent remain within
the existing164GiB memory admission including reserves. No unbounded fallback
or automatic higher ceiling is allowed. Failed prior spools stay retained;
there is no reuse credit from an incomplete old analysis.

Charge those retained failed spools against aggregate scratch. Each already
collected capture may reserve its exact six authenticated canonical artifact
sizes, bounded by the original prospective31,227,906,332-byte declaration;
this does not change a future measurement/storage limit. Admit the retained
spools plus the eight largest such reservations plus17GiB overhead only if
their sum fits256GiB. Start with retained capture6, the original reader failure
site, under the same900s limit; only after its valid report run the remaining16
with at most eight workers. Every capture remains required; no replacement or
outcome-dependent selection is permitted. Retain each completed report if a
later required capture fails.

Readiness still requires original signed lineage, failure cleanup/restoration,
all17 original captures, exact archive/profile/ledger integrity and fresh actual
resources. Reconstruct and independently validate retained bytes; do not
recollect a measurement to evade a reader limit. Stage17, custody completion,
the103-capture execution family and Stage18 acceptance remain separate gates.
D260's approved new24-hour experimental window is not started by this offline
correction or retained-data analysis. Its first actual new qualification/
admission action must record that window prospectively.
