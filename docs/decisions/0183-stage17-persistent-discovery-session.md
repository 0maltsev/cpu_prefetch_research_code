# ADR-0183: Persistent discovery workers and phase coordination

- Status: `ACCEPTED`
- Date: 2026-11-01
- Decision ID: D-183
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: EXT007 engineering continuation under ADR-0178
- Lifecycle gate: local component verification; no diagnostic or formal action authority

## Decision

Coordinate the bounded capture and drain components with two persistent
worker threads. Create both threads before preparation and warm-up, retain
the same threads and backend storage through measurement, and join them
after completion or cancellation. Thread creation, arena reallocation,
remapping, payload retouch, and sample-buffer regeneration are not part of
the warm-up-to-measurement transition.

Require explicit positive warm-up/measurement durations, attempt capacities,
drain duration/capacity, and barrier poll limit. This API supplies no default
scientific duration, numerical platform observation, namespace, or authority.
In particular it cannot override pre.3's five-second pre-freeze formal
calibration/pilot warm-up rule or select the formal D-037 duration.

Both workers must prepare successfully and reach the existing release/acquire
start barrier before the controller publishes a common warm-up origin.
Retain observed clock values separately from origins actually released to
workers; an overflowing window retains its real clock observation and starts
no capture. Failed preparation, clock failure, or exhausted barrier polling
cancels both barriers and preserves the available prefix.

Workers publish their independent warm-up results before any validation or
drain. The consumer waits for both publications, validates only the now
quiescent traces, and performs the bounded real-ring drain. Only validated
warm-up plus reconciled drain and verified ring reset permit private logical
reset. Consumer and producer reset their own state on their original worker
threads; both must reach a separate measurement barrier. A rejected private
reset remains a warm-up failure, not a valid transition or a fabricated
measurement start.

Measurement uses a new common released origin and separate cancellation
state and result slots. After both measurement workers are quiescent, the
consumer validates traces and performs final drain without resetting the
measured ring cursors. Clock/capture/validation failures remain failures even
when recovery drains successfully. Trace-capacity exhaustion remains an
insufficient result with its prefix retained, never a complete measurement
or permission to extend. No minimum-count selection or quantile computation
occurs in a worker loop.

Preparation and post-capture exceptions cancel both barriers and join the
threads while retaining already published results. Thread-start failure also
cancels and joins any worker that did start. The backend receives const views
of worker results during validation and cannot replace their observed stop
reasons through that interface.

## Verification and limits

Eleven real-ring tests with synthetic time exercise successful persistent
coordination and reconciliation; rejected/throwing preparation; origin-clock
failure; failed warm-up validation; both private-reset failure directions;
warm-up drain clock failure; actual observed-origin overflow; measurement
clock failure; measurement trace capacity; invalid plans; and a post-capture
exception after both workers publish. A regression exposed the private-reset
failure classification and was corrected. Worker identity checks cover
private resets and consumer drain ownership. Real OS thread-creation failure
is handled in source but is not claimed as fault-injection-tested evidence.

This is a backend-driven coordination component, not a stand measurement
executable. The live backend must still establish and independently verify
affinity, NUMA/page policy/residency, actual consumer action and integrity,
namespaces/seeds, frozen resource controls, and raw retention. A finite
process watchdog and exact signed diagnostic admission remain mandatory;
bounded polling cannot interrupt a stuck clock or backend callback. The
existing formal Q16a action and immutable protocol snapshots remain unchanged.
Future release qualification must bind this header, its changed library
dependency, and the completed live backend under a new qualified policy.
