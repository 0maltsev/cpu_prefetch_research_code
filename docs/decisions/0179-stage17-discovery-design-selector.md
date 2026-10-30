# ADR-0179: Discovery design enumeration and count-only selection

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-179
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: local software implementation of the owner-approved ADR-0178 design
- Lifecycle gate: no capture, operational evidence admission, or execution authority

## Decision

Implement the approved design as an offline, immutable 36-key enumeration:
H0/H1, near/far, and three working-set classes, each with the approved
100 ms, 1 s, and 5 s measurement horizons. Enumerate all H0 captures before
H1, placement then working-set within a state, and ascending candidate
duration within each context. This freezes diagnostic order only; it
changes no formal run order, seed, namespace, or registered estimator.

The selector consumes already-verified diagnostic facts, not arbitrary raw
files presented as operational proof. Require the exact planned prefix,
four independent nonnegative integer counts, explicit stop reason, and
observed elapsed time. A fixed-deadline result before its horizon or without
clock evidence is malformed; do not reinterpret it as an ordinary
insufficient-count result. A mandatory failure retains its prefix and stops
selection; subsequent captures are rejected. Missing, duplicated, reordered,
extra, or replacement captures cannot produce a selection.

Only the complete 36-capture family may select a duration. A candidate must
reach its fixed horizon and the approved 100,000-observation criterion in
every sequence of every context. Trace-capacity termination is ineligible,
even if counts already meet the minimum. Select the shortest qualifying
common duration; if none qualifies, remain unresolved without extending
or repeating the study. Successful and unsuccessful selection results
always deny execution authority and contribute zero formal runs.

## Boundaries

`stage17_q16a_discovery_v1.py --describe-design` describes the accepted
design and explicitly marks the operational plan incomplete. It supplies
no fabricated hardware values, resource budget, warm-up duration, seed
catalog, signature, qualification, capture result, or formal freeze. The
selector neither observes nor derives latency quantiles, `d2`, treatment
effects, or a throughput estimator. Its count inputs are not proof of
hardware correctness, residency, integrity, or source authenticity; those
must be established by the future diagnostic capture/admission path.

The design tool is not connected to the six-action production dispatcher
or policy v54. It cannot execute formal Q16a under a diagnostic label.
Capture duration/warm-up/reset, producer-home residency, finite resource
planning, qualified release, evidence verification, quarantine, and exact
signed diagnostic authority remain prerequisites before any live study.

## Verification

Thirteen synthetic tests cover the exact grid; shortest common candidate;
worst-context and all-four-sequence requirements; the N versus N-1 issue
interval boundary; insufficient counts; trace-capacity termination; missing
clock evidence and premature deadline claims; incomplete study; retained
mandatory-failure prefix and no continuation; malformed counts; exact order
and no retry/extra captures; and denial of execution/formal-run authority.
These tests are software verification, not diagnostic observations.
