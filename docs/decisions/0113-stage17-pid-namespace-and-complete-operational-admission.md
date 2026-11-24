# ADR-0113: Stage 17 PID-namespace identity and complete operational admission

- **Status:** Accepted for repository-local implementation; no operational
  authority
- **Decision ID:** D-STAGE17B-001
- **Classification:** engineering, platform-control, security, custody, and
  lifecycle governance
- **Owner:** repository, platform, pilot, custody, and protocol owners
- **Gate:** before any new Stage 17 stand workflow
- **Protocol:** `2.0.0-pre.2` (unchanged)

## Context

The policy-v8 process supervisor mixed namespace-local identifiers used by
`waitpid()`/`killpg()` with identifiers exposed by the PID namespace that owns
the `/proc` mount.  In a nested PID namespace this could falsely report a
quiescent transport family.  Policy v8 also intentionally admitted only
S17-EXT-001 and S17-EXT-006; the remaining external-input semantics,
production phase controllers, Stage 17 exit, and Phase 18 handoff were absent.

## Options considered

1. Require identical local and procfs-visible IDs.  Rejected: this excludes a
   supported Linux isolation arrangement and does not prove group identity.
2. Continue comparing `/proc/*/stat` IDs directly to syscall IDs.  Rejected:
   this is the confirmed fail-open defect.
3. Map every process through `NSpid` and `NSpgid`, bind the PID-namespace
   inode, retain the waitable leader until group quiescence, and fail closed
   when mapping or procfs evidence is unavailable.  Selected.

## Decision

The current Stage 17 policy uses a versioned supervisor that distinguishes
namespace-local PID/PGID from procfs-visible PID/PGID.  It validates the
namespace inode and full `NSpid`/`NSpgid` chains, rejects ambiguous or changing
mapping, ignores equal numeric IDs from a foreign namespace, holds the leader
waitable while signalling and observing descendants, and reaps only after the
group is proven gone.  Syscalls receive only namespace-local IDs.  Procfs
unavailability, denial, malformed data, or namespace drift blocks before an
attempt marker or enters fail-stop cleanup after child creation.

One successor semantic policy registers production verifiers for all ten
external inputs.  Evidence is admitted only by exact byte/hash/size checks and
input-specific closed-world invariants.  Signed action requests are distinct
from post-action resolutions.  Fixed Q15/Q16/pilot controllers verify their
own authority and actual runtime bytes.  A separate append-only exit machine
models pilot completion and prepares—but never issues—Phase 18 authority.

The repository-local single-owner pilot role collapse remains explicit:
`distinct_auditor=false` and `independent_review=false`.  It does not weaken
the Phase 18 access chronology.  No Stage 17 record authorizes a Phase 18
transition.

## Scientific effect

None.  This decision changes evidence admission and process ownership only.
It does not change queues, workloads, schedules, timing, estimands, calibration
formulae, treatment labels, or analysis.

## Compatibility effect

Policies v1 through v8, action plans v1 through v6, runtimes, schemas,
protocol snapshots, D-099 through D-108, graph/catalog/genesis v1, and journal
snapshots remain immutable.  Policy v9 binds them as predecessors and is the
only current production-admission policy.  Existing attempt markers from any
predecessor version continue to consume the one-shot action.

## Consequences and risks

- A host without readable, stable PID namespace/procfs mapping cannot execute
  the action; this is intentional fail-closed behavior.
- Synthetic fixtures can demonstrate software semantics but do not resolve an
  external input or establish stand readiness.
- Real stand evidence and separately issued bounded authorizations remain
  mandatory.

## Supersession rule

Any change to PID mapping, signalling/reaping order, evidence semantics,
authority verification, fixed actions, Phase 18 chronology, or one-shot rules
requires a new prospective ADR and versioned successor.  Scientific changes
require a protocol amendment.
