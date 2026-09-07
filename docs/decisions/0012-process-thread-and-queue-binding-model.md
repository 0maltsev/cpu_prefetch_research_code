# ADR-0012: Process, thread, and queue-binding model

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Runtime topology / measured-path binding
- Decision owners: Repository owner; architecture owner; controller owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; failure/cache-ownership proof due before data-plane acceptance

## Context and scientific constraints

Stage A has exactly one producer and one consumer, private observation buffers, strict timed-path work, and separate privileged/custody boundaries. Queue selection must not add measured dispatch or obscure package-specific behavior.

## Options considered

1. One measurement process with controller plus producer/consumer threads.
2. Separate worker processes with IPC.
3. Runtime polymorphic queue dispatch.
4. Compile/link-time, direct, or separate-binary binding.

## Decision

Use one unprivileged measurement process. Its controller main thread prepares and launches the run, then remains quiescent during the timed horizon; exactly one producer and one consumer worker execute the data plane. Privileged control and validation custody remain outside the process. Bind the queue at compile/link time or by separate binary/direct binding, with no measured-path virtual dispatch or treatment-selection branch.

## Evidence

The repository owner accepted Q2 on 2026-08-17. This topology satisfies the protocol's worker count and ownership constraints without adding hot-path IPC and is compatible with the accepted three-plane architecture.

## Consequences and compatibility

Scientific effect: preserves fixed worker semantics; binding is not a treatment. Compatibility effect: each package/build specialization is independently identified, tested, and disassembled; crash behavior and handoff are process-specific.

## Verification and acceptance tests

Prove worker/cache-line ownership, controller quiescence, exact thread count, affinity, crash/lifecycle publication, privilege absence, static/direct binding, and negative detection of dispatch/treatment branches.

## Rollback or supersession

A topology or binding change requires a superseding ADR plus renewed failure, cache-ownership, generated-code, timing-boundary, and privilege evidence.

## Protocol-amendment assessment

No amendment is required.
