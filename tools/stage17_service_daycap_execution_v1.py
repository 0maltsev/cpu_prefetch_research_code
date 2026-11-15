"""D254 private execution adapters; no phase or experiment authority.

Historical plans keep their original v2 dispatch. Only the explicit Q16b /3
family selects the approved descriptive day-cap validator. The caller still
owns release qualification, signatures, roots and one-attempt admission.
"""
from __future__ import annotations

import time
import types

import stage17_archive_flow_private_v1 as flow
import stage17_archive_inventory_native_v1 as inventory
import stage17_archive_metadata_fast_v1 as metadata
import stage17_formal_plan_v2 as historical
import stage17_formal_service_daycap_v1 as daycap
import stage17_output_registry_v12 as original_registry


def make_contract():
    """Return an independent contract without adding synthetic action keys."""
    def validate_plan(action, document):
        if (action == 'Q16b' and isinstance(document, dict)
                and document.get('schema_version') == daycap.VERSION):
            return daycap.validate_plan(document)
        return historical.validate_plan(action, document)

    def is_archived_plan(action, document):
        return (action == 'Q16b' and isinstance(document, dict)
                and document.get('schema_version') == daycap.VERSION
                or historical.is_archived_plan(action, document))

    return types.SimpleNamespace(**{**vars(historical),
        'VERSION': dict(historical.VERSION), 'SCHEMA': dict(historical.SCHEMA),
        'validate_plan': validate_plan, 'is_archived_plan': is_archived_plan})


def _make_output_registry(contract, scoped_custody):
    scope = dict(vars(original_registry))
    scope.update(contract=contract, custody=scoped_custody,
                 archive=metadata._archive_namespace(original_registry.archive))
    clones = {}
    for name, function in vars(original_registry).items():
        if (isinstance(function, types.FunctionType)
                and function.__module__ == original_registry.__name__):
            if function not in clones:
                clones[function] = metadata._clone(function, scope)
            scope[name] = clones[function]
    return types.SimpleNamespace(**scope)


def make_output_registry(contract=None):
    """Clone every v12 local function into one fresh private globals map."""
    scoped_custody = types.SimpleNamespace(**{**vars(original_registry.custody),
        'ProgramStore': inventory.make_store_class(base=original_registry.custody.ProgramStore)})
    return _make_output_registry(make_contract() if contract is None else contract, scoped_custody)


def is_archived(request):
    """Use the original request-format gate with the extended plan contract."""
    scope = {**original_registry.is_archived.__globals__, 'contract': make_contract()}
    return metadata._clone(original_registry.is_archived, scope)(request)


def _execute_fixed_action(*, archive_runtime_profile, **arguments):
    # Static v12 body: only these private aliases replace its local imports.
    request = arguments['request']
    if not is_archived(request):
        return previous.execute_fixed_action(**arguments)
    plan = request['action_inputs']['plan']
    extent = plans.validate_plan(request['action_id'], plan)
    if archive_runtime_profile.decoder.implementation_profile_sha256 != plan['storage']['implementation_profile_sha256']:
        raise FixedActionExecutionError('ARCHIVE_PROFILE', 'qualified runtime differs from signed storage plan')
    deadline = time.monotonic_ns() + extent.declared.watchdog_ns

    def resources(directory_fd, declared):
        return live_resources(directory_fd, declared, request=request, deadline_ns=deadline)

    def worker(argv, pass_fds, **values):
        return run_archived_worker(argv, pass_fds, request=request, profile=archive_runtime_profile,
                                   extent=extent, **values)

    def validate_result(**values):
        return output_registry.verify_archived_formal_metadata(repository_root=arguments['repository_root'],
            archive_runtime_profile=archive_runtime_profile, deadline_ns=deadline, **values)

    namespace = dict(previous.execute_fixed_action.__globals__)
    namespace.update(contract=plans, live_resources=resources, _run_formal_worker=worker,
        output_registry=types.SimpleNamespace(**{**vars(output_registry), 'validate_worker_result': validate_result}))
    execute = types.FunctionType(previous.execute_fixed_action.__code__, namespace,
                                 argdefs=previous.execute_fixed_action.__defaults__)
    execute.__kwdefaults__ = previous.execute_fixed_action.__kwdefaults__
    return execute(**arguments)


def make_executor():
    """Compose the unchanged v12 worker/finish transaction and native inventory.

    execute_fixed_action accepts v12's ordinary keyword arguments. All worker
    cleanup and v10 authority checks remain in their original function bodies.
    """
    result = flow.make_executor()
    scope = result.execute_fixed_action.__globals__
    contract = make_contract()
    registry = _make_output_registry(contract, result.custody)
    scope.update(plans=contract, is_archived=registry.is_archived, output_registry=registry)
    scope['execute_fixed_action'] = metadata._clone(_execute_fixed_action, scope)
    result.plans = contract
    result.is_archived = registry.is_archived
    result.output_registry = registry
    result.execute_fixed_action = scope['execute_fixed_action']
    return result
