"""D247 archived admission of the exact two-source Q16a handoff.

All signature, journal, deadline, namespace and archive-profile gates stay v26.
The qualified native worker and measurement code remain unchanged.
"""
from __future__ import annotations

import types

import stage17_phase_controller_v26 as previous
import stage17_q16a_handoff_v1 as handoff

ControllerError = previous.ControllerError
contract = previous.contract
activate = previous.activate
support = previous.support
runtime_from_context = previous.runtime_from_context
deadline_policy = previous.deadline_policy
is_archived = previous.is_archived
_runtime_from_context = previous._runtime_from_context
_validate_action_inputs = previous._validate_action_inputs


def _validate_inputs(request, validation):
    if request['action_id'] not in ('Q16b', 'Q16c'):
        return previous._validate_inputs(request, validation)
    legacy = previous.previous
    checked = {}

    def prior(result, prior, plan, selected_duration_ns):
        if prior == 'Q16a' and result.get('schema_version') == handoff.SCHEMA:
            try:
                checked['Q16a'] = handoff.consume(result, validation=validation, plan=plan,
                                                selected_duration_ns=selected_duration_ns)
            except handoff.Error as error:
                raise ControllerError(str(error)) from error
            return
        return legacy._with_globals(legacy.validate_prior_calibration,
            {'calibration': previous.calibration}, dict(result=result, prior=prior,
                plan=plan, selected_duration_ns=selected_duration_ns))

    def ring(plan, ring_result, binding):
        return legacy.validate_ring_reuse(plan, checked.get('Q16a', ring_result), binding)

    return legacy._with_globals(legacy.validate_action_inputs,
        {'contract': previous.contract, 'validate_prior_calibration': prior,
         'validate_ring_reuse': ring,
         'registry': types.SimpleNamespace(**{**vars(legacy.registry), 'canonical': previous.archive.canonical})},
        dict(request=request, validation=validation))


def validate_action_inputs(request, validation):
    return previous.previous._with_globals(previous.validate_action_inputs,
        {'_validate_inputs': _validate_inputs}, dict(request=request, validation=validation))


def _prepare_action(*, for_retention, **arguments):
    return previous.previous._with_globals(previous._prepare_action,
        {'_validate_inputs': _validate_inputs}, dict(for_retention=for_retention, **arguments))


def prepare_action(**arguments):
    return _prepare_action(for_retention=False, **arguments)


def prepare_retention(**arguments):
    return _prepare_action(for_retention=True, **arguments)


def execute_once(**arguments):
    return previous.previous._with_globals(previous.execute_once,
        {'prepare_action': prepare_action}, arguments)
