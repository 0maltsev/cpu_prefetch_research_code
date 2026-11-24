# ADR-0187: Retain the actual dequeued event during discovery demand capture

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-187
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: diagnostic backend integration primitive; no execution authority

The existing demand helper returns timing/trace status and advance counts but
discards the actual dequeued event pointer. A live discovery backend needs that
pointer to perform the unchanged immutable index/payload loads and rolling
checksum, retain independent consumer observations, and reconcile drain.
Inferring consumed records from producer selections would violate independence.

Add a discovery-only consumer helper returning both the demand capture result
and the queue's actual `DequeueResult`. Preserve the same exact acquire-load
clock boundaries and trace rules. Return the real status/pointer even when a
clock or trace failure is found after dequeue. Empty polls have no event. The
backend remains responsible for applying the ordinary validation/checksum to
every actual item, recording its independent ordinal, and stopping on mandatory
failure. No callback is executed inside the slot-demand timing interval.

Keep the original formal Q16a helper and action unchanged. This additive
primitive neither changes experiment design nor supplies a complete live
backend, event-observation contract, NUMA verification, or run authority.
The new header must be source-bound in the next prospective policy/release.

Verify real-ring success/empty and post-dequeue clock/trace failure, including
retention of the second distinct event when the trace is exhausted. Exercise
the real immutable arena's consumer action and relevant sanitizer matrices.

All 50 calibration cases pass under both development compilers and both
compiler ASan/UBSan and TSan matrices in the isolated accepted runtime.
Global formatting and the new unit's strict clang-tidy check pass. The
[verification record](../evidence/stage17/LOCAL-VERIFICATION-EXT007-20261102-01/consumer-and-release-checks.json)
binds the checked source bytes. No stand consumer capture was performed.
