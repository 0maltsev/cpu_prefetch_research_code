# Q16c private custody repair verified; continuation remains stopped

D291 repairs the metadata namespace mismatch that stopped D288. The original
failure, authority and restoration records are preserved. No experiment,
qualification, full-prefix custody pass or independent raw validation was
restarted. EXT007 and Stage17 remain incomplete.

The repaired retained-prefix helper has SHA256
`40fe2f8d35f442b841ce3c80aa4e4d1758d1cd9737cad84b860924b38428e0cf`.
It clones the unchanged capture-registry bodies into one private globals scope
using the authenticated private archive/custody types. The complete-prefix and
failed-diagnostic paths share that scope. Original byte, physical identity,
ledger, native checkpoint and scientific gates remain in place. The historical
archive runtime, measured code and all original data are unchanged.

Verification:

- **Eight focused tests passed**, including four new boundary tests. They load
  hash-bound source bytes through the real private archive loader and reopen a
  real eight-artifact custody ledger with independently imported dataclasses.
  Complete custody succeeds; failed native completion remains rejected by the
  ordinary reader and receives diagnostic-only status in the incident adapter.
  Wrong sizes/hashes, corrupt archives and corrupt ledger records are rejected.
  Verification leaves archive/metadata/ledger bytes unchanged. The separate
  suffix public-store inventory boundary also passes.
- **130 integration tests verified across the initial run and correction.**
  The initial run passed124 and had six environment errors: its existing archive
  fixtures used the3.43GB-free `/tmp` tmpfs, below their failure-reserve gate.
  Those six tests passed after setting TMPDIR to the repository disk, which had
  about312GB free. No production gate was changed. Both original failure output
  and corrected output are retained; no tests were skipped. Suites include
  custody registry, metadata adapters, execution scope, raw-analysis software,
  source/signature compatibility, supervisor sequence and policy63.
- The UID1000 stand probe used the original authenticated archive profile
  `c15d54de37bfe2cfe99d5c3d2d13e0853d77aac6eb743e87b5c510b9a61fabc0`.
  For original checkpoint and receipt pairs at ordinals0 and86, it reproduced
  the foreign-type rejection and passed the scoped `_bound` read. This verifies
  the exact failed boundary against actual retained metadata. It opened zero
  raw archive streams, opened no ProgramStore transaction and grants no custody
  inventory or scientific validity credit. The probe script SHA256 is
  `96bb3a340890ebe1bc947b551a87e98a7d793c64344d7ca7c7385da222589751`.
- Changed Python sources compile. Exact policy63 and preflight37 rendering
  checks pass. A structural JSON comparison confirms the policy delta is only
  the retained-prefix helper's runtime-closure binding. `git diff --check` passes.
  No C/C++ behavior changed; native sanitizers/codegen were not rerun or claimed
  as new evidence for this Python namespace repair.

At **15:01:14UTC (18:01Moscow),19November2026**, the original service remained
failed with MainPID0/exit1. Independent recovery remains verified with no errors;
all87 checkpoint/receipt pairs remain. The prefix analysis root and new-family
preparation root are absent. Stand free space is6,300,581,347,328bytes. The actual
86-prefix raw validation and94 new captures still have zero completed reports
and zero new captures respectively. Q16a708 and Q16b120 remain preserved.

[D292](../../../decisions/0292-q16c-metadata-stop-continuation-proposal.md)
proposes one explicitly approved continuation after this metadata-only stop,
retaining the original scientific design and all evidence. Its exact SHA256 is
`97bb720c84699f1b2bf8c71cd9152b32d2a137a527d3e80c8455902a618bdd5a`.
Planning estimate6–9h after launch, total ceiling11h54m20s; software preparation
precedes the clock. D288 explicitly prohibits a second day/automatic retry, so
the new proposal is not an execution authorization. No successor release or
fresh window is claimed ready. Owner acceptance and exact fresh authority
implementation/packaging must precede any launch.
