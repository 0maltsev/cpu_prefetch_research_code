"""Bind Q16 hardware control to the admitted Q15-R mapping and Q15-W result."""

from __future__ import annotations

from typing import Any

import stage17_output_registry_v8 as registry
import stage17_phase_controller_v4 as base
import stage17_phase_controller_v10 as action_validation
import stage17_phase_controller_v20 as predecessor

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction


def _validate_hardware_control(values: dict[str, Any], validation: Any) -> None:
    ext4 = validation.resolutions["S17-EXT-004"].semantic_context
    ext5 = validation.resolutions["S17-EXT-005"].semantic_context
    try:
        mapping = ext4["hardware_mapping"]
        mapping_id = mapping["mapping_id"]
        q15w = ext5["q15_w"]
        expected = {
            "mapping_id": mapping_id,
            "q15_w_result_sha256": q15w["result_sha256"],
            "prestate": q15w["request"]["action_inputs"]["prestate"],
        }
        registry.validate_hardware_control(expected)
        if expected["prestate"] != mapping["prestate"]:
            raise ControllerError("admitted Q15-R/Q15-W prestate differs")
    except (KeyError, TypeError, registry.OutputAdmissionError) as exception:
        raise ControllerError("admitted Q15 mapping/prestate is invalid") from exception
    if values.get("hardware_control") != expected:
        raise ControllerError("Q16 hardware control differs from admitted Q15-R/Q15-W")


base._validate_hardware_control = _validate_hardware_control
action_validation._validate_hardware_control = _validate_hardware_control
prepare_action = predecessor.prepare_action
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
execute_once = predecessor.execute_once
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
