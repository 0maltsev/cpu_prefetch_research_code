# D248: Prospective Q16b duration and repetition freeze

- Status: ACCEPTED by the owner in the current session
- Date: 2026-11-15
- Scope: future formal Q16b only; no change to collected Q16a

The owner selected **“Approve 1 second and 59 repetitions per cell”** in response
to the exact prospective question:

> Q16b needs its measurement duration frozen before collection. Approve 1 second
> per measurement with the required minimum of 59 repetitions in each of 60 cells
> (3,540 captures), keeping the existing 5-second warmup? This minimizes duration
> using the already successful 1-second Q16a window; Q16b’s rate estimate will use
> the approved D211 counting rule.

Freeze measurement duration to 1000000000 ns, warmup to 5000000000 ns, and the
planned count to exactly 59 repetitions in each of the 60 accepted cells. Preserve
D228's state/package/placement/working-set/repetition order and D035's existing
service-rate lower-limit estimator. D211's half-open completion interval remains
the numerator rule. All later drain observations remain retained for integrity.

One second is a prospective engineering/scientific input chosen by the owner
for the smallest approved duration. The completed Q16a window supplies practical
context, not an observed Q16b rate, precision guarantee or Q16b discovery study.
Neither an invalid result nor genuine low effective observations authorizes a
top-up or replacement. The first new experimental Q15/Q16 failure still stops
dependent work and requires reporting and restoration.

This supplies inputs intentionally left prospective by D035/D228. No statistical
method or immutable protocol text changes. Native sizing, prospective finite
resource/watchdog bounds, historical namespace reservation, shared archive
capacity and exact signed phase admission remain required before collection.
The earlier continuation-only isolation authority is not reused as a Q16b
authorization. This freeze alone grants no execution or Stage18 access.
