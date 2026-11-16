# D267: complete D260 transport lease and one restoration reserve

- Status: ACCEPTED engineering correction within the approved D260 window
- Date: 2026-11-16
- Scope: prelaunch control transport; no measurement or native limit changes

Independent prelaunch review found that signing the exact55860-second native
family ceiling as the entire authority lease leaves no allowance for signing,
signature verification, isolation preparation and owner admission. The original
D260 proposal retained the65040-second authority ceiling. Use a private v3
controller policy with a57600-second signed session lease, below that original
ceiling. Keep the exact plan,55860-second native watchdog, all per-capture limits,
sample counts, seeds, archive controls and scientific checks unchanged.
The new policy must be identical in authoring and original signature/UTC
verification, without mutating qualified/historical modules. Authenticate it
through a separately published packet3; preserve packets1/2 and their checks.

Before collection, require enough actual signed lease for the full55860 native
seconds plus600seconds of bounded controller admission/transport. Reserve56460
seconds from the collection command, retain the13500-second analysis allowance,
and retain exactly1800seconds of combined infrastructure/final reporting reserve.
This tightens the latest collection start to13:45:23UTC16November; the original
window and its recorded13:55:23UTC native-only cutoff remain unchanged.
The supervisor enforces the stricter derived cutoff; no clock is reset.

The1800-second reserve is shared once: at most1680seconds for bounded isolation
restoration before analysis and120seconds for final reporting. Analysis may use
its full13500seconds and must finish before the final120seconds; never withhold
a second1800-second reserve after spending restoration. Native hardware/worker
cleanup retains its original120-second limits. Verify actual terminal hardware
restoration, and check the executor's actual `stage17-q16b-attempt-v6.json`
marker when a required terminal receipt is absent.

Any unused first signed authority remains preserved. It may be superseded only
before a native attempt: require its original successful signature-preparation
receipt, the same registered empty family, unchanged namespace and registration
evidence, no attempt or terminal record, and actual ledger/quota state. Create
fresh request/authorization/attempt/session identities with the same103 planned
run identities and source-bound plan. Retain an explicit old/new authority
binding record. This renews no consumed authority and repeats no namespace
registration, qualification, capture or raw validation. The actual family has
one execution attempt; any failure stops without an automatic retry.

No empirical result, Stage17 completion or Stage18 authority follows.
