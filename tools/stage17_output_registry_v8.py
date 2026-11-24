"""Admit calibration hardware evidence for the exact named CPU mapping."""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_output_registry_v7 as predecessor

base = predecessor._base
OutputAdmissionError = base.OutputAdmissionError
CALIBRATION_HARDWARE_SCHEMA = "config/schemas/stage17-calibration-hardware-state-v2.schema.json"
MAPPING_CPUS = {
    "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1": (0, 1, 26),
    "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1": (0, 1, 8),
}


def validate_hardware_control(control: dict[str, Any]) -> dict[int, str]:
    mapping_id = control.get("mapping_id")
    cpus = MAPPING_CPUS.get(mapping_id) if isinstance(mapping_id, str) else None
    values = control.get("prestate")
    if (cpus is None or not isinstance(values, list)
            or any(not isinstance(item, dict)
                   or set(item) != {"cpu", "complete_value_hex"}
                   or type(item["cpu"]) is not int
                   or not isinstance(item["complete_value_hex"], str)
                   or len(item["complete_value_hex"]) != 16
                   or any(character not in "0123456789abcdef"
                          for character in item["complete_value_hex"])
                   for item in values)
            or [item.get("cpu") for item in values if isinstance(item, dict)] != list(cpus)
            or len(values) != len(cpus)):
        raise OutputAdmissionError("hardware mapping and ordered prestate CPUs differ")
    return base._msr_map(values)


def _validate_calibration_hardware(
    registry: base.PinnedOutputRegistry, directory_fd: int, action_id: str,
    request: dict[str, Any], artifacts: list[dict[str, Any]], run_count: int,
) -> None:
    matches = [item for item in artifacts
               if item["role"] == "STAGE17_CALIBRATION_HARDWARE_STATE"]
    if len(matches) != 1:
        raise OutputAdmissionError("calibration hardware evidence is absent or duplicated")
    binding = matches[0]
    expected_name = f"stage17-{action_id}-hardware-state-v2.json"
    if (binding["schema_identity"] != "cpu-prefetch-stage17-calibration-hardware-state/2"
            or binding["file_name"] != expected_name
            or binding["media_type"] != "application/json"):
        raise OutputAdmissionError("calibration hardware-state identity drifted")
    base._stream_binding(directory_fd, binding, 64 * 1024 * 1024)
    document = base._json_output(directory_fd, binding["file_name"], binding["size_bytes"])
    base.validate_document(registry, document, CALIBRATION_HARDWARE_SCHEMA,
                           "calibration hardware state")
    control = request["action_inputs"]["hardware_control"]
    prestate = validate_hardware_control(control)
    expected_apply = {cpu: f"{int(value, 16) | 15:016x}"
                      for cpu, value in prestate.items()}
    if (document["action_id"] != action_id
            or document["plan_sha256"] != request["action_inputs"]["plan_sha256"]
            or document["mapping_id"] != control["mapping_id"]
            or document["q15_w_result_sha256"] != control["q15_w_result_sha256"]
            or document["run_count"] != run_count
            or base._msr_map(document["restore_readback"]) != prestate
            or base._msr_map(document["apply_readback"]) != expected_apply
            or [item["cpu"] for item in document["apply_readback"]] != list(prestate)
            or [item["cpu"] for item in document["restore_readback"]] != list(reversed(prestate))):
        raise OutputAdmissionError("calibration hardware state differs from signed request")


base.PLAN_PATH = pathlib.PurePosixPath("config/stage17/stage17-fixed-phase-actions-v6.json")
base.PLAN_SCHEMA_PATH = pathlib.PurePosixPath("config/schemas/stage17-fixed-phase-actions-v6.schema.json")
base.CALIBRATION_HARDWARE_SCHEMA = CALIBRATION_HARDWARE_SCHEMA
base._validate_calibration_hardware = _validate_calibration_hardware
