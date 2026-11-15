"""D255 actual platform association in an explicit cold administrative scope.

EXT006 describes portable release bytes; EXT004 supplies the authenticated
stand association in the same validated journal. The private compatibility
view derives this one field from EXT004. It preserves every original source,
worker, inventory, platform and qualification binding and never mutates the
original context or represents the derived field as an original EXT006 fact.
The native release and all v6 authority bodies remain unchanged.
"""
from __future__ import annotations

import types

import stage17_archive_metadata_fast_v1 as metadata
import stage17_q16a_daycap_handoff_v1 as handoff
import stage17_phase_controller_daycap_v1 as original_controller
import stage17_operational_cli_daycap_v1 as original_cli


def associated_validation(validation, stand_id):
    """Use the actual journal's platform association, never a guessed value."""
    if not isinstance(stand_id, str) or not stand_id:
        raise handoff.Error('D255 requires an explicit verified stand identity')
    platform = validation.resolutions['S17-EXT-004'].semantic_context
    release = validation.resolutions['S17-EXT-006'].semantic_context
    if platform.get('stand_id') != stand_id:
        raise handoff.Error('D255 platform does not match the actual plan stand')
    if 'stand_id' in release and release['stand_id'] != stand_id:
        raise handoff.Error('D255 contradictory release association')
    # Current signed request authoring separately obtains this stand from EXT002;
    # preserve that independent gate when the complete current context is present.
    trust = validation.resolutions.get('S17-EXT-002')
    if trust is not None and trust.semantic_context.get('stand_id') != stand_id:
        raise handoff.Error('D255 trusted owner context belongs to a different stand')
    resolutions = dict(validation.resolutions)
    resolutions['S17-EXT-006'] = types.SimpleNamespace(
        semantic_context={**release, 'stand_id': platform['stand_id']})
    return types.SimpleNamespace(resolutions=resolutions)


def consume(document, *, validation, plan, selected_duration_ns, original_validation,
            original_plan, compatibility, original_boot_id, boot_id):
    """Keep every D254 compatibility gate, with an explicit derived association."""
    return handoff.consume(document,
        validation=associated_validation(validation, plan['stand_id']), plan=plan,
        selected_duration_ns=selected_duration_ns,
        original_validation=associated_validation(original_validation, original_plan['stand_id']),
        original_plan=original_plan, compatibility=compatibility,
        original_boot_id=original_boot_id, boot_id=boot_id)


def make_controller():
    """Rebuild the fixed private v25/v26 graph with only the D255 handoff view."""
    controller = original_controller._clone_module(original_controller,
        {'handoff': types.SimpleNamespace(**{**vars(handoff), 'consume': consume}),
         '_HISTORICAL': None})
    scope = controller.prepare_action.__globals__
    v25 = original_controller._clone_module(original_controller.original_v25,
        {'journal_runtime': controller.journal_runtime, 'activate': controller.activate})
    v26 = original_controller._clone_module(original_controller.original_v26,
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
    """Explicit administrative entry point; imports cannot alter native identity."""
    scope = dict(vars(original_cli))
    scope['controller'] = make_controller()
    clones = {}
    for name, function in vars(original_cli).items():
        if isinstance(function, types.FunctionType) and function.__module__ == original_cli.__name__:
            if function not in clones:
                clones[function] = metadata._clone(function, scope)
            scope[name] = clones[function]
    return types.SimpleNamespace(**scope)
