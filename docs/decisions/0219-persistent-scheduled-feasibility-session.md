# ADR-0219: Persistent scheduled feasibility session

- Status: `ACCEPTED` — engineering implementation authorized in the current session
- Date: 2026-11-03
- Scope: Q16c scheduled lifecycle component; no experiment or execution authority
- Scientific sources: immutable pre.3 Sections 5.1–5.5 and accepted D036

Q16c replays the actual one-attempt/drop schedule. The saturation producer in
D210 cannot implement it: stopping at a duration would omit arrivals whose
handling became late. Calling the historical top-level scheduled executor
separately for warmup and measurement would create new worker threads.

The new typed scheduled driver reuses the existing start barriers, dedicated
termination controls, same-owner preparation/reset, prepared schedule view,
checked deadline translation, primary capture primitives and parked-worker
observation/join seams. One producer and one consumer remain alive through both
phases. The producer algorithm is separately implemented for a finite frozen
schedule; no saturation-loop reinterpretation or new worker pair is used.
All five packages use the same statically typed phase capture backend. Its
scheduled specialization disables the cold D211 completion counter entirely;
Q16c retains all accepted events through drain and has no completion-window
filter. Existing capture-failure semantics remain unchanged and ineligible.

The prospective plan records both source origins, source endpoints, offered
counts and distinct schedule/namespace identities, plus explicit phase,
poll, drain and barrier bounds. `PreparedScheduleView::horizon_ticks` is an
endpoint, so the elapsed duration is endpoint minus source origin. The bootstrap
warmup schedule has an exact five-second horizon. The measurement horizon is
explicitly supplied. Schedule IDs, RNG derivation, source custody hashes,
schedule-family validity and decoded-deadline checksums remain mandatory
admission/independent-validation bindings; this component does not invent them.

Owner preparation supplies the actual immutable mapped deadline arrays.
Only after both owners are ready does the controller obtain and validate
those views, before releasing either phase. The arrays must match declared
counts, source origin/endpoint and the accepted nondecreasing half-open
schedule grammar. They remain alive and unchanged across drain/reset; no
schedule or permutation regeneration occurs. Execution never substitutes a
parent-heap array for the prepared mapped view.

For source deadline `s`, source origin `o` and actual released phase origin
`t0`, the target is the checked integer `t0 + (s-o)`. The raw producer row
stores that translated `a_i` in the same clock domain as its capture samples;
the original immutable source schedule remains retained separately. Lateness
does not move the deadline. Every planned arrival receives exactly one attempt,
including arrivals handled after the nominal horizon, subject only to the
explicit mandatory failure/watchdog bounds. FULL is retained and never retried.

Section 5.5 requires immediate release-publication of `arrivals_finished`
after the final scheduled attempt. The driver does not delay that flag until
the nominal horizon. The consumer's terminal empty poll must follow an acquire
that observed publication, preserving the final-enqueue race guarantee.
Both workers then park, observations and integrity checks complete, the same
queue resets in place, and those same owners enter the next start barrier.
No controller hold is added after early completion.

The fixed five seconds describe the warmup **schedule horizon**, not a claim
that owners actively executed for five wall-clock seconds. Sparse schedules
may finish earlier; late handling/drain may finish later. Retain the actual
released origin, producer post-publication completion sample, consumer terminal
checkpoint and controller checkpoint. `all_arrivals_attempted` and offered
count are separate from the factual `deadline_reached` flag. The latter can
legitimately be false on a successfully completed scheduled phase.

Mandatory during-phase native observations are unchanged. An empty/sparse
phase cannot waive them, fabricate worker activity or relabel an after-phase
read as during-phase evidence. Provably invalid prospective inputs fail before
collection: in particular, D036 explicitly rejects zero-offered measurement
runs. No minimum offered count is invented for warmup. A nonempty schedule's
last nominal deadline preceding an observation offset does not itself prove
impossibility, because handling can be late; the actual native observation
gate still fails closed if either worker has finished. Neither failure permits
replacement, reseeding or repetition through this component.

D036 uses independent run-cluster fractions and requires the prospective
common-marginal schedule family and run-generation process. It does not, by
itself, mandate one persistent mapping lifetime across separate feasibility
runs or paired temporal blocks. This component establishes only within-run
warmup-to-measurement persistence. It makes no cross-run pairing or mapping
claim; the accepted family, hardware whole-plot and ordering contracts remain
external requirements.

Targeted verification exercises all five packages, actual origin translation,
ties and late attempts, immediate completion with an early warmup end, normal
drain, unchanged arena/order, same-owner reset, absent D211 output, mapped
schedule mismatch, zero-offered measurement rejection, sparse/empty warmup
observation failure, reset failure and one-shot storage. Relevant strict and
sanitizer checks are coordinated with the native integration owner. Synthetic
results support software verification only, not empirical performance claims.
