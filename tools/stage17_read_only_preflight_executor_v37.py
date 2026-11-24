#!/usr/bin/env python3
"""Fresh policy37 preflight, with the original v25 gates and policy63 journal.

Only identity and journal selection change. Every v25 local function runs in
one private scope, retaining UTC, namespace, marker, one-attempt, cleanup and
OpenSSH checks without changing historical executor or journal globals.
"""
from __future__ import annotations

import pathlib
import types

import stage17_read_only_preflight_executor_v25 as owner
import stage17_read_only_preflight_executor_v26 as identity_owner
import stage17_state_journal_v60 as current_journal

EXECUTOR_ID = 'STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v37'
ActionExecutionError = owner.ActionExecutionError
_SCOPE = None


def runtime_identity_paths():
    scope = {**vars(owner), 'current_journal': current_journal}
    original = identity_owner._base_runtime_identity_paths
    paths = types.FunctionType(original.__code__, scope)()
    paths['executor'] = str(pathlib.Path(__file__).resolve())
    paths['state_journal'] = str(pathlib.Path(current_journal.__file__).resolve())
    return paths


def activate():
    global _SCOPE
    current_journal.activate()
    scope = {**vars(owner), 'current_journal': current_journal, 'EXECUTOR_ID': EXECUTOR_ID,
             'runtime_identity_paths': runtime_identity_paths}
    for name, function in vars(owner).items():
        if (isinstance(function, types.FunctionType) and function.__module__ == owner.__name__
                and name != 'runtime_identity_paths'):
            clone = types.FunctionType(function.__code__, scope, function.__name__,
                                       function.__defaults__, function.__closure__)
            clone.__kwdefaults__ = function.__kwdefaults__
            scope[name] = clone
    _SCOPE = scope
    return types.SimpleNamespace(**scope)


def execute_once(**arguments):
    return activate().execute_once(**arguments)


def main():
    return activate().main()


if __name__ == '__main__':
    raise SystemExit(main())
