# Q15-R P4-R-C D-105 through D-108 runtime decision bundle

Status: **`PROPOSED_EXACT_ACCEPTANCE_REQUIRED_NO_KEY_OR_STAND_AUTHORITY`**

Machine record SHA-256:
`6d753cee3d1dc6892df29171914ac42849440bb61bb9ba3686637823cf926e11`.

## Why this decision is required

Clean commit `dc643df498fa36c3c34507f977634c05421751b1`
implements the D-100 through D-103 repository-local P4-R-C preparation. Its
executor SHA-256 is
`0b7e2f1c65849abe7d29ed8fd91fabb6105b8977d3051b9947ac7346fc14bdf6`.
The implementation uses fixed absolute stand commands for `/usr/bin/env`,
`/usr/bin/python3`, and `/usr/bin/dd`, plus Python tar/compression modules.

D-102 says tool bytes are compatibility identity. D-099 captured the host,
kernel, root filesystem, and storage identity but did not capture these runtime
tools or modules. Treating them as an ordinary implicit platform default would
contradict the accepted fail-closed rule. The executor therefore keeps its
runtime-acceptance constant null and refuses to open the transport even if a
syntactically issued action record is supplied.

## Recommendations

### D-105 — acquire runtime identity rather than waive it

Select one separately signed, read-only runtime identity capture followed by a
separate review. Do not accept an unpinned runtime and do not mutate the stand.
The later capture must bind the exact host/transport, fixed collector bytes,
commands, stdin program, limits, UTC window, output paths, and one-attempt
disposition.

### D-106 — disclose the single-owner waiver

Extend the already disclosed role collapse for exactly one runtime capture and
review. The review must state `distinct_reviewer=false` and may not be called
independent. This preserves the accepted critical impersonation and
misuse-detection risks; it does not claim that those controls are satisfied.

### D-107 — fixed read-only acquisition graph

Implement only a repository-owned, fake-tested collector with pinned OpenSSH,
local `shell=False`, fixed absolute command strings and fixed stdin bytes, an
empty fixed remote environment where applicable, bounded complete output, one
target SSHSIG, one attempt per observation, zero retry, append-only local
evidence, and stop-first failure. No generic command selector, interactive
shell, fallback, mutation, installation, or cleanup is permitted.

The exact observation graph and script bytes will be frozen by the
implementation successor after acceptance; this decision does not invent
stand output or claim runtime compatibility.

### D-108 — complete reviewed evidence before successor

Only a complete canonical capture and separate single-owner review may resolve
the runtime gate. Evidence must cover the selected absolute executables,
interpreter/version metadata, imported module paths and hashes, tar/compression
dependencies, and loader/dependency observations. Partial evidence is retained
but ineligible. An accepted capture then feeds a clean executor successor; it
does not itself authorize P4-R-C.

## Scope if accepted

Acceptance would authorize only repository-local ADRs, a fixed read-only
runtime collector, schemas, fake/negative tests, and still-unissued
authorization/review templates. It would not authorize target-key use,
signature or authorization issuance, stand access, runtime collection, stand
mutation, D-104 P4-R-C, P5, Q15, controls, calibration, pilot, measurement, or
confirmatory work.

After the implementation is clean and hash-bound, a later exact action gate
must separately authorize one target-key SSHSIG and one read-only stand capture.
After review and acceptance of those immutable bytes, another clean successor
and another separately signed and approved P4-R-C action are required.

## Exact approval required

> Q15-R-P4-R-C-D105-RUNTIME-D — accept D-105 through D-108 exactly as
> recommended in decision-input SHA-256
> 6d753cee3d1dc6892df29171914ac42849440bb61bb9ba3686637823cf926e11,
> bound to clean commit dc643df498fa36c3c34507f977634c05421751b1,
> D-099 complete-evidence SHA-256
> afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241,
> and D-104 executor SHA-256
> 0b7e2f1c65849abe7d29ed8fd91fabb6105b8977d3051b9947ac7346fc14bdf6.
> Select one signed read-only runtime-identity capture and separate review,
> extend the disclosed single-owner waiver for that capture/review, freeze an
> exact pinned OpenSSH command/stdin-script graph with one attempt and zero
> retry, and require complete canonical reviewed runtime evidence before a
> clean executor successor. Authorize repository-local acceptance/ADR/
> collector/schema/fake-test/template implementation only. Do not use keys,
> sign or issue authorization, access or modify the stand, execute the
> collector, prepare or execute P4-R-C, or perform P5/Q15/platform-control/
> calibration/pilot/measurement/confirmatory work. Every key, stand, and
> execution step requires a later separately signed and explicitly approved
> authorization.
