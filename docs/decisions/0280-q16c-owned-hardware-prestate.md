# D280: own Q16c hardware prestate through deferred capture

Engineering repair under the owner's instruction to continue after the D279
native stop. This changes cold software lifetime, not scientific design or
hardware acceptance. It grants no fresh experiment, retry or deadline.

The sealed-source Q16c parser callback receives the family's three-CPU prestate
array by value. Its parsed capture previously retained a span into that local
copy. Deferred capture therefore used expired stack storage. Immediate sizing
checks ran while the copy was alive and did not expose this defect. Q16a/Q16b
use direct parser function pointers and retain the original family-owned array;
their accepted observations and qualification histories remain unchanged.

`ParsedNativeFormalScheduledCapture` now copies the supplied hardware prestate
into an owned vector before returning from parsing. Its stored native plan has
no borrowed prestate span; `plan()` rebinds that span to the current parsed
owner, including after copies/moves. Environmental paths retain their existing
documented lifetime. No value is synthesized and no measured plan, runtime
layout, clock, MSR acceptance, schedule, count, deadline or loop changes.
The additional tiny allocation occurs during cold parsing, before hardware
entry or measurement; native mapping sizes are unchanged.

A focused regression mutates the parser's input buffer, leaves its scope,
copies/moves the parsed owner, checks all accepted CPU/value pairs and calls
the real pure native layout calculation. The prior implementation fails and
throws `native formal capture prestate has no accepted H0/H1 plan`; the repair
passes. All136 runner tests and23 scheduled-input/publication ASan/UBSan checks
pass with stack-use-after-return detection enabled and the repository's
required `detect_leaks=0` under ptrace. This is software verification only.

The actual D279 checkpoint records exception13 before any mapping/session/raw
publication but discards the exception text. The diagnosed lifetime defect is
confirmed; attribution of that particular thrown exception remains an inference.
Preserve the first attempt, empty archived checkpoint, custody receipt and
restoration as failures, never successful Q16c data.

Before another stand attempt, create and verify a clean corrected release and
explicit source-bound continuation record. Keep old source qualification and
data identified by their actual producers. Authenticate any reuse of original
unobserved schedules against their signed generation proof and exact unchanged
generator closure. Do not rewrite old receipts, reset D277, repeat completed
Q16a/Q16b/raw validation or launch without a full fitting finite ETA. Any new
qualification is for the changed actual executable only and must stop/restore
on its first failure. Stage18 remains prohibited.
