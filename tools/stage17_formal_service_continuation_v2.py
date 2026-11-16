"""D264 explicit whole-family watchdog recalculation over the D260 /4 design.

The qualified v1 module and every original byte/hash remain unchanged. Only its
parent-budget equality check receives a private copied parent with the reviewed
suffix watchdog. The real original parent is authenticated before this seam.
All other original declarations, capture comparisons and limits run unchanged.
"""
import copy

import stage17_formal_service_continuation_v1 as previous
import stage17_archive_metadata_fast_v1 as metadata

ADMISSION_VERSION = 'cpu-prefetch-stage17-formal-service-continuation-admission/2'
validate_plan = previous.validate_plan
plan_bytes = previous.plan_bytes


def _compare_parent(plan, parent):
    required = validate_plan(plan).required_watchdog_ns
    watchdog = plan['budget']['watchdog_ns']
    previous.native._require(required <= watchdog <= parent['budget']['watchdog_ns'],
        'continuation', 'family watchdog omits suffix work or extends the original bound')
    adjusted = copy.deepcopy(parent)
    adjusted['budget']['watchdog_ns'] = watchdog
    return previous._compare_parent(plan, adjusted)


def validate_parent(plan, original_plan_bytes):
    scope = {**previous.validate_parent.__globals__, '_compare_parent': _compare_parent}
    return metadata._clone(previous.validate_parent, scope)(plan, original_plan_bytes)


def __getattr__(name):
    return getattr(previous, name)
