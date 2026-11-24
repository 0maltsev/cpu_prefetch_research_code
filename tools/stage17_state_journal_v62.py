"""D308 policy65 journal; unchanged v12 append/replay/state contracts."""
from pathlib import Path
import types
import stage17_state_journal_v12 as core
import stage17_semantic_verifier_v65 as semantic

SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = core.SCHEMA_PATHS
JournalError = core.JournalError
ExternalInputResolution = core.ExternalInputResolution
StateTransition = core.StateTransition
OperationalJournalValidation = core.OperationalJournalValidation


def activate():
    scope = {**vars(core),'semantic':semantic,'SEMANTIC_POLICY_PATH':SEMANTIC_POLICY_PATH}
    for name,fn in vars(core).items():
        if isinstance(fn,types.FunctionType) and fn.__module__ == core.__name__:
            cloned = types.FunctionType(fn.__code__,scope,fn.__name__,fn.__defaults__,fn.__closure__)
            cloned.__kwdefaults__ = fn.__kwdefaults__; scope[name] = cloned
    return types.SimpleNamespace(**scope)


configure = activate


def validate_operational_journal(**arguments):
    return activate().validate_operational_journal(**arguments)


def checked_in_status(root):
    root = Path(root).resolve(); latest = root/'config/stage17/journal/stage17-state-journal-000000.json'
    return validate_operational_journal(repository_root=root,evidence_root=root,latest_journal=latest,journal_directory=latest.parent)
