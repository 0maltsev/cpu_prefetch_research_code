#!/usr/bin/env python3
"""Fixed-action executor successor completing ADR-0161: chains
`stage17_fixed_action_executor_v6.py`'s own ADR-0160 durable-session
deadline fix together with `stage17_output_registry_v5.py`'s ADR-0161
offered-count frozen-plan cross-check fix.

`execute_fixed_action` (defined once, in `stage17_fixed_action_
executor_v5.py`, patched by `v6.py`) reaches `output_registry.
validate_worker_result(...)` via a fresh attribute lookup on the real
`stage17_output_registry_v4` module object every call -- the identical
"no further rebinding needed" pattern `v6.py`'s own docstring already
used for `execute_fixed_action` itself. So chaining both fixes here
only requires importing both predecessor modules for their respective
monkey-patch side effects; no function body needs copying again.
"""

from __future__ import annotations

import stage17_fixed_action_executor_v6  # noqa: F401 -- ADR-0160: durable-session deadline
import stage17_output_registry_v5  # noqa: F401 -- ADR-0161: offered_count field fix
