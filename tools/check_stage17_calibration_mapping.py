"""Synthetic checks of production calibration admission; no stand access."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import tempfile
from types import SimpleNamespace

import stage17_operational_cli_v14 as cli
import stage17_output_registry_v8 as registry
import stage17_phase_controller_v4 as phase_base
import stage17_phase_controller_v21 as phase


def expect_rejection(action, error_type):
    try:
        action()
    except error_type:
        return
    raise AssertionError("invalid calibration evidence was accepted")


def self_test(root: pathlib.Path) -> None:
    assert phase_base._validate_hardware_control is phase._validate_hardware_control
    assert registry.base._validate_calibration_hardware is registry._validate_calibration_hardware
    assert cli.base.controller is phase
    pinned = registry.base.pin_registry(root)
    assert pinned.plan["profile_id"] == "STAGE17-FIXED-PHASE-ACTIONS-v6"
    for mapping_id, cpus in registry.MAPPING_CPUS.items():
        prestate = [{"cpu": cpu, "complete_value_hex": "123456789abcdef0"} for cpu in cpus]
        control = {"mapping_id": mapping_id, "prestate": prestate,
                   "q15_w_result_sha256": "b" * 64}
        for field, value in (("cpu", True), ("complete_value_hex", "F" * 16),
                             ("complete_value_hex", "0"), ("complete_value_hex", 0)):
            malformed = copy.deepcopy(control)
            malformed["prestate"][1][field] = value
            expect_rejection(lambda: registry.validate_hardware_control(malformed),
                             registry.OutputAdmissionError)
        validation = SimpleNamespace(resolutions={
            "S17-EXT-004": SimpleNamespace(semantic_context={"hardware_mapping": {
                "mapping_id": mapping_id, "prestate": prestate,
            }}),
            "S17-EXT-005": SimpleNamespace(semantic_context={"q15_w": {
                "result_sha256": "b" * 64,
                "request": {"action_inputs": {"prestate": prestate}},
            }}),
        })
        captures = []
        context = 0
        for state in ("H0", "H1"):
            for placement in ("NEAR", "FAR"):
                for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"):
                    for repetition in range(59):
                        captures.append({
                            "context_ordinal": context, "repetition_ordinal": repetition,
                            "hardware_state": state, "placement": placement,
                            "working_set_class": working_set,
                            "seed_id": f"SYNTHETIC-{context}-{repetition}",
                            "calibration_plan_sha256": "a" * 64,
                        })
                    context += 1
        inputs = {"plan_sha256": "a" * 64, "hardware_control": control,
                  "captures": captures}
        def validate_inputs(values):
            cli.base.controller._validate_action_inputs(
                action="Q16a", request={"action_inputs": values},
                validation=validation, synthetic_test_only=True,
            )
        validate_inputs(inputs)
        for mutate in ("mapping", "prestate", "lineage"):
            invalid = copy.deepcopy(inputs)
            if mutate == "mapping":
                invalid["hardware_control"]["mapping_id"] = "UNKNOWN"
            elif mutate == "prestate":
                invalid["hardware_control"]["prestate"][2]["cpu"] = 26 if cpus[2] == 8 else 8
            else:
                invalid["hardware_control"]["q15_w_result_sha256"] = "c" * 64
            expect_rejection(lambda: validate_inputs(invalid), phase.ControllerError)
        for action_id in ("Q16a", "Q16b", "Q16c"):
            document = {
                "schema_version": "cpu-prefetch-stage17-calibration-hardware-state/2",
                "action_id": action_id, "plan_sha256": "a" * 64,
                "mapping_id": mapping_id, "q15_w_result_sha256": "b" * 64,
                "whole_plot_order": ["H0", "H1"],
                "apply_readback": [{"cpu": cpu, "complete_value_hex": "123456789abcdeff"} for cpu in cpus],
                "restore_readback": list(reversed(prestate)), "run_count": 708,
                "restoration_verified": True, "phase18_authority": False,
            }
            with tempfile.TemporaryDirectory(prefix="stage17-calibration-mapping-") as temporary:
                directory = pathlib.Path(temporary)
                name = f"stage17-{action_id}-hardware-state-v2.json"
                descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    def validate_output(value):
                        payload = json.dumps(value, sort_keys=True).encode()
                        (directory / name).write_bytes(payload)
                        binding = {
                            "role": "STAGE17_CALIBRATION_HARDWARE_STATE",
                            "schema_identity": document["schema_version"],
                            "file_name": name, "media_type": "application/json",
                            "size_bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        }
                        registry.base._validate_calibration_hardware(
                            pinned, descriptor, action_id, {"action_inputs": inputs},
                            [binding], 708,
                        )
                    validate_output(document)
                    for mutate in ("mapping", "apply", "restore", "order", "lineage", "count"):
                        invalid = copy.deepcopy(document)
                        if mutate == "mapping":
                            invalid["mapping_id"] = next(item for item in registry.MAPPING_CPUS if item != mapping_id)
                        elif mutate == "apply":
                            invalid["apply_readback"][0]["complete_value_hex"] = "000000000000000f"
                        elif mutate == "restore":
                            invalid["restore_readback"][0]["complete_value_hex"] = "0000000000000000"
                        elif mutate == "order":
                            invalid["apply_readback"].reverse()
                        elif mutate == "lineage":
                            invalid["q15_w_result_sha256"] = "c" * 64
                        else:
                            invalid["run_count"] = 1
                        expect_rejection(lambda: validate_output(invalid), registry.OutputAdmissionError)
                finally:
                    os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    parser.add_argument("--check-policy", action="store_true")
    arguments = parser.parse_args()
    self_test(arguments.root.resolve())
    if arguments.check_policy:
        status = cli.journal.checked_in_status(arguments.root.resolve())
        assert status.current_state == "PREPARED"
        assert status.resolution_count == 0 and status.transition_count == 0
        assert len(status.missing_input_ids) == 10 and not status.pilot_ready
        print("stage17-calibration-policy: PASS policy=v54 state=PREPARED resolutions=0 pilot_ready=false")
    print("stage17-calibration-mapping: PASS mappings=2 outputs=6 output_mutants=36 request_mutants=6 malformed_prestates=8 stand=NOT_ACCESSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
