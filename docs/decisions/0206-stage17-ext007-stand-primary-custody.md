# ADR-0206: EXT007 stand-side analysis and primary-only raw custody

- Status: **ACCEPTED — explicit owner approval recorded on 2026-11-03**
- Date: 2026-11-03
- Proposed policy: `EXT007-RAW-NONE-STAND-PRIMARY-v1`
- Scoped supersession: D-033's second independent raw-copy requirement for
  Stage 17 EXT007 diagnostic and calibration data only, including the retained
  first v19 attempt and R2. All other D-033 scopes remain unchanged.

## Owner request and verified storage

The owner asks to analyze on the stand, download only final results, and
regularly clean failed or unnecessary data from the development PC.
Analysis can already run on the stand using the existing validators.

The stand has four 3.84 TB disks participating in RAID10. Its evidence path
is on the single `/dev/md3` ext4 filesystem, with about 7.15 TB free at the
read-only observation. No separate independent raw-storage domain was found.
RAID redundancy and a second directory on this filesystem are not a second
independent artifact copy under D-033.

## Proposed decision

1. Keep one authoritative, uncompressed raw/control copy on the stand under
   each original immutable run identity. Explicitly record `m_dur=1` for this
   scoped policy. There is no independent raw backup; loss of the stand's
   filesystem can lose the raw evidence.
2. Verify exact original sizes and SHA-256, quiescence, restoration and
   manifest bindings before running the unchanged independent validators on
   the stand. The former PC-copy gate is replaced by this explicit policy
   and primary verification, not falsely marked satisfied.
3. Download small signed authorities, manifests, hash inventories, failure
   and restoration records, validation reports and final results to the PC.
   These are derived/provenance copies, not substitutes counted as raw copies.
4. Preserve failed and partial experimental raw data on the stand. They
   remain necessary evidence; do not delete or relabel them to obtain a
   passing result. No automatic deletion of the stand's raw source is allowed.
5. Stop the ongoing PC raw transfer. After fresh verification of the stand
   originals, remove only this task's PC raw duplicates and incomplete
   transfer payloads. Retain small cleanup receipts identifying paths, sizes,
   source bindings and the accepted policy. Historical two-copy receipts
   remain historical, with an appended withdrawal of the removed PC copy.
6. For future EXT007 work, keep raw computation and validation scratch on
   the stand. Remove disposable PC transfer payloads and superseded temporary
   artifacts after their required retained equivalents are verified. Keep
   source, qualified releases, useful build dependencies and provenance.

## Unchanged scientific and execution rules

No compression format, logical raw encoding, estimand, timestamp, working-set
definition, sample count, run duration, validity rule or selector changes.
The R2 study remains failed and its finite authorization consumed. This
storage decision authorizes no additional experimental invocation or retry.
Formal and diagnostic execution still require their own accepted plans and
exact authorization. Stage 18 and pilot custody are outside this exception.

## Adoption and validation

Record the owner's explicit acceptance separately, binding these exact bytes.
Then bind this policy to stand-side analysis and cleanup records. Verify the
existing stand originals before deletion and independently verify analysis
outputs before downloading. Keep failure evidence and record incomplete
states honestly. This is a durability-policy change, not a claim that a RAID
mirror or a manifest supplies the removed independent raw copy.

## Acceptance record

The owner explicitly approved “Approve stand-only raw storage and PC cleanup”.
The [original proposal and acceptance](../evidence/stage17/STAND-CUSTODY-D206-20261103-01/owner-acceptance.json)
are retained separately. Original proposal SHA-256: `c1d4d9cd0ec53b3aea9a4d8dd7b13c7b3f73552f1b475a4476b3b8a6ca10b92f`.
No additional experimental execution follows from this decision.
