#!/usr/bin/env python3
"""Phase-controller successor further raising `stage17_phase_controller_
v2.py`'s own `MAX_BOUND_INPUT_BYTES` bound, this time from 64 MiB
(ADR-0159, `stage17_phase_controller_v17.py`) to 128 MiB (ADR-0165).

The real `S17-EXT-010`/`STAGE17-BLINDED-PILOT` execution attempt on
standv2-30 failed at its very first step -- before any real hardware
run started, no partial evidence lost -- with `"fixed request exceeds
its fixed size limit"`. Root-caused by direct code reading: `stage17_
phase_controller_v18.py`'s `prepare_action` reads the real request file
via `controller_support._read_binding(authorization["request_binding"],
"fixed request")`, which enforces `MAX_BOUND_INPUT_BYTES` (64 MiB since
ADR-0159). The real `STAGE17-BLINDED-PILOT` request embeds the complete,
real, admitted `S17-EXT-008` pilot plan verbatim (required by `stage17_
phase_controller_v10.py`'s `_validate_action_inputs`), making the real
request file 68,835,354 bytes -- about 1.65 MB past the 64 MiB (
67,108,864-byte) ceiling ADR-0159 set for Q16b's real ~47 MB request,
never anticipated to need to grow again for the pilot's own, larger
request.

As `stage17_phase_controller_v17.py`'s own docstring already
establishes, this bound gates nothing about worker/evidence identity --
it is purely an arbitrary file-size ceiling in `_read_binding`/
`_read_unbound_regular`, so raising it again changes no security
property: every real hash/signature/identity check downstream remains
exactly as strict as before.
"""

from __future__ import annotations

import stage17_phase_controller_v19 as predecessor
import stage17_phase_controller_v2 as _v2

_v2.MAX_BOUND_INPUT_BYTES = 128 * 1024 * 1024

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
execute_once = predecessor.execute_once
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
