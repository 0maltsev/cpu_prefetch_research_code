#!/usr/bin/env python3
"""Phase-controller successor implementing ADR-0160: grants Q16b (in
addition to STAGE17-BLINDED-PILOT) `DURABLE_PILOT_SESSION` deadline
mode, with a real, fixed `session_max_wall_seconds` bound -- not
derived from a pilot_plan resolution, since Q16b carries no `S17-EXT-008`
predecessor the way `STAGE17-BLINDED-PILOT` does.

`prepare_action` is defined once, in `stage17_phase_controller_v4.py`;
every successor since `v5` only ever re-exports it, so its own free
variables resolve against `v4.py`'s own module globals no matter which
successor a caller imports (ADR-0126/ADR-0131, the same rule
`v15.py`'s own `execute_once` docstring already documents). So the only
correct way to change `prepare_action`'s deadline-mode/session-maximum
branching is a fresh copy here, faithful to `v4`'s own body except for
the two targeted changes ADR-0160 describes -- widening
`expected_deadline_mode` to recognize `Q16b`, and adding a `Q16b`-
specific branch for `maximum_seconds` alongside the existing pilot
branch.

`execute_once` (defined once, in `v15.py`) makes its own bare call to
`prepare_action`, which resolves against `v15.py`'s own module globals
-- the identical free-variable trap, requiring the identical fix
`v15.py`'s own docstring already used for `executor`: this file also
monkey-patches `stage17_phase_controller_v15.prepare_action` to this
module's new function, so `execute-action`'s real call path (not just
`verify-signature`'s direct `controller.prepare_action` call) actually
exercises the new deadline logic.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import pathlib

import stage17_fixed_action_executor_v6  # noqa: F401 -- side effect: patches
# stage17_fixed_action_executor_v5.execute_fixed_action's own separate,
# hardcoded deadline-policy check (independent of prepare_action below)
# to also accept Q16b's DURABLE_PILOT_SESSION mode. execute_once (v15.py)
# reaches it via `executor.execute_fixed_action(...)`, a fresh attribute
# lookup on the real v5 module object every call, so patching that
# module's own attribute (done in v6.py's own import-time side effect)
# is sufficient without any further rebinding here.
import stage17_phase_controller_v4 as base
import stage17_phase_controller_v15 as _v15
import stage17_phase_controller_v17 as predecessor
import stage17_state_journal_v39 as journal_runtime

controller_support = base.controller_support
AUTH_SCHEMA = base.AUTH_SCHEMA
REQUEST_SCHEMA = base.REQUEST_SCHEMA
_action_definition = base._action_definition
_binding = base._binding
ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
execute_once = predecessor.execute_once
main = predecessor.main

# ADR-0160: real, measured Q16b per-run wall time on standv2-30 was
# ~0.557s/run (458 runs / 255s, WORKER_TIMEOUT at the pre-existing
# 180s GLOBAL_WALL_SECONDS bound) against 3540 total runs -- a
# realistic completion of ~1972s (~33 minutes). 3600 seconds (1 hour)
# gives roughly 80% margin over the measured rate while still bounding
# the maximum real-hardware exposure time, matching the spirit of
# ADR-0108's own fail-closed, no-implicit-extension design.
Q16B_SESSION_MAX_WALL_SECONDS = 3600


def prepare_action(
    *, repository_root: pathlib.Path, journal: pathlib.Path,
    journal_directory: pathlib.Path, operational_evidence_root: pathlib.Path,
    authorization_path: pathlib.Path,
    signature_path: pathlib.Path, pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None,
    synthetic_test_only: bool = False,
) -> PreparedAction:
    root = repository_root.resolve()
    authorization, authorization_bytes = controller_support._load(authorization_path)
    controller_support._validate(
        root, AUTH_SCHEMA, authorization, "phase authorization"
    )
    definition, registry = _action_definition(root, authorization["action_id"])
    if authorization["fixed_action_definition_sha256"] != registry.plan_sha256:
        raise ControllerError("fixed-action plan byte binding drifted")
    if authorization["permission_matrix"] != definition["permission_matrix"]:
        raise ControllerError("fixed action permission matrix drifted")
    expected_deadline_mode = (
        "DURABLE_PILOT_SESSION"
        if authorization["action_id"] in ("STAGE17-BLINDED-PILOT", "Q16b")
        else "ONE_SHOT_ACTION"
    )
    policy = authorization["deadline_policy"]
    if (policy["mode"] != expected_deadline_mode
            or policy["per_run_max_wall_seconds"] != 180
            or policy["implicit_extension"] is not False
            or policy["partial_session_completes"] is not False):
        raise ControllerError("action deadline/session policy drifted")
    actual_now = controller_support._now()
    validation = journal_runtime.validate_operational_journal(
        repository_root=root, evidence_root=operational_evidence_root,
        latest_journal=journal,
        journal_directory=journal_directory, pilot_archive=pilot_archive,
        pilot_sidecar=pilot_sidecar, as_of_utc=actual_now,
        allow_synthetic_test_evidence=synthetic_test_only,
    )
    required_ids = tuple(definition["required_resolution_ids"])
    if any(item not in validation.resolutions for item in required_ids):
        raise ControllerError("fixed action predecessor is absent")
    if validation.current_state != definition["required_state"]:
        raise ControllerError("fixed action state gate is not satisfied")
    expected_predecessors = [
        _binding(validation.resolutions[item]) for item in required_ids
    ]
    if authorization["predecessor_resolutions"] != expected_predecessors:
        raise ControllerError("authorization predecessor lineage drifted")
    authority_resolution = definition["authorization_resolution_id"]
    if authority_resolution is not None:
        admitted = validation.resolutions.get(authority_resolution)
        if admitted is None or not isinstance(admitted.semantic_context, dict):
            raise ControllerError("action authorization resolution is absent")
        if (admitted.semantic_context.get("authorization_sha256")
                != controller_support._sha(authorization_bytes)
                or admitted.semantic_context.get("authorization") != authorization):
            raise ControllerError("execution authority differs from admitted bytes")
    ext3 = validation.resolutions["S17-EXT-003"].semantic_context
    if not isinstance(ext3, dict) or not isinstance(ext3.get("trust"), dict):
        raise ControllerError("admitted trust context is absent")
    trust = ext3["trust"]
    values = trust["measurements"]
    expected_trust_context = {
        "ext002_resolution": _binding(validation.resolutions["S17-EXT-002"]),
        "ext003_resolution": _binding(validation.resolutions["S17-EXT-003"]),
    }
    if (authorization["trust_context"] != expected_trust_context
            or authorization["actor"] != values["principal"]
            or authorization["reviewer"] != values["reviewer_role"]
            or authorization["target"]["stand_id"] != trust["subject_id"]):
        raise ControllerError("authorization trust actor/reviewer/stand drifted")
    controller_support._verify_signature(
        authorization_bytes, signature_path, trust
    )
    issued = controller_support._parse_utc(authorization["issued_at_utc"])
    expires = controller_support._parse_utc(authorization["expires_at_utc"])
    sampled = controller_support._parse_utc(actual_now)
    if authorization["action_id"] == "STAGE17-BLINDED-PILOT":
        pilot = validation.resolutions["S17-EXT-008"].semantic_context[
            "pilot_plan"
        ]
        repetitions = pilot["repetitions_per_cell"]
        recovery_seconds = math.ceil(
            pilot["recovery"]["duration_ticks"] / 1_000_000_000_000
        )
        maximum_seconds = (
            180 * 180 * repetitions
            + recovery_seconds * max(repetitions - 1, 0)
            + 180
        )
        if policy["session_max_wall_seconds"] != maximum_seconds:
            raise ControllerError("pilot session maximum is not plan-derived")
    elif authorization["action_id"] == "Q16b":
        maximum_seconds = Q16B_SESSION_MAX_WALL_SECONDS
        if policy["session_max_wall_seconds"] != maximum_seconds:
            raise ControllerError(
                "Q16b session maximum does not match the fixed ADR-0160 bound"
            )
    else:
        maximum_seconds = 1800
        if policy["session_max_wall_seconds"] is not None:
            raise ControllerError("one-shot action cannot declare a session maximum")
    if (not issued <= sampled < expires
            or expires - issued > dt.timedelta(seconds=maximum_seconds)):
        raise ControllerError("authorization is future/expired/overlong")
    request_path, request_bytes = controller_support._read_binding(
        authorization["request_binding"], "fixed request"
    )
    request = json.loads(request_bytes)
    if not isinstance(request, dict):
        raise ControllerError("fixed request root is not an object")
    controller_support._validate(root, REQUEST_SCHEMA, request, "fixed request")
    runtime, release = _runtime_from_context(authorization["action_id"], validation)
    expected_runtime = {key: runtime[key] for key in (
        "role", "profile", "size_bytes", "sha256",
    )}
    if (request["runtime_binding"] != expected_runtime
            or request["release_binding"] != release
            or authorization["evidence_root_binding"]
            != request["evidence_root_binding"]
            or request["predecessor_resolutions"] != expected_predecessors
            or request["authorization_id"] != authorization["authorization_id"]
            or request["session_id"] != authorization["session_id"]
            or request["action_id"] != authorization["action_id"]
            or request["stand_id"] != authorization["target"]["stand_id"]
            or request["synthetic_test_only"] is not synthetic_test_only
            or pathlib.Path(authorization["request_binding"]["path"])
            != request_path):
        raise ControllerError("fixed request lineage/runtime/release drifted")
    _validate_action_inputs(
        action=authorization["action_id"], request=request,
        validation=validation, synthetic_test_only=synthetic_test_only,
    )
    worker_path = pathlib.Path(runtime.pop("path"))
    return PreparedAction(
        root=root, authorization=authorization,
        authorization_bytes=authorization_bytes, request=request,
        request_bytes=request_bytes, runtime=runtime, worker_path=worker_path,
        release=release, validation=validation, registry=registry,
    )


_v15.prepare_action = prepare_action


if __name__ == "__main__":
    raise SystemExit(main())
