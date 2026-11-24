"""Explicit formal CLI using the authenticated cold archive overlay controller.

Preserved formal bodies retain v6 authority and the D242 recovery activation.
The original v20 module and its private namespaces remain unchanged.
"""
from __future__ import annotations

import sys
import types

import stage17_operational_cli_v20 as previous
import stage17_phase_controller_v28 as controller

administrative_previous = previous.administrative_previous
recovery = previous.recovery
COMMANDS = previous.COMMANDS
FUNCTIONS = previous.FUNCTIONS


def activate():
    previous.activate()


def formal_functions():
    """Clone the v20 formal namespace, replacing only its controller/activation."""
    scope = {**previous.formal_functions(), 'controller': controller, 'activate': activate}
    for name in FUNCTIONS:
        original = scope[name]
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
