# ADR-0210: Persistent service warm-up session core

- Status: `ACCEPTED` — engineering implementation authorized in the current session
- Date: 2026-11-03
- Protocol snapshot: `2.0.0-pre.3/`, unchanged
- Scope: independent component and synthetic verification; no formal dispatch or release qualification

Protocol Sections 5.3–5.5 require a continuous-ready service workload with real
warm-up, drain, logical reset and persistent mappings. The current formal
worker skips non-pilot warm-up. A summary flag cannot establish those facts.
This decision implements a reusable prerequisite without connecting it to
`stage17_fixed_action.cpp`, changing the running archive, or collecting data.

`run_service_session` accepts explicit phase durations, producer-attempt and
consumer-poll bounds, drain deadlines and barrier bounds. There are no empirical
defaults. One producer and one consumer prepare once and remain alive across
both phases. The clock, phase capture backends, package, preparation, observer,
thread launcher and all storage are caller-owned. The core introduces no queue
algorithm or package-specific branch inside an attempt. Tests instantiate the
existing R0/R1/R2/L0/L1 packages and their real raw-capture/checksum backend.

Each phase starts from an actual controller clock read released through the
existing start barrier. The producer remains continuously ready until its
absolute deadline and release-publishes `arrivals_finished`. The consumer keeps
polling through drain; it accepts an empty result as terminal only when the
poll follows an acquire that observed `arrivals_finished`. This preserves the
final-enqueue race guarantee without stopping the consumer at the producer's
deadline. Explicit bounds fail closed, never extend or retry the phase.

After warm-up both workers park. The controller retains after-phase observations,
checks count reconciliation and backend integrity, and invokes the queue's
in-place quiescent reset. Each same worker then resets its private logical
state and enters the measurement barrier. No queue, arena, order, raw buffer,
thread or mapping is replaced by the core. The reset callback must preserve
ring empty slots/cursors, linked sentinel/recycler order, immutable records and
all persistent mappings; production composition must independently establish
those facts. Measurement receives a fresh origin after those handshakes.

The consumer checks the clock again after the terminal empty poll, outside the
capture brackets, and requires successful nondecreasing time strictly before the
existing drain deadline. After parked-worker observations, the controller retains
a cold post-drain clock checkpoint at least as late as both owners' last samples,
with unchanged clock origin. The next phase origin must not precede that checkpoint;
clock ties are permitted. Cold monitoring/checkpoint time is not charged against
the consumer drain deadline. These guards prevent a late terminal poll or an
inter-phase clock reversal from becoming a successful session.

Results retain clock origin, observed/released phase origins, explicit duration,
checked producer/drain deadlines, actual clock statuses, preparation/reset and
observation outcomes, and drain-inclusive lifecycle counts. The capture backend
must share the same clock instance/origin throughout; controller checks reject
origin drift. No interval-throughput numerator or completion endpoint comparator
is implemented here. D211 and its independently versioned cold classifier are
separate from this component; the total consumed count remains for reconciliation.

The storage is one-shot and externally placed. Two distinct existing dedicated
termination controls are supplied by the caller; their current constructors
allocate cold storage, and this core makes no native placement claim for it.
The controller frame, callbacks, worker stacks/TLS, queue/node regions, records,
raw buffers and control/monitor storage still require explicit native layout,
placement, page-policy and observation integration before formal collection.
Callback finiteness and no allocation/I/O in capture/reset remain interface
obligations, not facts inferred from successful preparation. Thread launch may
allocate cold; successful starts must remain joinable and be reaped before the
captured objects die. Finite native process watchdog/recovery remains external.

Failures preserve available counters and reject measurement after failed warm-up,
drain, validation, observation or reset. No partial failure is converted to
success or restarted. A successful component result supplies no admission,
scientific validity, source qualification or experiment authority. Actual Q16b
parameters, all versioned input/output contracts and formal native dispatch
remain future integration work under their own accepted inputs.

Verification covers real package operations and separate warm-up/measurement
streams, same-worker preparation/reset, retained addresses and immutable records,
linked sentinel/FIFO reset, the final-enqueue/empty-poll race, resource limits,
clock failures/overflow, observer failures, partial thread starts and one-shot
storage. Allocation instrumentation covers owner loops and logical queue reset;
where the accepted Clang TSan runtime cannot link global allocation replacements,
only that instrumented assertion is explicitly skipped and functional tests stay
active. Targeted sanitizer and strict format/static evidence is retained under
`build/stage17-step3-prep/d210-verification/`; synthetic evidence has no empirical
performance meaning. No protocol bytes or existing scientific controls change.
