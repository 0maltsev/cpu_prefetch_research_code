#!/usr/bin/env python3
"""Real Q15 session-controller successor fixing a second, distinct real
crash class: `SupervisorError: empty or nonpositive NSpgid`.

`stage17_process_group_supervisor_v3.py` (ADR-0131) already fixes this
exact error -- a real, live process (a kernel thread) that legitimately
reports `NSpgid: 0` in `/proc/<pid>/status`, which `v2.py`'s own
`ProcfsIdentityModel._identity_at` does not tolerate. But
`stage17_q15_session_controller_v10.py` -- the module `execute_session`
actually lives in, per `v12.py`'s own patch -- still does `import
stage17_process_group_supervisor_v2 as supervisor` at its own module
level, and `supervisor.SupervisorLease()`/`supervisor.cleanup_process_
group(...)` inside `v10.py`'s functions resolve that name against
`v10.py`'s own globals at call time, not against whichever module
imports `v10`. A real Q15-R+Q15-W live-pairing session on the real
stand hit this for real: the actual MSR H1-apply/H0-restore cycle
completed and was independently verified safe (real readback matching
the sealed H0 prestate on all three CPUs), but the post-action cleanup
walk crashed on this exact, already-fixed-elsewhere bug before a real
`Q15_W_RESULT` document could be written.

Fixes it the same "reassign the attribute on the module that actually
reads it" way `v12.py` already fixed `execute_session` itself:
`_v10.supervisor = process_group_supervisor_v3`. `v3` re-exports every
name `v10.py` needs from `supervisor` (`SupervisorLease`, `cleanup_
process_group`, `SupervisorError`, etc.) unchanged except the two real,
targeted subclass overrides (`ProcfsIdentityModel`, `SupervisorLease`)
that actually fix the crash -- `cleanup_process_group` itself is
`predecessor.cleanup_process_group` verbatim, and picks up the fix
polymorphically through whichever `ProcfsIdentityModel` instance
`SupervisorLease.enter()` (now `v3`'s own override) actually
constructs, not through its own module identity.
"""

import stage17_process_group_supervisor_v3 as process_group_supervisor_v3
import stage17_q15_session_controller_v10 as _v10
import stage17_q15_session_controller_v12 as predecessor

_v10.supervisor = process_group_supervisor_v3

module = predecessor
for _ in range(6):
    module.phase_controller = predecessor.phase_controller
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

main = predecessor.main
execute_session = predecessor.execute_session


if __name__ == "__main__":
    raise SystemExit(main())
