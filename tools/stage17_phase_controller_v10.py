#!/usr/bin/env python3
"""Restores `_validate_action_inputs`, dropped in the same `v4`-to-`v5`
succession as `_runtime_from_context` (ADR-0127) and never re-exported or
reimplemented by any version from `v5` onward.

`tools/stage17_operational_cli_v11.py`'s `author_request` -- the real
"author-request" CLI action, now genuinely reached by the hermetic
rehearsal for the first time tonight once `S17-EXT-002`/`S17-EXT-003`
admission was fixed (ADR-0129) -- calls `controller._runtime_from_context`
(restored by `v9`/ADR-0127) immediately followed by
`controller._validate_action_inputs`. Against `v9` the second call raises
`AttributeError: module 'stage17_phase_controller_v9' has no attribute
'_validate_action_inputs'`: `v5.py` only ever re-exported `ControllerError`,
`PreparedAction`, `prepare_action`, `execute_once`, `main`, dropping this
sibling function alongside `_runtime_from_context` at the same succession
point ADR-0127 already documents -- ADR-0127's own fix only restored the
one function whose absence had by then been observed; this is the second
half of the identical gap, not a new decision. `v9` and its entire
accepted closure are untouched by this file; it is a new, additive
successor only.

Ported from `v4`'s implementation with no behavioral change, confirmed by
exact programmatic extraction, not manual retyping. Its data-shape
dependency was verified against what real `S17-EXT-008` admission still
produces: `stage17_operational_semantics_v5.py`'s (and, before it,
`_v4.py`'s unchanged) `S17-EXT-008` branch still sets
`semantic_context["pilot_plan_sha256"]`/`["pilot_plan"]` exactly as this
function's `STAGE17-BLINDED-PILOT` branch expects; every other action
family (`Q15-R`, `Q15-W`, `Q16a`, `Q16b`, `Q16c`) validates only the
`request`/`validation` values passed in as parameters, with no reference
to any admission-side whitelist this session's other fixes touched.
"""

from __future__ import annotations

from typing import Any

import stage17_phase_controller_v9 as predecessor


ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
execute_once = predecessor.execute_once
main = predecessor.main
_runtime_from_context = predecessor._runtime_from_context

_BASE_V4 = predecessor.predecessor.predecessor.predecessor.predecessor.predecessor
pilot_plan_runtime = _BASE_V4.pilot_plan_runtime
_validate_hardware_control = _BASE_V4._validate_hardware_control
_validate_hash = _BASE_V4._validate_hash
_validate_q16_matrix = _BASE_V4._validate_q16_matrix
_validate_q16a_matrix = _BASE_V4._validate_q16a_matrix


def _validate_action_inputs(
    *, action: str, request: dict[str, Any], validation: Any,
    synthetic_test_only: bool,
) -> None:
    values = request["action_inputs"]
    if not isinstance(values, dict):
        raise ControllerError("fixed action inputs are not an object")
    # The test-linked dispatcher consumes the same typed scientific input
    # families.  Its backend is synthetic; its contract is not a nonce bypass.
    if action == "Q15-R":
        expected = {
            "qualification_id", "attempt_id", "session_id",
            "probe_platform_binding",
        }
    elif action == "Q15-W":
        expected = {
            "q15_r_attempt_sha256", "q15_r_result_sha256", "session_id",
            "prestate",
        }
    elif action == "Q16a":
        expected = {"plan_sha256", "hardware_control", "captures"}
    elif action == "Q16b":
        expected = {
            "plan_sha256", "q16a_result_sha256", "hardware_control", "runs"
        }
    elif action == "Q16c":
        expected = {
            "plan_sha256", "q16a_result_sha256", "q16b_result_sha256",
            "hardware_control", "runs"
        }
    else:
        expected = {"plan_sha256", "pilot_plan"}
    if set(values) != expected:
        raise ControllerError("production action input family is incomplete/expanded")
    if action == "STAGE17-BLINDED-PILOT":
        plan_context = validation.resolutions["S17-EXT-008"].semantic_context
        if (values["plan_sha256"] != plan_context["pilot_plan_sha256"]
                or values["pilot_plan"] != plan_context["pilot_plan"]):
            raise ControllerError("pilot action differs from admitted frozen plan")
        pilot_plan_runtime.validate(
            values["pilot_plan"], stand_id=request["stand_id"],
            synthetic_test_only=synthetic_test_only,
            admitted_resolutions=validation.resolutions,
        )
    for name, value in values.items():
        if name.endswith("_sha256"):
            _validate_hash(value, name)
    if action == "Q16a":
        _validate_hardware_control(values, validation)
        _validate_q16a_matrix(values)
        for capture in values["captures"]:
            for name, value in capture.items():
                if name.endswith("_sha256"):
                    _validate_hash(value, f"captures/{name}")
    if action in {"Q16b", "Q16c"}:
        _validate_hardware_control(values, validation)
        if not isinstance(values["runs"], list) or not values["runs"]:
            raise ControllerError("Q16 frozen run family is absent")
        for run in values["runs"]:
            if not isinstance(run, dict):
                raise ControllerError("Q16 frozen run is not an object")
            for name, value in run.items():
                if name.endswith("_sha256"):
                    _validate_hash(value, f"runs/{name}")
        _validate_q16_matrix(action, values)


if __name__ == "__main__":
    raise SystemExit(main())
