# ADR-0052: Freeze the Q15 probe and collector contract

- Status: `ACCEPTED`
- Date: 2026-08-24
- Decision ID: D-052
- Classification: platform qualification and scientific-treatment verification
- Decision owners: protocol, platform, timing, queue, compiler, security, custody,
  and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: the unresolved probe/collector-definition input in ADR-0051; it
  does not supersede any Q15 authority or implementation requirement
- Lifecycle gate: before a Q15 qualification-tool release and before Q15-R

## Context and constraints

The imported protocol requires independent behavioral evidence that the H0/H1
hardware-prefetch states are distinguishable for a regular stream and, where
possible, for pointer-dependent access. It also requires exact clock, atomic,
CPU, residency, software-prefetch, MSR-prestate, and independent-readback
evidence. ADR-0051 intentionally left those definitions unresolved.

The contract must fail closed without choosing a favorable empirical effect
threshold. It must not confuse a timing diagnostic with treatment-state
verification, claim that all speculative fetching is disabled, or turn a
pointer-dependent nonresponse into invented evidence.

## Options considered

1. Accept MSR readback alone.
2. Use an elapsed-time or estimated effect-size threshold.
3. Use an exact raw PMU event with binary H0/H1 criteria, integrity checks, and
   an explicit pointer-dependent `where possible` classification.
4. Leave all probe and collector semantics unresolved.

## Decision

Select option 3. The exact machine-readable contract is
`config/q15/q15-probe-collector-contract-v1.json`, contract ID
`Q15-PROBE-COLLECTOR-CONTRACT-v1`.

- The candidate scope is Intel family 06/model 55H, CPUs 0/1/26, near pair
  0/1, far pair 0/26, 64-byte lines, and 4096-byte verified base pages.
- Linux `perf_event_open` programs raw `L2_RQSTS.ALL_PF`, EventSel `0x24`,
  UMask `0xf8`, config `0x000000000000f824`, per-thread on singleton
  affinity, user-only, pinned, non-inherited, and non-multiplexed.
- The working set is
  `ROUND_UP(2*VERIFIED_LOCAL_LLC_BYTES,VERIFIED_BASE_PAGE_BYTES)`. Allocation,
  target-node first touch, and one priming pass precede the single counted
  pass. The counted traversal permits no allocation, I/O, software-prefetch
  instruction, or page fault.
- The regular probe performs one volatile 64-bit demand load per cache line in
  ascending order. Integrity, H0 counter greater than zero, and H1 counter
  equal to zero are jointly mandatory.
- The pointer probe performs one dependent 32-bit next-index load over one
  deterministic cycle containing every line. The order uses
  `FISHER-YATES-PHILOX4X32-10-v1` and the exact recorded seed. Integrity and H1
  zero are mandatory. Positive H0 is `DISTINGUISHED`; zero H0 is
  `NOT_DISTINGUISHABLE_WHERE_NOT_POSSIBLE`, not a false claim of distinction.
- Elapsed time is retained as diagnostic evidence only and is never subtracted
  from the counter or used as an acceptance threshold.
- The seven exact collectors cover selected-pair clock qualification,
  atomic/layout facts, actual CPU/migration, address residency, the software-
  prefetch mapping, complete MSR prestates, and independent post-apply/restore
  MSR readback.
- H1 qualification follows H0 baseline, one-CPU apply, independent complete-
  value readback, H1 probes, complete restore, and independent restoration
  readback. Partial evidence is retained append-only.

This decision freezes contracts only. It does not assert that probe or
collector executables exist, authorize dynamic execution, authorize MSR reads
or writes, or constitute Q15-R/Q15-W authority.

## Evidence

- Explicit owner instruction on 2026-08-24 to freeze the exact contracts and
  authorize one Q15-S1 commit and clean no-authority bundle build.
- Imported protocol `EXPERIMENT_IMPLEMENTATION_SPEC.md`, SHA-256
  `8488f9d3870b620b0b4f15cb1f47c2eb7ab3ecb8b15fc09603047dc379a5912c`.
- Candidate preflight and topology hashes recorded in the contract.
- Intel Performance Monitoring Events Guide 335279 and Intel's official
  Skylake-X core-event table for `L2_RQSTS.ALL_PF`.
- Repository schema/semantic mutation checks; no probe, collector, stand, PMU,
  or MSR execution.

## Scientific and compatibility effects

Scientific effect: the accepted H0/H1 qualification gate is conservative and
binary for the registered PMU event. It changes no package, workload,
measurement path, estimator, or experiment outcome. Pointer-dependent evidence
is reported honestly under the protocol's `where possible` qualification.

Compatibility effect: contract ID and SHA-256, event encoding, probe byte/code
identity, generated-code audit, collector implementations, executable hashes,
working-set derivation inputs, raw evidence, and authorization records become
qualification identity. A different event, threshold, traversal, seed,
collector acceptance rule, or candidate scope is incompatible.

## Verification and acceptance tests

The Draft 2020-12 schema and semantic validator require all frozen values,
verify local evidence hashes, reject altered scope/event/privilege/multiplexing/
fault/timing/probe/collector/artifact/authority semantics, and explicitly prove
that every implementation and authority flag remains false.

Future executable implementation must add positive, negative, fake-backend,
fault, sanitizer, and generated-code evidence. A clean bundle containing this
contract remains no-authority and cannot claim dynamic qualification.

## Rollback or supersession

Never rewrite an executed contract or its evidence. A material contract change
requires a new contract ID, superseding ADR, clean tool release, new prospective
Q15 authorization, and requalification. A scientific meaning change also
requires a versioned protocol amendment. Failure to implement or satisfy this
contract leaves the stand ineligible.

## Protocol-amendment assessment

No amendment is required. This decision makes the imported behavioral and
evidence requirements executable without changing their scientific meaning.
