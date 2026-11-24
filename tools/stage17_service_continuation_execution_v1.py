"""D260 private /4 execution transport; admission remains the caller's duty.

The native worker is separately qualified. This adapter retains the original
archive worker, finish transaction, process ownership and resource checks. It
does not accept a prefix, a compatibility proof or an execution authorization.
Those are independent prerequisites at the controller boundary.
"""
from __future__ import annotations

import types

import stage17_service_daycap_execution_v1 as previous
import stage17_formal_service_continuation_v2 as continuation


def make_contract():
    original = previous.make_contract()

    def selected(action, document):
        return (action == 'Q16b' and isinstance(document, dict)
                and document.get('schema_version') == continuation.VERSION)

    def validate_plan(action, document):
        if selected(action, document):
            return continuation.validate_plan(document)
        return original.validate_plan(action, document)

    def is_archived_plan(action, document):
        return selected(action, document) or original.is_archived_plan(action, document)

    return types.SimpleNamespace(**{**vars(original),
        'validate_plan': validate_plan, 'is_archived_plan': is_archived_plan})


def make_output_registry(contract=None):
    old = previous.make_output_registry()
    return previous._make_output_registry(
        make_contract() if contract is None else contract, old.custody)


def is_archived(request):
    return make_output_registry().is_archived(request)


def make_executor():
    result = previous.make_executor()
    scope = result.execute_fixed_action.__globals__
    contract = make_contract()
    registry = previous._make_output_registry(contract, result.custody)
    scope.update(plans=contract, is_archived=registry.is_archived, output_registry=registry)
    result.plans = contract
    result.is_archived = registry.is_archived
    result.output_registry = registry
    return result
