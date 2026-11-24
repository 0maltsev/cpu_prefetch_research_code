"""Generic policy61 journal; private copies of the complete v12 journal gates.

No incident recovery, pinned stand/source identity, or transition substitution.
Activation rebuilds an independent function scope instead of rewriting any
historical journal's semantic bindings or validation entry point.
"""
from __future__ import annotations

import pathlib
import types

import stage17_state_journal_v12 as core
import stage17_semantic_verifier_v61 as semantic

SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = core.SCHEMA_PATHS
JournalError = core.JournalError
ExternalInputResolution = core.ExternalInputResolution
StateTransition = core.StateTransition
OperationalJournalValidation = core.OperationalJournalValidation
_RUNTIME = None


def activate():
    """Select policy61 in a private copy, after any legacy import side effects."""
    global _RUNTIME
    scope = {**vars(core), 'semantic': semantic, 'SEMANTIC_POLICY_PATH': SEMANTIC_POLICY_PATH}
    for name, function in vars(core).items():
        if isinstance(function, types.FunctionType) and function.__module__ == core.__name__:
            clone = types.FunctionType(function.__code__, scope, function.__name__,
                                       function.__defaults__, function.__closure__)
            clone.__kwdefaults__ = function.__kwdefaults__
            scope[name] = clone
    _RUNTIME = types.SimpleNamespace(**scope)
    return _RUNTIME


configure = activate


def validate_operational_journal(**arguments):
    return activate().validate_operational_journal(**arguments)


def checked_in_status(root: pathlib.Path):
    repository = root.resolve()
    latest = repository / 'config/stage17/journal/stage17-state-journal-000000.json'
    return validate_operational_journal(repository_root=repository, evidence_root=repository,
        latest_journal=latest, journal_directory=latest.parent)
