# ADR-0120: Stage 17 post-preflight controller compatibility

- **Status:** `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- **Decision ID:** D-120
- **Classification:** implementation correctness and version compatibility
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before T2, Q15, Q16, pilot, or Stage 18 preparation

## Context

ADR-0119 made the read-only preflight path persistable under semantic policy
v14, preflight policy v11, journal runtime v12, CLI v6, and executor v9.  The
phase controller remained v4 and imported journal runtime v10, which loads
semantic policy v12.  Consequently an otherwise valid policy-v14 journal could
complete the first read-only transition but could not be consumed by the
post-preflight controller.  Reusing a policy-v12 controller after admitting
policy-v14 evidence would be a fail-open version mix.

## Decision

Add a prospective compatibility successor:

- semantic policy v15 and semantic verifier v15;
- journal runtime v13;
- phase controller v5;
- Q15 session controller v3; and
- operational CLI v7.

Policy v15 preserves the immutable graph, catalog, genesis, record schemas,
scientific protocol, fixed actions, worker, output registry, executor, and
preflight policy v11.  It binds the exact successor Python closure.  Controller
v5 delegates unchanged action semantics to controller v4 but replaces its
journal dependency with journal v13 before any preparation or action.  Q15
controller v3 and CLI v7 similarly replace only their controller/journal
dependencies.  They expose no synthetic production switch and grant no
authority.

An EXT001 envelope v11 admitted through preflight policy v11 remains valid:
the append-only journal records do not encode an admission-policy pathname,
and both journal v12/policy v14 and journal v13/policy v15 independently re-read
and semantically validate the same exact evidence bytes.  Executor v9 continues
to use journal v12 for the one read-only preflight.  All later production
controller admission uses journal v13/policy v15.  No record is translated or
rewritten.

## Scientific and compatibility effects

There is no scientific effect.  No factor, treatment, schedule, estimator,
hardware value, calibration output, pilot result, or Stage 18 access rule is
changed.  The compatibility effect is fail-closed: controller v4 remains an
immutable predecessor and cannot consume the current journal; controller v5
accepts only a journal that independently passes policy v15.

## Evidence and acceptance

Acceptance requires a persisted external-journal regression that:

1. admits EXT001 and T1 through the production CLI;
2. reloads the exact journal under both the preflight runtime and journal v13;
3. proves controller v5 is bound to journal v13 while controller v4 remains
   bound to journal v10; and
4. reaches complete six-program preparation with zero marker and transport.

The clean pilot-candidate bundle must bind and contain policy v15 and every
successor runtime.  Stand access, preflight execution, privileged controls,
calibration, pilot, and Stage 18 remain separately authorized.

## Supersession

Any action, authority, trust, output, or scientific change requires a new
prospective ADR.  A future runtime correction must preserve this policy and
all predecessors byte-for-byte.
