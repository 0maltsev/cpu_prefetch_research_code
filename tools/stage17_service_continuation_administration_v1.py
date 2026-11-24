"""D260 private /4 controller over the freshly qualified D263 release.

Callers authenticate this complete cold packet. The original phase-action
signature, UTC, journal, hardware, namespace, resources, archive and one-attempt
gates remain mandatory. No E26 renewal or historical module mutation is used.
"""
import types

import stage17_phase_controller_daycap_v2 as qualification
import stage17_operational_cli_daycap_v2 as original_cli
import stage17_daycap_administration_v1 as association
import stage17_archive_metadata_fast_v1 as metadata
import stage17_archive_daycap_overlay_v1 as old_overlay
import stage17_formal_service_continuation_v2 as continuation
import stage17_service_continuation_execution_v1 as execution
import stage17_q16a_service_continuation_handoff_v1 as handoff
import stage17_service_prefix_admission_v1 as prefix


def make_controller():
    original = association.original_controller
    view = handoff.make_handoff()
    associated_view = types.SimpleNamespace(**{**vars(view), 'consume': handoff.consume})
    historical_reader = metadata._clone(association._read_historical_associated,
        {**association._read_historical_associated.__globals__, 'handoff': associated_view})
    overlay = original._clone_module(old_overlay, {'daycap': continuation, '_CONFIG': None})
    contract = execution.make_contract()
    controller = original._clone_module(original,
        {'handoff': associated_view, '_HISTORICAL': None, '_read_historical': historical_reader,
         'journal_runtime': qualification.journal, 'execution': execution, 'overlay': overlay,
         'contract': types.SimpleNamespace(**{**vars(original.contract),
             'validate_plan': contract.validate_plan, 'is_archived_plan': contract.is_archived_plan}),
         'registry': execution.make_output_registry()})
    scope = controller.prepare_action.__globals__

    def is_continuation(request):
        return (request.get('action_id') == 'Q16b'
                and isinstance(request.get('action_inputs', {}).get('plan'), dict)
                and request['action_inputs']['plan'].get('schema_version') == continuation.VERSION)

    prior_validate = controller._validate_inputs

    def validate_inputs(request, validation):
        if not is_continuation(request):
            raise controller.ControllerError('D260 administration requires explicit Q16b service-plan/4')
        # Both the completed Q16a handoff and original17 Q16b prefix are gates;
        # either failure propagates before a new native worker can be admitted.
        extent = prior_validate(request, validation)
        accepted = prefix.admit(request['action_inputs']['plan'], validation)
        if accepted != extent:
            raise controller.ControllerError('D260 prefix and native suffix extents disagree')
        return extent

    scope.update(_is_daycap=is_continuation, _validate_inputs=validate_inputs,
                 configure_verified_descriptor=overlay.configure_verified_descriptor)
    v25 = original._clone_module(original.original_v25,
        {'journal_runtime': qualification.journal, 'activate': controller.activate})
    v26 = original._clone_module(original.original_v26,
        {'previous': v25, 'activate': controller.activate, 'contract': controller.contract,
         '_contract': controller.contract, 'is_archived': controller.is_archived,
         '_validate_inputs': validate_inputs,
         'qualified_archive_profile': controller.qualified_archive_profile,
         '_prepare_action': controller._prepare_archive})
    scope.update(_v25=v25, _v26=v26, runtime_from_context=v25.runtime_from_context,
                 _runtime_from_context=v25._runtime_from_context,
                 _validate_action_inputs=v25._validate_action_inputs,
                 make_executor=execution.make_executor)
    return types.SimpleNamespace(**scope)


def make_cli():
    scope = dict(vars(original_cli))
    scope.update(controller=make_controller(), registry=execution.make_output_registry(),
                 daycap_execution=execution)
    for name, function in vars(original_cli).items():
        if isinstance(function, types.FunctionType) and function.__module__ == original_cli.__name__:
            scope[name] = metadata._clone(function, scope)
    return types.SimpleNamespace(**scope)
