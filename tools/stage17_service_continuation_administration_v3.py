"""D267 finite authority preparation margin; native plan bounds stay unchanged."""
import stage17_service_continuation_administration_v2 as previous

SESSION_SECONDS=57600
NATIVE_SECONDS=55860


def deadline_policy(extent):
    if len(extent.captures)!=103 or extent.declared.watchdog_ns!=NATIVE_SECONDS*10**9:
        raise previous.previous.association.original_controller.ControllerError('D267 requires the exact103 native budget')
    policy=previous.previous.association.original_controller.original_v25.deadline_policy(extent)
    return {**policy,'session_max_wall_seconds':SESSION_SECONDS}


def make_controller():
    view=previous.make_controller()
    view.deadline_policy=deadline_policy
    view.prepare_action.__globals__['deadline_policy']=deadline_policy
    view._v25.deadline_policy=deadline_policy
    view._v25._prepare_action.__globals__['deadline_policy']=deadline_policy
    view._v26.deadline_policy=deadline_policy
    return view


def make_cli():
    return previous.previous.metadata._clone(previous.previous.make_cli,
        {**previous.previous.make_cli.__globals__,'make_controller':make_controller})()
