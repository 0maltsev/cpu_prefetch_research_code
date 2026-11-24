# D207 prospective resource arithmetic

This supports the [proposed duration amendment](../../../decisions/0207-stage17-ext007-discovery-duration-revision.md).
It is not accepted, not an executable action plan, and grants no authority.

`resource-report.json` models the proposed 36-capture 1/2/5-second grid with
30-million-attempt buffers in both phases. `source-layout-report.json` is
earlier 24-capture 1/5-second arithmetic used only as the source of 24 local,
cold layout queries. Its capture count and aggregate totals are superseded
by the 36-capture report; neither proposal has been executed. The query
inputs and native outputs are retained in `layout-inputs/` and `layouts/`.
Their original paths in the source report refer to the preparation directory;
these copies retain exact hashes. No raw experiment data was read to create
these reports. No native experiment was executed by the layout queries.

The six allocation geometries match across queried hardware states and
1/5-second durations. Allocation for 2 seconds is derived from the same
capacity-based layout formula, not an observed parser pass. The current
qualified parser rejects that new duration. A versioned successor and fresh
exact-layout verification are prerequisites to any future admission.

The disk requirement is 656,917,737,766 bytes, including output, temporary
drain spool and 16 GiB free reserve. The 76,116-second watchdog is a maximum,
not a runtime prediction. Both resource availability and exact successor
requirements must be checked before execution. D206 supplies the accepted
one-copy EXT007 custody policy; it supplies no duration or execution approval.
