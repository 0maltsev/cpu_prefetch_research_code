# EXT007 prerequisite qualification checkpoint, 2026-11-03

Outcome: **BLOCKED_AT_CLOCK_QUALIFICATION**. No Q15-R/W execution,
discovery capture, or formal calibration followed this failure.

The owner's privileged public-JSON search completed at effective UID 0:
98,268 JSON files, zero errors, zero matches for the three D124 receipt
families within the explicitly declared scope. The independent stand search
covered 33,022 files with zero errors or matches. The combined record retains
the separate Git-history search, exact scope, exclusions and hashes. These
are not whole-disk or no-incident claims. A fresh D124 attestation passed
EXT001 admission in the new v5-18 namespace.

The immutable clean release is source
`817c6522e3954efce53797e2bcc202a3bfc5d9af`, archive SHA-256
`df47dab36a85de010df337011beabf37eff411090f68cfdcaa5e498bacc6d6ff`.
Fresh read-only preflight passed all six observations. Journal 000006 has
EXT001/002/003/006 admitted and two transitions, state PREFLIGHT_ACCEPTED.
The earlier v5-17 authoring/admission failures remain on the stand; no
failed draft was rewritten into a pass.

## Actual clock qualification

One fixed-count near-pair capture ran from 07:13:53Z to 07:15:54Z using
the release clock qualification tool, SHA-256
`0ccefc493c48de378f4611570e6839dabbb0a7589d2c09caad3e63e734961f8d`.
The command, prospective 600-second timeout, start/end times, exit code 1,
raw output and stdout/stderr hashes are retained. There was no timeout.
Both CPUs had 100,000 prime reads and 10,000,000 deltas. Counts, affinity,
read status, monotonicity and the cross-core evaluator passed.

| Criterion | CPU 0 | CPU 1 | Accepted limit |
|---|---:|---:|---:|
| p99.9 delta | 0.078 us | 0.077 us | <= 1 us |
| p99.999 delta | 12.579 us | 12.593 us | <= 10 us |
| Maximum delta | 305.767 us | 28.013 us | Diagnostic only |
| Regressions / equal adjacent readings | 0 / 0 | 0 / 0 | 0 / <= 10 |

The exact failed criterion is the p99.999 limit on both CPUs. The production
evaluator and D009 agree; no threshold, count or acceptance rule changed.
This capture does not qualify the build/platform/pair. No fresh capture or
alternative CPU pair was substituted.

Cause is **NOT_ESTABLISHED**. The retained operator logs show that EXT006
admission/status and Q15-R request/authorization preparation overlapped the
clock capture. No affinity restriction was applied to those operator
processes. The post-failure read-only inventory shows no CPU isolation/nohz,
schedutil governors, clocksource tsc, unchanged boot, and unrestricted
ordinary process masks. These observations identify possible interference;
they do not establish what caused any captured outlier. Post-failure process
and interrupt snapshots are not during-capture disturbance measurements.

Q15-R request/signature preparation completed, with authority ending
07:45:12Z. Signature verification explicitly reported action NOT_EXECUTED.
Do not use expired authority or start Q15-R while this clock gate is blocked.

## Retention and next decision

`inventory.json` records every retained file's exact size and SHA-256.
`stand-v18/` files were transferred without compression, decoded and checked
against the stand-side size/hash. Their original bytes remain on the stand;
this directory is the verified PC copy. Private signing keys are absent.

The current six-step EXT007 plan remains at Step 2. An explicit prospective
remediation/requalification plan is needed before another clock capture;
the failed result remains retained and cannot be reclassified. Any proposal
must keep the selected clock, CPU identities, counts and accepted limits,
specify exact stand controls/readbacks/restoration, and bound fresh attempts.
The failed capture supplies no permission to repeat until a pass occurs.
