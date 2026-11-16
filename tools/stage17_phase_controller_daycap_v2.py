"""D263 fresh policy60 qualification controller; all action gates remain intact.

No E26 incident adapter or /4 execution admission is selected by this module.
"""
import stage17_daycap_administration_v1 as previous
import stage17_state_journal_v56 as journal
import types

def make_controller():
    original = previous.original_controller
    controller = original._clone_module(original,
        {'handoff': types.SimpleNamespace(**{**vars(previous.handoff), 'consume': previous.consume}),
         '_HISTORICAL': None, '_read_historical': previous._read_historical_associated,
         'journal_runtime': journal})
    scope = controller.prepare_action.__globals__
    v25 = original._clone_module(original.original_v25,
        {'journal_runtime': journal, 'activate': controller.activate})
    v26 = original._clone_module(original.original_v26,
        {'previous': v25, 'activate': controller.activate, 'contract': controller.contract,
         '_contract': controller.contract, 'is_archived': controller.is_archived,
         '_validate_inputs': controller._validate_inputs,
         'qualified_archive_profile': controller.qualified_archive_profile,
         '_prepare_action': controller._prepare_archive})
    scope.update(_v25=v25, _v26=v26, runtime_from_context=v25.runtime_from_context,
        _runtime_from_context=v25._runtime_from_context,
        _validate_action_inputs=v25._validate_action_inputs)
    return types.SimpleNamespace(**scope)


_CONTROLLER = make_controller()

def __getattr__(name):
    return getattr(_CONTROLLER, name)

def activate():
    return _CONTROLLER.activate()
