# ADR-0059: Freeze prospective Q15-R containment limits

- Status: `ACCEPTED_POLICY_NO_EXECUTION_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-059
- Classification: resource, validity, and watchdog containment
- Decision owners: controller, platform, security, custody, and protocol owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no scientific behavior; supplies ADR-0048's open Q15 inputs
- Lifecycle gate: controller implementation and every Q15-R authorization

## Decision

Q15-R-P1 freezes a 14400-second authorization/session bound, 1800-second
active collection bound, independent 60-second start watchdog, u64-maximum
controller and worker pre-start poll bounds, 7200 CPU seconds, 2 GiB output,
128 artifacts, 16 MiB canonical frame payload, and 4 GiB primary quota.

The controller stops on the first binding, role, peer, platform, PMU/MSR,
integrity, canonicalization, custody, expiry, limit, or disconnect failure. It
retains partial evidence, never promotes it, and never retries. The u64 poll
bounds do not replace the external elapsed-time watchdog and introduce no
in-measurement poll limit.

Scientific effect: none because these are qualification containment bounds and
cannot be selected from treatment or outcome evidence. Any changed limit or
stop rule requires a new prospective record.
