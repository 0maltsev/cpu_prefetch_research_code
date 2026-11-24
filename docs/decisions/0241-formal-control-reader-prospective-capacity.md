# ADR-0241: Derive offline formal-control capacity from the signed plan

- Status: `ACCEPTED` — engineering correction within the authorized D240 recovery
- Date: 2026-11-08
- Scope: offline parsing of the original E23 Q16a control documents only
- Experiment, retry, family validity and Stage 18 authority: none

## Observed defect

The original-prefix analysis exited at 13:04:57 UTC with
`unsupported cumulative packed page capacity`. Its supervisor reports exit 1,
all owned children reaped and no raw mutation. It produced no accepted capture
report or prefix manifest. This was an offline reader failure, not another
Q15/Q16 invocation. All original archives, failed evidence and reconstructed
scratch remain retained on the stand.

The unchanged D213 reader limits cumulative packed page arrays to 268,435,456
bytes. The original signed plan requires more storage, independently of any
observed page value. Its 42 residency queries each retain address and node
arrays. Each phase has BEFORE and AFTER queries over seven complete regions,
plus the seven frozen DURING subsets. With the existing 8,192-element blocks
and eight-byte integers, charge every allocated 65,536-byte block including
final slack. The exact prospective totals are 387,710,976 bytes for contexts
0 and 1, and 388,759,552 bytes for context 2. All three exceed the discovery
reader's 256 MiB ceiling while remaining below 512 MiB.

## Correction

The separately byte-bound offline operator derives the 84 array lengths and
their aggregate packed capacity from the original signed capture geometry,
region sizes and DURING counts. It supplies that exact finite capacity to an
isolated copy of the existing packed-reader function. Historical validator
files and their module globals remain unchanged. Keep the original integer
syntax/range, JSON, size/hash/identity and control checks. Require every array
to have its frozen length, exactly 84 arrays, and the exact charged capacity;
reject extra/missing arrays and formal `drain_rows` rather than spooling them.
Reject any derived capacity above 512 MiB.

The worker's 8 GiB address-space limit, four-worker policy, total memory,
scratch quota and deadline remain unchanged. Check that packed capacity plus
the existing resident-text and arena bounds fits that worker limit. This is
an implementation capacity correction, not an increase in observations,
duration, scientific tolerance, capture count or selection opportunity.
All raw reconciliation and D212 classification still use the original
independent per-capture validator. An unsupported or invalid observation still
fails; no validity report is synthesized from the capacity calculation.

Before a full-prefix analysis, check the corrected reader and validator against
one already reconstructed original capture. That check grants no prefix reuse.
D240 still requires all 177 independently accepted original captures and an
actual successful supervisor completion, followed by compatibility, fresh
qualification and signed continuation admission. The changed offline operator
must have its exact source hash admitted by a verified successor release;
the existing release's original operator pin is not bypassed or modified on
the stand.

## Verification

Targeted software tests reproduce the original packed-capacity rejection,
exercise the unchanged packed reader under a derived bound, verify the three
actual signed-plan totals, reject malformed values/lengths/geometry, preserve
historical globals, and reject a worker budget too small for the reader. These
tests do not establish empirical capture validity. Retained-byte validation
remains a separate operational step.
