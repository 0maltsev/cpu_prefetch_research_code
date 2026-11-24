"""D256 private cold graph: D255 association plus signed E26 transition renewal.

The qualified native release, original journals and cached historical journal
functions remain unchanged. Importing this module performs no state mutation.
"""
from __future__ import annotations

import types

import stage17_daycap_administration_v1 as previous
import stage17_state_journal_v55 as journal


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


def make_cli():
    scope = dict(vars(previous.original_cli))
    scope.update(controller=make_controller(), journal=journal)
    clones = {}
    for name, function in vars(previous.original_cli).items():
        if isinstance(function, types.FunctionType) and function.__module__ == previous.original_cli.__name__:
            if function not in clones:
                clones[function] = previous.metadata._clone(function, scope)
            scope[name] = clones[function]
    return types.SimpleNamespace(**scope)
