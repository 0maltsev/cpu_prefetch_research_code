# cpu-prefetch-v5 Stage 17 audit, 2026-10-30

Disposition: **Stage 17 incomplete; calibration and pilot remain blocked.**

`audit.json` records a fresh read-only SSH inspection of `root@94.126.205.83`,
the actual validator command and its result, and sizes/SHA-256 values of the
retained journal, Q15 outputs, prepared Q16a inputs, exact candidate archive,
sidecar, and existing local admission wrapper. No credential bytes are included.

The existing wrapper was run as UID/GID 1000, the evidence owner's identity,
with the exact archive and sidecar. Running as root fails the transport-key
ownership gate; omitting archive locators fails EXT006. Neither gate was
disabled. The successful replay reports:

```json
{"current_state":"PREFLIGHT_ACCEPTED","missing_inputs":["S17-EXT-007","S17-EXT-008","S17-EXT-009","S17-EXT-010"],"pilot_ready":false,"resolutions":6,"transitions":2}
```

## Milestone evidence

| Input | Observed disposition |
| --- | --- |
| EXT001-003 | Admitted read-only authorization, preflight, owner acceptance |
| EXT004 | Admitted dynamic qualification |
| EXT005 | Admitted Q15-W result; retained output reports verified restoration and no quarantine |
| EXT006 | Admitted release/custody; exact archive and sidecar supplied during replay |
| EXT007 | Missing calibration results and accepted freeze |
| EXT008 | Missing admitted complete pilot plan |
| EXT009 | Missing admitted pilot storage/custody/recovery family |
| EXT010 | Missing exact phase authorization |

The six resolutions belong to v5-12. Later v5-13/14/15 attempts are separate
transactions; they do not erase or replace it. v5-14/15 failure records report
`S17-Q15R-MSR-READ` before sealed handoff. Devices for CPUs 0, 1, 8 are currently
root-owned mode 0600. This explains an access concern for UID 1000, but does
not independently prove every historical failure's cause. No permission was
broadened and no stopped attempt was retried.

## Before calibration

1. Integrate the existing 06_3EH mapping through the whole-plot MSR controller,
   actual CPUID verification, evidence schema selection, and Python admission
   closure. It still contains predecessor `{0,1,26}`/06_55H assumptions.
2. Resolve Q16a's unconditional PRFCHW check for the accepted T0-only platform
   form; verify both accepted forms without weakening unknown-platform gates.
3. Verify calibration memory preparation and residency against the paper's
   producer-home and working-set requirements. The prepared plan has 708
   captures and capacities 1024, 131072, and 8388608 for L2, LLC, and beyond-LLC
   classes respectively. Labels and sizes alone are not verified residency.
   Q16a currently constructs its event arena/ring on the controller thread;
   its capture path has no explicit producer-home page-placement verification.
4. Re-pin changed source/schema/controller bytes in a versioned release policy,
   produce and verify a clean candidate, and establish exact operational
   access and prospective authorization. Preserve all old attempts.
5. Complete Q16a/b/c, freeze their accepted results, then admit EXT007-009 and
   the exact EXT010 authority before executing the blinded pilot. Derive the
   exit chain from actual complete artifacts. Stage 18 remains separate.

The checked-in genesis still has zero resolutions. This audit does not import
the external journal as a new genesis or claim the server's evidence is the
development checkout's operational state. No pilot, calibration campaign,
informal timing trial, or hardware-control write ran during this audit.

## Local verification

ADR-0176 documents the bounded mapping-validation fix and its limits. The
new regression first failed on the original implementation for both the valid
06_3EH CPU set and the crossed predecessor set. After the correction, the
development runner suite passes 28/28 and the targeted Stage17FixedAction
suite passes 5/5 under GCC ASan/UBSan with LeakSanitizer disabled as prescribed.
The same targeted suite passes 5/5 under GCC TSan. The changed C++ files pass
the configured clang-format check, and `git diff --check` passes.
These are software checks only, not stand qualification or empirical results.
