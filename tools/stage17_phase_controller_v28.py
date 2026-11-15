"""Cold archive overlay admission over the preserved v27 Q16a handoff.

Only archive-profile selection changes. The v26 formal preparation, signature,
namespace and UTC gates and the qualified native worker remain unchanged.
"""
from __future__ import annotations

import stage17_phase_controller_v27 as previous
import stage17_archive_overlay_v1 as overlay

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
    v26 = previous.previous
    return v26.previous._with_globals(v26.execute_once,
        {'prepare_action': prepare_action}, arguments)
