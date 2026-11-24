"""D250 explicit formal administration with v27 Q16a handoff admission.

Deploy only through a separately authenticated administrative packet. The
qualified v18 sources, worker and historical D242 adapter remain unchanged.
Authoring does not sign; admission still requires the original v6 signature.
"""
from __future__ import annotations

import sys
import types

import stage17_operational_cli_v18 as previous
import stage17_operational_cli_v19 as administrative_previous
import stage17_phase_controller_v27 as controller
import stage17_state_journal_v53 as recovery

COMMANDS = frozenset(('author-formal-request', 'author-formal-authorization',
    'verify-formal-signature', 'execute-formal', 'admit-formal-retention'))
FUNCTIONS = ('_validation', 'author_formal_request', 'author_formal_authorization',
    'verify_formal_signature', 'execute_formal', 'prepare_formal_retention',
    'admit_formal_retention', 'main')


def activate():
    previous.activate()
    # Restore the already accepted historical transition adapter after legacy
    # import/activation side effects. No recovery transition is authored here.
    recovery.activate()


def formal_functions():
    """One private namespace for the preserved v18 formal command bodies."""
    scope = {**vars(previous), 'controller': controller, 'activate': activate}
    for name in FUNCTIONS:
        original = getattr(previous, name)
        function = types.FunctionType(original.__code__, scope, name,
                                      original.__defaults__, original.__closure__)
        function.__kwdefaults__ = original.__kwdefaults__
        scope[name] = function
    return scope


def author_formal_request(**arguments):
    return formal_functions()['author_formal_request'](**arguments)


def author_formal_authorization(**arguments):
    return formal_functions()['author_formal_authorization'](**arguments)


def verify_formal_signature(**arguments):
    return formal_functions()['verify_formal_signature'](**arguments)


def execute_formal(**arguments):
    return formal_functions()['execute_formal'](**arguments)


def prepare_formal_retention(**arguments):
    return formal_functions()['prepare_formal_retention'](**arguments)


def admit_formal_retention(prepared, output_root):
    return formal_functions()['admit_formal_retention'](prepared, output_root)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        return administrative_previous.main()
    return formal_functions()['main']()


if __name__ == '__main__':
    raise SystemExit(main())
