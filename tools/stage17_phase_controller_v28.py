"""Cold archive overlay admission over the preserved v27 Q16a handoff.

Only archive-profile selection changes. The v26 formal preparation, signature,
namespace and UTC gates and the qualified native worker remain unchanged.
"""
from __future__ import annotations

from pathlib import Path

import stage17_phase_controller_v27 as previous
import stage17_archive_overlay_v1 as overlay
import stage17_archive_metadata_fast_v1 as metadata

ControllerError = previous.ControllerError
contract = previous.contract
activate = previous.activate
support = previous.support
runtime_from_context = previous.runtime_from_context
deadline_policy = previous.deadline_policy
is_archived = previous.is_archived
_runtime_from_context = previous._runtime_from_context
_validate_action_inputs = previous._validate_action_inputs
_validate_inputs = previous._validate_inputs


def qualified_archive_profile(request, validation, *, deadline_ns):
    return overlay.qualified_profile(request, validation, deadline_ns=deadline_ns)


def validate_action_inputs(request, validation):
    v26 = previous.previous
    return v26.previous._with_globals(v26.validate_action_inputs,
        {'_validate_inputs': _validate_inputs,
         'qualified_archive_profile': qualified_archive_profile},
        dict(request=request, validation=validation))


def _prepare_action(*, for_retention, **arguments):
    v26 = previous.previous
    return v26.previous._with_globals(v26._prepare_action,
        {'_validate_inputs': _validate_inputs,
         'qualified_archive_profile': qualified_archive_profile},
        dict(for_retention=for_retention, **arguments))


def prepare_action(**arguments):
    return _prepare_action(for_retention=False, **arguments)


def prepare_retention(**arguments):
    return _prepare_action(for_retention=True, **arguments)


def execute_once(**arguments):
    prepared = prepare_action(**arguments)
    v26 = previous.previous
    if not is_archived(prepared.request):
        return v26.previous._with_globals(v26.previous.execute_once,
            {'prepare_action': lambda **unused: prepared}, arguments)
    import stage17_fixed_action_executor_v11 as original_executor
    executor = metadata.make_executor(original_executor)
    return executor.execute_fixed_action(repository_root=prepared.root,
        authorization=prepared.authorization, authorization_bytes=prepared.authorization_bytes,
        request=prepared.request, request_bytes=prepared.request_bytes,
        worker_binding=prepared.runtime, worker_path=prepared.worker_path,
        release_binding=prepared.release,
        output_root=Path(prepared.request['evidence_root_binding']['absolute_path']),
        archive_runtime_profile=prepared.archive_runtime_profile,
        synthetic_test_only=arguments.get('synthetic_test_only', False))
