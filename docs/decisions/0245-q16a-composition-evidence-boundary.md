# D245: Preserve both Q16a collection histories during composition

- Status: ACCEPTED engineering implementation under D240
- Date: 2026-11-13
- Scientific estimator, observation minimum and immutable protocol: unchanged
- Scope: completed original 177-report prefix and D244's 531-report suffix

`stage17_q16a_composite_v1.evaluate` validates the original parent bytes and
the actual continuation plan. It reads each original report with its own local
ordinal and run IDs. Its new composite packet records the original analysis
slot separately from local capture ordinal, together with each source's true
plan SHA and revision. There is no fabricated 708-capture execution plan or
native result. Existing v2 calibration dispatch continues to reject suffix-only
evaluation.

Both legs use unchanged D230 report normalization and exact derivation. Missing
and invalid reports remain explicit; they cannot be padded, replaced or topped
up. Genuine reconciled FULL remains valid data and independently fails the
zero-loss gate. The new packet contains no claim of producer authentication,
family validity, operational admission or execution authority from mathematics
alone.

`stage17_q16a_suffix_admission_v1.authenticate` is incident-bound to the actual
D244 configuration and operator packet hashes. It requires the final
analysis process receipt, typed exit/reaping/non-mutation fields, finite elapsed
time and scratch usage, all 531 ordered reports and the final suffix manifest.
Administrative elapsed time is parsed separately from integer-only scientific
JSON; no original receipt is rewritten.

The caller supplies qualified `prepare_retention` output. The gate checks the
original v6 signature, predecessor lineage, request/attempt/result/completion,
authority chronology, restoration and quiescence through the existing qualified
semantics. Every suffix checkpoint, custody receipt and canonical raw binding
must match the signed original result's artifact inventory. Each report's raw
hashes and counts are checked against that checkpoint and its nine archive,
release-ledger and custody-registration records. The capture check preserves
the original prefix admission logic with explicit family SHA and local ordinal
parameters; historical source and module globals remain unchanged.

This offline metadata gate permits at most 12,000 files, 32 MiB per file,
512 MiB aggregate reads and 1,800 seconds, with symlink/regular-file/hash/race
checks. Those limits neither change experiment limits nor authorize raw decode.

`evaluate_authenticated` first requires completed suffix admission, then invokes
the existing prefix/compatibility admission using authenticated EXT006 context.
It reads the already validated original prefix reports and calls the exact
composite arithmetic. The returned evidence envelope still marks geometry
provenance and EXT007 admission unestablished. Native geometry provenance,
downstream export/freeze and operational admission require their actual checks;
successful composition alone grants no Q16b/Q16c execution or Stage18 authority.

Verification covers original identity/source retention, known exact arithmetic,
missing/invalid data, FULL retention, corrupted/aliased reports, changed context,
prospective mismatch and accepted-incident byte guards. Suffix admission tests
use actual small D220 software fixtures to check original metadata equivalence,
local/context separation, source-family mismatch, native/checkpoint mismatch,
typed process completion, finite limits, symlink/FIFO rejection and refusal to
compose unfinished analysis. An additional check uses the actual retained plan
bytes with no reports: all 708 slots remain MISSING/UNRESOLVED with no credit.

Full empirical suffix admission and composition cannot pass before D244 finishes.
This software implementation does not pre-accept those future results or change
the running operator. No native source or qualified measured release is changed.

## Exact retained-report finalization correction

Review found a deterministic final bookkeeping mismatch in the frozen D244
operator: it compares `asdict(store.ledger_binding())`, containing
`file_name/size_bytes/sha256`, with the registry's summary containing
`sequence_number/sha256`. The running inverse/raw validation is unaffected, but
that comparison cannot pass after all 531 reports finish. Preserve the running
operator and every completed report.

`finalize_stage17_q16a_suffix_v1.py` waits for the original terminal receipt,
checking only that receipt every 30 minutes until the original finite deadline
plus a 30-minute finalization allowance. It grants no experiment or retry. A
normal successful original finalization requires no repair. Otherwise it handles
only exit 1 with the exact original ledger-comparison traceback, all children
reaped, unchanged raw data and all 531 reports present. Any other error stops it.

The finalizer authenticates original signatures and custody again through the
qualified code, then checks every retained report against signed checkpoint,
native counts, raw hashes and ledger records. It reads metadata only and does
not decode raw captures again. It projects the actual current ledger tip to the
registry's two-field representation, requires both the original summary and
physical file hash/sequence to match, and rechecks stability before publication.

It may publish the missing suffix manifest and a separately bound finalization
supplement, naming its actual source, original nonzero process receipt and error,
all 531 report bindings and both ledger representations. Original process/error
bytes remain unchanged. Admission requires either the genuine original success
or this exact reviewed supplement, and still checks every original signature and
report binding. The supplement is never a generic failure override. Tests bind
the finalizer source hash and reject other errors, wrong ledger shapes/sequences
and ordinary nonzero exits without a supplement. The finalizer remains bounded
to 2 GiB AS and the same finite metadata-read limits.
