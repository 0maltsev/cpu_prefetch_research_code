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
from pathlib import Path

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


admission = original_controller.admission
SCHEMA = original_controller.SCHEMA
CONTEXT_SCHEMA = original_controller.CONTEXT_SCHEMA
_uuid = original_controller._uuid

def _read_historical_associated(raw, root):
    document = admission._json(raw)
    admission.fields(document, 'schema_version historical_context original_plan compatibility boot_id '
                     'execution_authority phase18_authority', 'historical configuration')
    admission.same(document['schema_version'], SCHEMA, 'historical configuration schema')
    _uuid(document['boot_id'])
    for flag in ('execution_authority', 'phase18_authority'):
        admission.same(document[flag], False, 'historical configuration authority')
    reader = admission.BoundReader()
    for key in ('historical_context', 'compatibility'):
        admission.require(Path(document[key]['path']).parent == root, 'historical packet namespace: ' + key)
    context = reader.document(document['historical_context'])
    admission.fields(context, 'schema_version boot_id resolutions execution_authority phase18_authority',
                     'historical context export')
    admission.same(context['schema_version'], CONTEXT_SCHEMA, 'historical context export schema')
    _uuid(context['boot_id'])
    admission.same(context['boot_id'], document['boot_id'], 'same historical/current verified boot')
    for flag in ('execution_authority', 'phase18_authority'):
        admission.same(context[flag], False, 'historical context authority')
    admission.fields(context['resolutions'], 'S17-EXT-004 S17-EXT-006', 'historical context resolutions')
    resolutions = {}
    for key, row in context['resolutions'].items():
        admission.fields(row, 'semantic_context', 'historical resolution')
        admission.require(type(row['semantic_context']) is dict, 'actual old semantic context required')
        resolutions[key] = types.SimpleNamespace(semantic_context=row['semantic_context'])
    validation = types.SimpleNamespace(resolutions=resolutions)
    old = resolutions['S17-EXT-006'].semantic_context
    admission.same(old['source_revision'], handoff.original.SOURCE, 'actual historical source42')
    admission.same(old['release_artifact_sha256'], handoff.OLD_WORKER, 'actual historical worker7ab')
    admission.same(old['inventory_sha256'], handoff.original.INVENTORY, 'actual historical inventory')
    plan = reader.document(document['original_plan'])
    admission.same(plan['source_revision'], old['source_revision'], 'actual old plan source')
    # D255: derive the private association before the preserved stand checks.
    validation = associated_validation(validation, plan['stand_id'])
    resolutions = validation.resolutions
    for key in resolutions:
        admission.same(plan['stand_id'], resolutions[key].semantic_context['stand_id'], 'actual old plan stand')
    proof = reader.document(document['compatibility'])
    admission.same(proof['schema_version'], handoff.SCHEMA, 'bound compatibility schema')
    admission.same(proof['original_plan'], document['original_plan'], 'actual historical plan binding')
    admission.same(proof['scope'], dict(decision='D254', purpose=handoff.PURPOSE,
        stand_id=plan['stand_id'], boot_id=document['boot_id']), 'bound compatibility scope')
    for flag in ('execution_authority', 'phase18_authority'):
        admission.same(proof[flag], False, 'compatibility authority')
    reader.finish()
    return document, context, validation, plan, proof


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
         '_HISTORICAL': None, '_read_historical': _read_historical_associated})
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
