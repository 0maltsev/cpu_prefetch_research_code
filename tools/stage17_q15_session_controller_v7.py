#!/usr/bin/env python3
"""Re-exports `execute_session` alongside the unchanged `main` re-export.

`execute_session` has lived unchanged in `stage17_q15_session_controller_
v2.py` since that version and is still what the real `main()` CLI
entrypoint calls internally today -- confirmed by tracing `main` through
every successor (`v3` through `v6` each just re-export `predecessor.main`
unchanged; `v3` first defines it as `return predecessor.main()`, meaning
the real implementation has stayed in `v2.py` the whole time). No version
from `v3` onward ever re-exported `execute_session` itself as a top-level
name, only `main`. This is not a behavior fix: `execute_session`'s
internal calls resolve `phase_controller.*` through `v2.py`'s own
module-level global, which every successor's reassignment loop (continued
here unchanged) already keeps pointed at the current phase-controller
regardless of which module the caller imported. This file only exposes
that same, unchanged, already-correctly-wired function as a direct
top-level attribute, for callers that need to invoke a Q15 session
in-process with a live Python callback (e.g. interleaving Q15-W
preparation mid-session) rather than through `main()`'s argv-based CLI
entrypoint, which cannot accept such a callback.
"""

import stage17_phase_controller_v10 as phase_controller
import stage17_q15_session_controller_v2 as _v2
import stage17_q15_session_controller_v6 as predecessor


module = predecessor
for _ in range(5):
    module.phase_controller = phase_controller
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

main = predecessor.main
execute_session = _v2.execute_session


if __name__ == "__main__":
    raise SystemExit(main())
