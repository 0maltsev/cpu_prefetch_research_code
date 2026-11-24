# ADR-0156: Stage 17 fixed-action executor kernel-thread tolerance

- **Status:** `ACCEPTED`
- **Decision ID:** D-156
- **Classification:** implementation correctness, latent defect in
  already-accepted production code, action-time reachability gap
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-007` fixed-action execution (Q16a/
  Q16b/Q16c) can be retried

## Context

The first real, live Q16a execution ever attempted in this engagement
(journal `standv2-20`, `/home/omaltsev/stage17-owner-evidence/stage17-
operational-evidence-standv2-20/`) reached `READY_FOR_STAGE17_PHASE_
AUTHORIZATION` (6 resolutions, 3 transitions -- itself a first), authored
and signed a real Q16a request (`verify-signature: PASS`), and ran the
real `execute-action` command against the stand. The real, underlying
708-capture hardware measurement completed in full: the worker's own
result document reports `terminal_state: "Q16A_CAPTURE_COMPLETE"`, all
1417 expected artifacts present (708 output + 708 trace + 1 hardware-
state file), and the failure record's own `recovery_readback` shows a
real MSR readback on CPUs 0/1/26 matching the known baseline exactly
(`restoration_verified: true`). A direct, independent, read-only MSR
check after the fact confirmed the same (`VERIFY_PASS`). Despite this,
`stage17-operational` reported overall `FAIL: primary supervisor failed
after fallback cleanup: empty or nonpositive NSpgid`.

Root-caused by direct code tracing, not assumed: this is the exact defect
ADR-0131 already diagnosed and fixed for the read-only-preflight chain
(`_identity_at` raising `SupervisorError("empty or nonpositive NSpgid")`
for any process that legitimately reports `NSpgid: 0` in `/proc/<pid>/
status` -- every kernel thread, always, on any real host). ADR-0131's
fix (`stage17_process_group_supervisor_v3.py`) was cascaded to the
read-only-preflight executor (`_v14.py` -> `_v15.py`) and the Q15 session
controller (`_v13.py` -> `_v14.py`), but never to the fixed-action
executor: `tools/stage17_fixed_action_executor_v4.py` still imports
`stage17_process_group_supervisor_v2` directly. This was never caught
before tonight for the same reason ADR-0131's own original defect wasn't:
every prior exercise of the fixed-action path ran inside a private PID
namespace where host kernel threads are not visible in `/proc` at all;
`standv2-20`'s live Q16a run is the first time this path has ever walked
a real host's own `/proc` tree.

The exact, deterministic call site: `cleanup_process_group` (`stage17_
process_group_supervisor_v2.py:455`) calls `identity_model.identity_for_
local_pid(leader_pid)`, which scans every PID under `/proc` via `self.
_identity_at(...)` with no retry wrapping -- unlike every other `/proc`
scan in that function (`_direct_children_fail_stop`, `_process_group_
members_fail_stop`), which are deliberately retry-wrapped because a
procfs read can be transient. With the unfixed `v2` model, `identity_for_
local_pid` is not merely likely but guaranteed to hit the first kernel
thread it encounters and raise immediately and fatally; kernel threads
(`kworker/*`, `ksmd`, `khugepaged`, etc.) are always present on a real
host. This is deterministic, not a race: confirmed via a synthetic-
fixture regression (feeding `_identity_at` and `identity_for_local_pid`
a kernel-thread-shaped status blob, `NSpgid: 0`, without touching real
`/proc`, since reading `/proc/1/ns/pid` requires `CAP_SYS_PTRACE` this
session did not have locally) reproducing the crash on `v2` and proving
`v3`'s existing, already-accepted fix tolerates it -- both for `_identity_
at` directly and for the exact `identity_for_local_pid` scan path that
failed live. Any retry of Q16a against `v4` unchanged would fail the same
way every time.

Because a function's free variables resolve against the module that
*defines* it, not the module that imports it (ADR-0126, ADR-0131), fixing
this is not a one-line import change: `_run_worker` and `execute_fixed_
action` are both defined in `stage17_fixed_action_executor_v4.py`'s own
body, and `stage17_phase_controller_v4.py`'s `execute_once` -- the only
place that calls `executor.execute_fixed_action`, inherited unchanged by
every successor through `_v14.py` -- closes over `v4`'s own `executor`
binding no matter which successor a caller imports. Monkey-patching `v4.
process_supervisor`/`v4.executor` from outside would silently change what
already-admitted resolutions' pinned hashes are supposed to guarantee,
without changing `v4.py`'s own file bytes -- undermining the exact
property the `runtime_closure` hash-pin exists to provide.

`standv2-20`'s own already-admitted `S17-EXT-001` through `S17-EXT-006`
resolutions pin `config/stage17/stage17-operational-evidence-admission-
policy-v41.json`'s current bytes (transitively, `tools/stage17_fixed_
action_executor_v4.py`'s and `tools/stage17_operational_cli_v11.py`'s
current hashes) forever, matching the exact precedent ADR-0131 itself
recorded for `pid_namespace_supervisor = v2`. This fix therefore cannot
make `standv2-20`'s existing chain executable; it only prepares a fresh
journal's own `S17-EXT-001` to admit the corrected entry points. Real
hardware safety for the `standv2-20` attempt itself was independently
confirmed via the failure record's own `recovery_readback` and a direct
read-only MSR check, both showing the real Q16a measurement work
completed and restored cleanly; no code correctness question here bears
on hardware safety.

## Decision

Add, as additive successors exactly as ADR-0131 established for this
same class of gap:

- `tools/stage17_fixed_action_executor_v5.py`: re-exports every `v4` name
  unchanged except `_run_worker` and `execute_fixed_action`, which are
  copied verbatim (confirmed byte-identical via `inspect.getsource`)
  except for importing `stage17_process_group_supervisor_v3` instead of
  `_v2`. `FixedActionExecutionError` is a fresh subclass of `v4`'s own,
  preserving `isinstance` compatibility up the chain.
- `tools/stage17_phase_controller_v15.py`: re-exports every `v14` name
  unchanged except `execute_once`, copied verbatim from `stage17_phase_
  controller_v4.py`'s own body except for importing `stage17_fixed_
  action_executor_v5` as `executor` instead of `_v4`. Confirmed via
  `inspect.getsource` diff that the copied body is textually identical to
  `v4`'s, and via `__globals__` inspection that `executor` now resolves to
  `_v5`, not `_v4`.
- `tools/stage17_semantic_verifier_v42.py`: re-exports every `v41` name
  unchanged (including `verify_input`'s own `S17-EXT-004`/`S17-EXT-006`
  dispatch, untouched) except `verify_policy_v42`/`verify_policy_v14`,
  which grow `v41`'s own `required`/`required_dynamic_action_bindings`
  sets by one entry each (`stage17_phase_controller_v15.py`, `stage17_
  fixed_action_executor_v5.py`) and expect `VERIFIER_VERSION = "42"`,
  matching exactly how `v41.py` grew `v40.py`'s sets by one entry
  (`_read_only_preflight_executor_v25.py`) rather than replacing them.
- `tools/stage17_state_journal_v36.py`: identical to `stage17_state_
  journal_v35.py` except importing `stage17_semantic_verifier_v42` as
  `semantic` instead of `_v41`; the same 5-level monkey-patch walk onto
  `stage17_state_journal_v16`'s own predecessor chain, confirmed via
  `stage17_state_journal_v12.semantic is v42` after import.
- `config/schemas/stage17-operational-evidence-admission-policy-v42.
  schema.json`: mechanical successor to `_v41`'s schema, changing only
  the five version-numbered `const`s (`$id`, `schema_version`, `policy_
  id`, `policy_version`, `entries[].verifier_version`) plus `predecessor_
  status`, matching exactly the five-line diff shape `_v40` -> `_v41`
  already established.
- `tools/author_stage17_policy_v42.py`: renders `config/stage17/stage17-
  operational-evidence-admission-policy-v42.json`, pinning `_v5.py`/
  `_v15.py`/`_v42.py`(semantic)/`_v36.py`(journal) plus `stage17_
  operational_cli_v11.py`'s edited hash into `runtime_closure`/`bindings`.

`tools/stage17_operational_cli_v11.py` is edited in place (`import
stage17_phase_controller_v14 as controller` -> `_v15`; `import stage17_
state_journal_v35 as journal_runtime` -> `_v36`), matching this file's
own established, already-repeated convention (27 prior in-place edits,
each re-pinned by a fresh policy generation) -- unlike `stage17_fixed_
action_executor_v4.py`/`stage17_phase_controller_v14.py`, which stay
byte-for-byte frozen precisely because their own functions' free
variables are what closed over the stale import, the exact asymmetry
`stage17_phase_controller_v14.py`'s own `journal_runtime`-walk docstring
already documents for a different binding.

`stage17_fixed_action_executor_v4.py`/`stage17_phase_controller_v14.py`
remaining reachable in the new closure is expected, not a drift signal,
for the same reason already documented for `phase_controller` v8/v9 and
`process_group_supervisor` v2/v3: `_v5.py`/`_v15.py` each import their
immediate predecessor to re-export everything but the one thing they
changed, so every older generation legitimately coexists. `stage17_q15_
session_controller_v14.py`'s own separate, direct import of `stage17_
fixed_action_executor_v4` (for `Q15-W`'s own action execution, a
different code path that has not been observed to hit this crash) is
deliberately left untouched by this ADR -- out of scope for the Q16a/b/c
`execute-action` reachability gap this fix closes; it remains a known,
separate latent risk for a future ADR if it is ever observed to fire for
real.

## Effects

Fixes the specific, real, reproduced crash that stops any fixed-action
`execute-action` (Q16a, Q16b, Q16c, and `STAGE17-BLINDED-PILOT`) from
ever completing successfully on any real, non-namespaced stand with
kernel threads visible in `/proc` -- which is to say, on any real stand
machine. No scientific design, hardware-safety mechanism, credential
handling, transport mechanics, or admission semantics for any `S17-EXT-
00N` input changes -- only which Python files a fresh journal's `execute-
action` loads at runtime, and which files a fresh journal's own `S17-EXT-
001` policy check requires present. This does not make `standv2-20`'s
existing chain executable (see Context above); a fresh `S17-EXT-001`
admission against this new generation is required before any real Q16a/
Q16b/Q16c retry.

## Verification and supersession

Acceptance requires, all confirmed for real this session (not
hand-waved): (1) `inspect.getsource` proving `_run_worker`/`execute_
fixed_action` in `_v5.py` and `execute_once` in `_v15.py` are textually
identical to their `_v4.py` originals; (2) `__globals__`/module-identity
inspection proving `_v5.py`'s `process_supervisor` is genuinely `_v3`
(not `_v2`), `_v15.py`'s `execute_once.__globals__["executor"]` is
genuinely `_v5` (not `_v4`), and `cli_v11.controller.execute_once.
__globals__["executor"].__name__ == "stage17_fixed_action_executor_v5"`
after `cli_v11.py`'s own edit; (3) a synthetic-fixture regression
(`NSpgid: 0` status blob, no real `/proc` access) proving `v2`'s
`_identity_at` raises and `v3`'s does not, and proving `v3`'s inherited,
unmodified `identity_for_local_pid` tolerates a kernel-thread-shaped
entry mixed into the same scan that crashed live; (4) `stage17_state_
journal_v12.semantic is stage17_semantic_verifier_v42` after importing
`_v36.py`, proving the monkey-patch walk actually reaches the real
`S17-EXT-001` handler; (5) `git diff` confirming no previously-accepted
file's bytes changed except `stage17_operational_cli_v11.py` (whose own
convention already accepts in-place edits re-pinned by a fresh policy
generation) and `stage17_operational_evidence_admission_policy_v41.json`
staying byte-for-byte untouched. Any later change to which process states
this scan tolerates, or to which entry points a fresh journal's `S17-EXT-
001` requires, needs another prospective successor under the same
standard applied since ADR-0108.
