"""Calibration schema and observed hardware-mapping context successor."""

from __future__ import annotations

import stage17_operational_semantics_v11 as predecessor
import stage17_output_registry_v8 as registry

OperationalSemanticError = predecessor.OperationalSemanticError
ROLE_SCHEMA_v12 = {
    **predecessor.ROLE_SCHEMA_v11,
    "STAGE17_CALIBRATION_HARDWARE_STATE": registry.CALIBRATION_HARDWARE_SCHEMA,
}
predecessor.ROLE_SCHEMA_v11 = ROLE_SCHEMA_v12
ROLE_SCHEMA_v11 = ROLE_SCHEMA_v12
ROLE_SCHEMA_v8 = ROLE_SCHEMA_v12
ROLE_SCHEMA_v6 = ROLE_SCHEMA_v12


def verify_manifest_v11(**arguments):
    context = predecessor.verify_manifest_v11(**arguments)
    if arguments["expected_input_id"] == "S17-EXT-004":
        manifest, _ = predecessor.load(arguments["manifest_path"])
        artifacts = predecessor._read_artifacts_v11(
            arguments["repository_root"], arguments["manifest_path"], manifest,
            arguments["pinned_repository_bytes"],
        )
        observed = predecessor._one(artifacts, "Q15_R_READ_ONLY_PRESTATE").document
        mapping_id = observed["mapping_id"]
        expected_model = {
            "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1": 85,
            "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1": 62,
        }.get(mapping_id)
        control = {"mapping_id": mapping_id, "prestate": observed["prestate"]}
        try:
            registry.validate_hardware_control(control)
        except registry.OutputAdmissionError as exception:
            raise OperationalSemanticError(str(exception)) from exception
        if observed["cpu_family"] != 6 or observed["cpu_model"] != expected_model:
            raise OperationalSemanticError("observed Q15 CPU model and mapping differ")
        context["hardware_mapping"] = control
    elif arguments["expected_input_id"] == "S17-EXT-007":
        admitted = arguments["admitted_resolutions"]
        mapping = admitted["S17-EXT-004"].semantic_context["hardware_mapping"]
        q15w = admitted["S17-EXT-005"].semantic_context["q15_w"]
        expected = {
            "mapping_id": mapping["mapping_id"],
            "prestate": q15w["request"]["action_inputs"]["prestate"],
            "q15_w_result_sha256": q15w["result_sha256"],
        }
        if expected["prestate"] != mapping["prestate"]:
            raise OperationalSemanticError("Q15-R/Q15-W prestate differs")
        for family in context["actions"].values():
            if family["request"]["action_inputs"]["hardware_control"] != expected:
                raise OperationalSemanticError("calibration lacks admitted Q15 hardware identity")
    return context
