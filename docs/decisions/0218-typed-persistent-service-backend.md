# ADR-0218: Typed persistent service capture backend

- Status: `ACCEPTED` — engineering implementation authorized in the current session
- Date: 2026-11-03
- Scope: Q16b backend component and synthetic verification; no execution authority
- Scientific rules: D035, D210 and owner-accepted D211 remain unchanged

The historical formal Q16b path creates a single measurement session and reports
drain-inclusive consumption. It does not supply the required persistent warmup
or D211 interval numerator. The D210 session core and D211 cold counter already
implement the necessary lifecycle and endpoint rules. This decision composes
them with the existing typed capture primitives without changing historical
dispatch, raw codecs, queue operations, prefetch primitives or timing boundaries.

`FormalServiceSessionBackend<Clock, Preparation>` infers the concrete package
from `Preparation::package()`. Instantiation is restricted to R0, R1, R2, L0
and L1. There is no package switch in an attempt or poll. The preparation
provider owns the queue, immutable arena, package, two run identities and
separate producer/consumer phase states. Its actual mappings, queue/node order,
package distance, seed, placement and resource budgets remain explicit inputs
of the future qualified native composition.

The backend prepares both phase streams on their actual owners. D210 retains
the same workers and mappings, completes ordinary consumer drain, parks both
workers, validates the warmup primary join and checksum, and invokes the same
queue's in-place quiescent reset. Each owner checks its still-fresh measurement
state and performs its preparation provider's private reset/readback before
the fresh start barrier. No queue, package, immutable record order or worker
is replaced. Required five-second warmup and prospective bounds must be
enforced by the admitted formal plan; this reusable component supplies no
empirical parameter defaults.

Each producer call uses `timing::capture_due_producer_attempt`; each consumer
call uses `timing::capture_dequeue_poll`. The wrapper retains the exact current
capture result and raw append status. Only a successful committed observation
advances the retained primary-prefix counts. Invocation counts are separate.
Existing timing-capture failure semantics are preserved: a clock failure may
leave no observation after a queue operation, and a dequeue-completion clock
failure may occur before the checksum action. The wrapper does not reconstruct
an outcome, fabricate a row, repeat the operation or repair the checksum.
The lifecycle's failure-return outcome is not evidence of an actual FULL.
Failed current evidence and the independent raw prefixes remain available;
the phase stops and cannot supply a valid service-rate observation.

At quiescence, the existing independent primary reader reconciles run identity,
accepted ordinals, actual record selection, timestamp order, complete drain and
the immutable consumer action. Both streams are then sealed. Only a joined
measurement phase invokes `count_service_interval` using its actual released
origin sample, unchanged exact clock domain and prospective plan duration.
The result is retained in the consumer phase state, separate from total
drain-inclusive consumption. A valid zero numerator remains valid. FULL is
retained data and remains a separate zero-loss decision. No interval count,
filtering, additional timestamp or quantile calculation enters the hot loop.

Failed preparation, capture, retention, observation, reset, join or interval
validation prevents a successful session. Unfinished streams are sealed
incomplete after join. Complete raw bytes that subsequently fail cold interval
validation remain complete bytes but provide no valid numerator or eligible
run. The backend does not establish hardware controls, source qualification,
artifact custody, execution admission or formal-family sufficiency.

The typed phase capture interface also accepts the existing scheduled
`ProducerAttempt` and consumer ordinal seam. Q16c can reuse these phase states,
capture primitives and native mappings. It requires a separate persistent
scheduled lifecycle: calling the existing top-level measurement executor again
would create new workers and would not establish persistent warmup/reset.
This decision neither implements nor authorizes such a scheduling substitution.

Targeted tests cover all five real packages, unchanged prefetch calls and
primary joins, same-worker preparation/reset, retained arena identity, exact
D211 end boundaries and valid zero throughput, existing clock-failure behavior,
raw-capacity failures, failed reset/observation, corrupt checksum and invalid
origin. Relevant sanitizer and strict source checks are coordinated with the
native integration owner before release. These are software-verification
fixtures, not experimental performance evidence.
