"""Signed archive-plan admission, retaining the original v6 authority boundary.

Storage /2 plans require an implementation profile from the verified EXT006
release context. The signed plan binds that exact profile, not a guessed host
codec. Historical /1 families retain their original admission path.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import time
import types

import stage17_phase_controller_v25 as previous
import stage17_formal_plan_v2 as plans
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_calibration_v2 as calibration

ControllerError = previous.ControllerError
deadline_policy = previous.deadline_policy
activate = previous.activate
support = previous.support
runtime_from_context = previous.runtime_from_context
# CLI11's preserved Q15 request route uses these legacy callback signatures.
# Keep EXT003 runtime selection and typed Q15 input checks exactly as in v25.
_runtime_from_context = previous._runtime_from_context
_validate_action_inputs = previous._validate_action_inputs
MAX_PROFILE_BYTES = 16 * 1024**2

_contract = types.SimpleNamespace(**{**vars(previous.contract),
                                     "validate_plan": plans.validate_plan})
contract = _contract


@dataclass(frozen=True)
class PreparedArchiveAction(previous.PreparedAction):
    archive_runtime_profile: runtime.RuntimeProfile


def is_archived(request):
    action = request.get("action_id")
    return (action in plans.VERSION and request.get("schema_version") ==
            "cpu-prefetch-stage17-fixed-action-request/6" and
            request.get("action_inputs", {}).get("plan", {}).get("schema_version") == plans.VERSION[action])


def qualified_archive_profile(request, validation, *, deadline_ns):
    """The caller supplies an already authenticated EXT006 resolution context."""
    context = validation.resolutions["S17-EXT-006"].semantic_context
    previous.runtime_from_context(validation)
    storage = request["action_inputs"]["plan"]["storage"]
    binding = context.get("archive_profile_binding")
    if (type(binding) is not dict or set(binding) != {"path", "size_bytes", "sha256"}
            or type(binding["path"]) is not str
            or binding["sha256"] != storage["implementation_profile_sha256"]):
        raise ControllerError("archival plan lacks its exact qualified implementation profile")
    bundle = context.get("archive_bundle_root")
    provisioned = context.get("archive_runtime_root")
    if type(bundle) is not str or type(provisioned) is not str:
        raise ControllerError("qualified archive bundle/runtime roots are absent")
    # EXT006 retains the receipt's exact bundle-relative member binding.
    member = "config/stage17/formal-archive-implementation-profile-v1.json"
    if binding["path"] != member:
        raise ControllerError("qualified implementation profile is outside its bundle member")
    expected_path = Path(bundle) / member
    try:
        return runtime.load_runtime_profile(expected_path,
            expected=archive.PhysicalBinding(binding["size_bytes"], binding["sha256"]),
            bundle_root=Path(bundle), runtime_root=Path(provisioned),
            max_profile_bytes=MAX_PROFILE_BYTES, deadline_ns=deadline_ns)
    except (archive.ArchiveError, OSError, ValueError, TypeError) as error:
        raise ControllerError("qualified archive implementation rejected: " + str(error)) from error


def _validate_inputs(request, validation):
    prior = lambda **values: previous._with_globals(previous.validate_prior_calibration,
        {"calibration": calibration}, values)
    def validate_prior(result, prior_action, plan, selected_duration_ns):
        return prior(result=result, prior=prior_action, plan=plan,
                     selected_duration_ns=selected_duration_ns)
    return previous._with_globals(previous.validate_action_inputs,
        {"contract": _contract, "validate_prior_calibration": validate_prior,
         "registry": types.SimpleNamespace(**{**vars(previous.registry),
                                                "canonical": archive.canonical})},
        {"request": request, "validation": validation})


def validate_action_inputs(request, validation):
    if not is_archived(request):
        return previous.validate_action_inputs(request, validation)
    extent = _validate_inputs(request, validation)
    qualified_archive_profile(request, validation,
        deadline_ns=time.monotonic_ns() + extent.declared.cleanup_ns)
    return extent


def _prepare_action(*, for_retention, **arguments):
    # This unqualified successor has no fallback when the archive registry is
    # absent. All signature, original byte, journal and UTC checks remain v25.
    import stage17_output_registry_v12 as registry
    profiles = []

    def validate(request, validation):
        if not is_archived(request):
            return previous.validate_action_inputs(request, validation)
        extent = _validate_inputs(request, validation)
        profiles.append(qualified_archive_profile(request, validation,
            deadline_ns=time.monotonic_ns() + extent.declared.cleanup_ns))
        return extent

    prepared = previous._with_globals(previous._prepare_action,
        {"registry": registry, "validate_action_inputs": validate},
        {"for_retention": for_retention, **arguments})
    if not is_archived(prepared.request):
        return prepared
    if len(profiles) != 1:
        raise ControllerError("archive implementation was not admitted exactly once")
    return PreparedArchiveAction(**{f.name: getattr(prepared, f.name)
                                   for f in fields(previous.PreparedAction)},
                                 archive_runtime_profile=profiles[0])


def prepare_action(**arguments):
    return _prepare_action(for_retention=False, **arguments)


def prepare_retention(**arguments):
    return _prepare_action(for_retention=True, **arguments)


def execute_once(**arguments):
    prepared = prepare_action(**arguments)
    if not is_archived(prepared.request):
        return previous._with_globals(previous.execute_once,
            {"prepare_action": lambda **unused: prepared}, arguments)
    import stage17_fixed_action_executor_v11 as executor
    return executor.execute_fixed_action(repository_root=prepared.root,
        authorization=prepared.authorization, authorization_bytes=prepared.authorization_bytes,
        request=prepared.request, request_bytes=prepared.request_bytes,
        worker_binding=prepared.runtime, worker_path=prepared.worker_path,
        release_binding=prepared.release,
        output_root=Path(prepared.request["evidence_root_binding"]["absolute_path"]),
        archive_runtime_profile=prepared.archive_runtime_profile,
        synthetic_test_only=arguments.get("synthetic_test_only", False))
