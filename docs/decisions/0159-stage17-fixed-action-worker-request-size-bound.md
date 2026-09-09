# ADR-0159: Stage 17 fixed-action worker request-size bound

- **Status:** `ACCEPTED`
- **Decision ID:** D-159
- **Classification:** implementation correctness, latent capacity limit
  in already-accepted production code, action-time reachability gap
- **Owner:** repository/build/runner owner
- **Gate:** before any real `Q16b` `execute-action` can be retried; a
  new pilot-candidate release and a fresh journal's `S17-EXT-001`
  through `S17-EXT-006` admission are both required downstream of this
  fix (see Effects)

## Context

The first real, live Q16b execution attempt in this engagement
(journal `standv2-26`) reached a fully signed and verified authorization
(`verify-signature: PASS signature=VERIFIED action=NOT_EXECUTED`) after
a first, separate size gate was found and fixed in-memory (see below),
then failed for real on `execute-action`: `stage17-operational: FAIL:
fixed worker returned 1`. The worker's own preserved stderr (`stage17-
q16b-stderr-v4.bin`, written by the executor before raising, per its
own existing `WORKER_NONZERO` handling) reads verbatim: `runner: FAIL:
fixed dispatcher request read failed`.

Root-caused by direct code tracing, not assumed. Two independent size
gates exist on the same underlying request document, in two different
layers:

1. Python: `tools/stage17_phase_controller_v2.py`'s `MAX_BOUND_INPUT_
   BYTES = 16 * 1024 * 1024`, enforced by `_read_binding`/`_read_
   unbound_regular`, called from `prepare_action` (`stage17_phase_
   controller_v4.py:421`, inherited unchanged by every successor
   through `_v15.py`) against the authorization's `request_binding`.
   This layer was found first (`verify-signature` failing with `fixed
   request exceeds its fixed size limit`) and fixed for that specific
   signed authorization via an in-memory-only monkey-patch (`stage17_
   phase_controller_v2.MAX_BOUND_INPUT_BYTES = 64 * 1024 * 1024`, a
   scratchpad wrapper never committed, since `stage17_phase_controller_
   v2.py`'s bytes are individually hash-pinned in the already-admitted
   `policy-v44.json` for `standv2-26` and editing them on disk would
   have deadlocked the journal exactly as ADR's own `standv2-25`
   precedent already established for a different file). `verify-
   signature` then passed.
2. C++: `src/runner/stage17_fixed_action.cpp`'s `kMaximumRequestBytes =
   16 * 1024 * 1024`, the default `maximum_bytes` argument of `read_
   regular_fd`, compiled directly into the worker binary and enforced
   independently when `run_fixed_action_worker` reads the request via
   its own `--request-fd` (line ~3963). This layer has **no** safe
   in-memory equivalent: it is baked into the exact worker binary whose
   `binary_sha256` is already admitted into `S17-EXT-006`'s `release_
   binding` and embedded in every signed Q16b runner_admission ticket.
   It is what actually stopped the real, live attempt.

Both gates were calibrated around Q16a's own scale (708 runs, one
shared package, ~9-12MB serialized) and never revisited when Q16b's
matrix was designed. Q16b's own real requirements force a much larger
request: `_validate_q16_matrix` (`tools/stage17_phase_controller_v4.py:
134-189`) hardcodes `packages = ("R0","R1","R2","L0","L1")` and requires
every one of the resulting 60 `(package, hardware_state, placement,
working_set_class)` cells present in a single action's `runs` list,
while `package_capture`/`load_sealed_runner_ticket` (`stage17_fixed_
action.cpp:2080`/`1237`) require each of those 3540 runs to carry its
own complete, literal `runner_admission` object (~10-11KB, 21 evidence
entries) -- the object's own bytes are re-canonicalized and re-hashed
per run, so there is no shared/deduplicated reference a smaller request
could use instead. `708 * 5` packages worth of per-run ticket embedding
is an architecturally forced ~35-47MB regardless of JSON formatting
choices; this was confirmed directly against the real, signed
`standv2-26` authorization, whose own `request_binding.size_bytes` is
`37045716`.

An investigation into whether Q16b could instead be split into 5
separate per-package submissions (avoiding any size-bound change at
all) found this is not a safe, small alternative: `S17-EXT-007`'s own
manifest verification (`tools/stage17_operational_semantics_v8.py`, via
the shared `_phase_family` helper, `tools/stage17_operational_semantics_
v4.py:622-679`) calls `_one(artifacts, "Q16B_REQUEST")` etc., and `_one`
(`stage17_operational_semantics_v4.py:462-466`) hard-fails unless
exactly one artifact of that role exists. Making `S17-EXT-007` accept a
family of five per-package Q16b results instead of one would require
redesigning `_phase_family` itself, which is shared, unmodified code
also used by `Q15-R`, `Q15-W`, `Q16a`, `Q16c`, and the pilot action --
comparable in scope to fixing the size bound directly, but with real
regression risk against every other fixed action, and no established
precedent in this codebase for a one-of-many result family. Raising the
compiled bound is the smaller, better-isolated change.

## Decision

Raise `kMaximumRequestBytes` in `src/runner/stage17_fixed_action.cpp`
from 16MiB to 64MiB, matching the existing `kMaximumWorkerBytes` bound
already used elsewhere in the same file for a differently-purposed but
comparably-sized bound (reading the worker's own `/proc/self/exe` for
self-verification). This single constant is the default for `read_
regular_fd`, so it also raises the equivalent bound on `--context-fd`
reads at every call site (`Q15-R`, `Q15-W`, `Q16a`, `Q16b`, `Q16c`, and
the blinded-pilot session); none of those other action's real request
or context documents are anywhere close to even the original 16MiB
bound, so this is not expected to change their behavior.

Unlike the Python-tool-file fixes this engagement has used to date
(ADR-0156 through ADR-0158's additive-successor-plus-cascade pattern),
there is no equivalent "leave the old bytes frozen, add a new file"
option for a single compiled worker binary: any source change produces
a new `binary_sha256` by construction. This fix is therefore a direct,
in-place edit to `stage17_fixed_action.cpp`, requiring a full new
release cycle rather than an in-place tool-file cascade.

## Effects

`standv2-26`'s existing chain cannot be salvaged by this fix: its
already-admitted `S17-EXT-002`/`S17-EXT-003`/`S17-EXT-006` resolutions,
and all 5 signed Q16b runner_admission tickets, pin the *old*
`binary_sha256` (`19fbc5d00dc2e77a527ead2483ff5fe968e71d62001adab0c599
f46ddebf074b`). The signed `standv2-26` Q16b authorization is separately
non-retryable regardless (`retry_allowed: false`, and its own attempt
marker, `stage17-q16b-attempt-v4.json`, was already written by the real,
live `execute-action` failure). A fresh pilot-candidate bundle must be
cut from a new, clean commit containing this fix, and a fresh journal
must redo `S17-EXT-001` through `S17-EXT-006` admission against the new
`binary_sha256` before any Q16b (or Q16a/Q16c/pilot) `execute-action`
can run again. No scientific design, hardware-safety mechanism, queue
semantics, timing unit, or admission *semantics* changes -- only how
many bytes the worker will read from a `--request-fd`/`--context-fd`
before refusing.

## Verification and supersession

Acceptance requires: (1) the real, live `standv2-26` failure record
above (`fixed worker returned 1`, stderr `fixed dispatcher request read
failed`), confirming this is a real, reproduced defect and not a
hand-waved concern; (2) direct code inspection confirming `kMaximumRequest
Bytes` is `read_regular_fd`'s only size gate on the worker's own request/
context reads, and that no other compiled bound independently
duplicates or would still block a ~35-47MB request after this change;
(3) confirmation, at the time a new pilot-candidate bundle is cut, that
the rebuilt worker's `--validate-admission` diagnostic path and the full
existing regression matrix still pass unchanged for `Q15-R`, `Q15-W`,
`Q16a`, and the pilot action, none of which is expected to exercise the
new headroom. Any later request-shape change large enough to approach
the new 64MiB bound (for example, a future `Q16c`/pilot design that also
requires all packages embedded per-run at Q16b's own scale) needs
another prospective bound review under the same standard.
