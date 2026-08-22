# ADR-0043: Stage 17 entry runner, CPU-pair, and relax profile

- Status: `ACCEPTED`
- Date: 2026-08-22
- Decision owners: repository owner; platform, controller, timing,
  queue-correctness, storage, security, and custody owners at their later gates
- Protocol version: `2.0.0-pre.2`
- Supersedes: none
- Lifecycle gate: production-path implementation before any Stage 17 pilot

## Context and scientific constraints

Stage 16 proved the component software and deterministic preflight bundle but
had no selected worker pair, processor-relax mapping, or fail-closed production
runner profile. Hashed read-only topology evidence proves CPUs 0/1 are distinct
physical cores in the producer NUMA/LLC domain and CPUs 0/26 cross package,
NUMA, and LLC domains. It provides no dynamic qualification or performance
result. Q13 authorizes implementation only and explicitly withholds privileged
control, calibration, pilot, and confirmatory authority.

## Options considered

- Worker pair: `(0,1)` near and `(0,26)` far; reverse producer home; another
  eligible pair; remain unresolved.
- Relax: no instruction; one x86 `PAUSE`; yield/sleep; adaptive backoff.
- Runner: generic measured-loop dispatch; per-package executables; one
  controller with five static specializations; postpone integration.

## Decision

Select pair identity `XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1`: producer CPU 0
for both placements, consumer CPU 1 for `NEAR`, and consumer CPU 26 for `FAR`.
Select `X86-PAUSE-ONE-PER-RELAX-SITE-v1`, exactly one `_mm_pause()` at each
relax call and no adaptive or scheduler behavior. Select
`STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v1`: a controller-side choice among
five compile-time specializations and no package dispatch in the measured
executor.

Admission requires exact nonzero watchdog values and one immutable,
hash-verified, eligible, current-binding record for every runner dependency,
including separate pilot authorization. No field has a default. A diagnostic
field check cannot create the ticket that gates the static execution API.

## Evidence

- Q13 owner acceptance on 2026-08-22.
- Hashed topology set `STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01` and its
  verified aggregate SHA-256.
- Imported tight-poll, placement, one-attempt, static binding, and access rules.
- ADR-0001, ADR-0012, ADR-0016, ADR-0018, ADR-0020, ADR-0030 through ADR-0034,
  and ADR-0042.
- Focused pair/admission/dispatch/hash negative tests and dual-disassembler
  relax/mutant evidence are required from each affected release.

No queue outcome, latency, throughput, calibration, pilot, or confirmatory
observation selected the decision.

## Consequences and compatibility

The producer home remains fixed while the placement factor changes the
consumer context. Pair-specific clock, affinity, address-residency, atomic, and
platform qualification is still mandatory. Changing either CPU changes the
pair identity and invalidates all pair-bound evidence.

`PAUSE` becomes release identity and intentional extra work at every relax
site, but does not add an enqueue retry, blocking wait, timestamp, or memory
order. A different instruction or count is incompatible.

The static runner preserves package semantics. The current implementation
deliberately exposes no execution CLI; Q13 is not execution authority. The
Stage 16 preflight bundle remains unchanged. The real prefetch instruction,
combined affined worker, exact freeze inputs, full call-graph audit, and every
stand/pilot gate remain open.

## Verification and acceptance tests

- Exact near/far pair and five-package registry tests.
- Missing/duplicate/stale/mutable/ineligible/hash-mismatched evidence tests.
- Dirty build, binary, stand, binding, profile, relax, package, placement, and
  zero-limit negative tests.
- Non-symlink regular-file and SHA-256 verification before ticket creation.
- GNU and LLVM release disassembly showing one `PAUSE`; negative mutant with
  two `PAUSE` instructions and a scheduler call.
- Later full combined-worker source/call-graph/assembly, sanitizer, affinity,
  and no-allocation evidence before pilot.

## Rollback or supersession

Stop before worker creation on any mismatch and retain diagnostic evidence.
Never substitute another CPU, relax operation, evidence record, or limit. A
change needs a prospective superseding ADR, new identity, and complete
pair-/runner-bound requalification; old evidence remains under its identity.

## Protocol-amendment assessment

This selects platform and engineering mappings at delegated gates without
changing the imported logical schedule, queue, timestamp, storage, lifecycle,
or analysis semantics. No protocol amendment is required. Any future change
to those semantics still requires a versioned amendment.
