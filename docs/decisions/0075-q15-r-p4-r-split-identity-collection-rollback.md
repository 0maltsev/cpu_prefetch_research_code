# ADR-0075: Split Q15-R-P4-R identity from one-shot collection

- Status: `ACCEPTED_REPOSITORY_LOCAL_TEMPLATE_FREEZE_NO_STAND_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-075
- Accepted by: Q15-R-P4-F
- Decision owners: protocol, platform, security, release, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; refines the future P4-R operational graph without issuing it
- Lifecycle gate: before the first identity command, stand mutation, transfer,
  extraction, self-test, or collection

## Context and scientific constraints

The 2026-08-22 inventory is reference evidence, not fresh transaction
identity. Combining identity, transfer, collector execution, repair, retry, or
cleanup in one approval would allow stale lineage and would destroy the
independent review boundary. Partial evidence must survive failure.

## Options considered

1. separate read-only P4-R-I identity acquisition and stop for review, then a
   separately signed P4-R-C for create-exclusive staging and one collection;
2. treat stale inventory as current authority;
3. use an omnibus action with retry, repair, or cleanup; or
4. remain blocked.

## Decision

Freeze two non-collapsible future gates:

- `Q15-R-P4-R-I` contains exactly four fixed read-only argv vectors, captures
  fresh identity and pinned-host evidence, and stops for independent review.
  It authorizes no mutation, transfer, self-test, or collector execution.
- `Q15-R-P4-R-C` must bind the accepted fresh identity and review hashes,
  satisfy P4-K and a new signed authorization, execute the exact thirteen
  ordered verification actions, transfer once, and invoke the collector at
  most once through fixed argv and environment. Retry count is zero.

Freeze eleven stop-condition groups and rollback profile
`Q15-R-P4-R-STOP-RETAIN-NO-DELETE-v1`: pre-mutation failure leaves the stand
unchanged; post-mutation failure stops and retains exact partial staging and
custody bytes. Deletion, overwrite, rename/reuse, automatic cleanup,
activation, and restoration claims are forbidden.

Both successor records remain templates. Neither gate is issued, signed, or
authorized, and no automatic continuation exists.

## Evidence

- P4-R v2 preparation SHA-256:
  `f8c63d1f95d69c6a9562cfec6d2635757c9dbba80137d68fdedf56bd189b6ba4`.
- Decision bundle SHA-256:
  `18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604`.
- Q15-R-P4-F acceptance SHA-256:
  `ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`.
- The accepted collector contract and P4-R limits require fixed commands,
  bounded output, first-failure stop, partial preservation, and zero retry.

## Consequences and compatibility

Scientific effect is none; the graph produces platform eligibility evidence
only. Compatibility effect is exact: gate split, predecessor hashes, action
order, fixed commands, limits, one-attempt rule, stop groups, retention, and
rollback semantics are transaction identity.

## Verification and acceptance tests

Checks reject gate collapse, automatic continuation, stale or absent identity,
changed commands/order/limits, retry, shell/glob/inherited environment,
deletion, cleanup, activation, fabricated hashes, and any operational authority
in the templates.

## Rollback or supersession

Any graph, command, order, retry, timeout, verification, stop, retention, or
rollback change requires prospective supersession. Failed and abandoned bytes
remain append-only evidence; cleanup requires a separate exact authorization.

## Protocol-amendment assessment

No protocol amendment is required. The decision strengthens fail-closed
qualification governance and does not alter measurement or inference rules.
