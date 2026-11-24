#!/usr/bin/env python3
"""Policy-v21 Stage 17 phase-controller successor (ADR-0127).

Restores `_runtime_from_context`, present in `stage17_phase_controller_v2.py`
through `_v4.py` and dropped without replacement in the `v4`-to-`v8`
succession.  `tools/stage17_operational_cli_v10.py`'s `author-request`
calls `controller._runtime_from_context(action, validation)` directly;
against `v8` this raises `AttributeError` because no version from `v5`
onward ever re-exported or reimplemented it, and no prior test or real
usage ever exercised `author-request` to catch the gap.

Ported from `v4`'s implementation with no behavioral change.  Its two
branches were verified against the current real data shapes before this
file was written: `S17-EXT-003`'s admitted `semantic_context["runtime"]
["measurements"]` still carries exactly `worker_path`, `worker_role`,
`runtime_profile`, `worker_size_bytes`, `worker_sha256`,
`supported_actions` (populated by `stage17_operational_semantics_v4.py`'s
`_verify_extracted_release`); `S17-EXT-006`'s admitted `semantic_context`
still carries `release_artifact_path`, `release_artifact_size_bytes`,
`release_artifact_sha256`, `release_artifact_role`, `runtime_profile`,
and `supported_actions` as flat keys (populated by
`stage17_semantic_verifier_v14.py`'s `verify_s17_ext_006`).  The
compiled-worker runtime-profile identity `"STAGE17-FIXED-ACTION-WORKER-v4"`
is unchanged.  `v8` and its entire accepted closure are untouched by this
file; it is a new, additive successor only.
"""

from __future__ import annotations

from typing import Any

import stage17_phase_controller_v8 as predecessor
import stage17_state_journal_v16 as journal_runtime


for module in (predecessor, predecessor.predecessor, predecessor.predecessor.predecessor):
    module.journal_runtime = journal_runtime

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
execute_once = predecessor.execute_once
main = predecessor.main


def _runtime_from_context(
    action: str, validation: journal_runtime.OperationalJournalValidation,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if action in {"Q15-R", "Q15-W"}:
        source = validation.resolutions["S17-EXT-003"]
        context = source.semantic_context
        if not isinstance(context, dict):
            raise ControllerError("EXT003 runtime context is absent")
        runtime_record = context.get("runtime")
        measurements = (
            runtime_record.get("measurements")
            if isinstance(runtime_record, dict) else None
        )
        if not isinstance(measurements, dict):
            raise ControllerError("EXT003 runtime measurements are absent")
        path = measurements["worker_path"]
        release = {
            "source_resolution_id": source.resolution_id,
            "source_resolution_sha256": source.sha256,
            "artifact_role": measurements["worker_role"],
            "runtime_profile": measurements["runtime_profile"],
            "worker_size_bytes": measurements["worker_size_bytes"],
            "worker_sha256": measurements["worker_sha256"],
        }
    else:
        source = validation.resolutions["S17-EXT-006"]
        context = source.semantic_context
        if not isinstance(context, dict):
            raise ControllerError("EXT006 release context is absent")
        measurements = {
            "worker_path": context["release_artifact_path"],
            "worker_size_bytes": context["release_artifact_size_bytes"],
            "worker_sha256": context["release_artifact_sha256"],
            "worker_role": context["release_artifact_role"],
            "runtime_profile": context["runtime_profile"],
            "supported_actions": context["supported_actions"],
        }
        path = measurements["worker_path"]
        release = {
            "source_resolution_id": source.resolution_id,
            "source_resolution_sha256": source.sha256,
            "artifact_role": measurements["worker_role"],
            "runtime_profile": measurements["runtime_profile"],
            "worker_size_bytes": measurements["worker_size_bytes"],
            "worker_sha256": measurements["worker_sha256"],
        }
    if (measurements["worker_role"] != "STAGE17_FIXED_ACTION_WORKER"
            or measurements["runtime_profile"]
            != "STAGE17-FIXED-ACTION-WORKER-v4"
            or tuple(measurements["supported_actions"]) != (
                "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                "STAGE17-BLINDED-PILOT",
            ) or action not in measurements["supported_actions"]):
        raise ControllerError("admitted fixed-action runtime surface drifted")
    runtime = {
        "path": path, "role": measurements["worker_role"],
        "profile": measurements["runtime_profile"],
        "size_bytes": measurements["worker_size_bytes"],
        "sha256": measurements["worker_sha256"],
    }
    return runtime, release


if __name__ == "__main__":
    raise SystemExit(main())
