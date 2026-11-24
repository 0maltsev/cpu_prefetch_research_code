#!/usr/bin/env python3
"""Phase-controller successor raising stage17_phase_controller_v2.py's
own MAX_BOUND_INPUT_BYTES=16MiB bound to 64MiB, matching ADR-0159's own
C++-side kMaximumRequestBytes raise (stage17_fixed_action.cpp) -- the
Python-side companion bound was never updated to match, discovered
live while building Q16b's real ~47MB request on standv2-30
(3540 runs, 5 per-package runner_admission tickets each embedding the
full 21-file evidence set, serialized well past the old 16MiB ceiling).

This bound gates nothing about worker/evidence identity -- it is purely
an arbitrary file-size ceiling in stage17_phase_controller_v2.py's own
_read_binding/_read_unbound_regular helpers (used by prepare_action via
stage17_phase_controller_v4.py's own `controller_support` alias), so
raising it changes no security property: every real hash/signature/
identity check downstream remains exactly as strict as before.
"""

from __future__ import annotations

import stage17_phase_controller_v16 as predecessor
import stage17_phase_controller_v2 as _v2

_v2.MAX_BOUND_INPUT_BYTES = 64 * 1024 * 1024

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
execute_once = predecessor.execute_once
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
