# ADR-0117: Durable Stage 17 pilot session and independent Phase 18 trust

- Status: Accepted
- Date: 2026-08-28
- Classification: implementation/governance
- Owner: implementation owner; protocol owner for the D-116 dependency
- Gate: Stage 17 stand handoff

## Context

The predecessor v3 action boundary imposed one 180-second deadline on the
whole pilot, while the complete 180-cell, repeated plan and mandatory warm-up
cannot fit in that interval.  It also allowed worker-authored summaries to
stand in for independently decoded raw observations, and the Phase 18
readiness path did not require an independently pre-admitted public-key
fingerprint.

D-116 and protocol `2.0.0-pre.3` prospectively resolve the pilot warm-up
bootstrap: pre-freeze pilot/calibration runs use exactly five seconds only to
estimate run-specific dependence; later work uses the frozen conservative
rule.  No pilot outcome is confirmatory.

## Options considered

1. Retain one 180-second pilot process.
2. Remove deadlines for the pilot.
3. Use one bounded durable session containing independently marked,
   authorized, append-only run attempts, each with a 180-second deadline.

## Decision

Select option 3.  Policy v12 binds protocol `2.0.0-pre.3`, the complete v4
pilot plan, deterministic schedules, the v4 worker/controller closure, and the
independent raw-stream decoder.  The session lifetime is derived from the
frozen plan; it cannot be extended implicitly.  Every run has its own durable
attempt and terminal record.  Partial sessions retain evidence and never
complete Stage 17.

Q15-R/Q15-W remain one supervised retained session.  Q16 and pilot actions use
the release identity admitted by EXT006; Q15 uses the earlier clean identity
observed and owner-accepted through EXT002/003, and EXT006 must later prove
byte equality.

Stage 17 completion is derived only from the admitted EXT010 bytes, controller
attempt/result/completion, durable pilot-session completion, sealed full-run
manifest, and independently decoded raw observations.  A valid `FULL` stays
valid data and separately fails zero loss.

Phase 18 requires an external trust-anchor record whose exact bytes and actual
OpenSSH public-key fingerprint were admitted independently of Stage 17.  A
readiness request without that input remains blocked.  Every Phase 18 access
transition has its own detached signature and strict predecessor chronology;
Stage 17 authority cannot advance it.

## Scientific effect

No treatment, estimand, factor, schedule family, repetition count, or
confirmatory access rule changes.  D-116 is the only scientific amendment and
is confined to prospective warm-up bootstrap.  Independent decoding prevents
worker summaries from altering validity or zero-loss semantics.

## Compatibility effect

Policies and action records before v12/v4 remain readable but are not current
production authority.  Pilot bundles use profile v4 and protocol
`2.0.0-pre.3`.  Test-only bundles are byte-classified and cannot satisfy a
production EXT006 resolution.

## Supersession rule

Any change to the session deadline derivation, raw layout, warm-up rule,
action set, trust root, or Phase 18 chronology requires a new ADR and, where
scientific meaning changes, a versioned protocol amendment.
