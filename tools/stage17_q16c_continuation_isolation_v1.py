"""D285 fresh isolation receipts, retaining the actual passed clock/Q15 evidence.

Only the frozen isolation core prepares/restores controls. No qualification
capture is exposed or called by this continuation adapter.
"""
import copy
import hashlib
from pathlib import Path
import types

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29')
BASE=E/'operator-preparation-v29/run_clock_qualification_v29.py'
BASE_SHA='827a02579c1003c0b2c0c962090be68350ec27f7d2eba78b8ed3c7797a1bcda0'
_BASE=None


def load_base():
    global _BASE
    if _BASE is None:
        raw=BASE.read_bytes()
        if any(p.is_symlink() for p in (BASE,*BASE.parents)) or hashlib.sha256(raw).hexdigest()!=BASE_SHA:
            raise ValueError('D285 exact qualified isolation adapter required')
        module=types.ModuleType('q16c_d285_original_isolation');module.__file__=str(BASE)
        exec(compile(raw,str(BASE),'exec'),module.__dict__)
        config=copy.deepcopy(module.BINDINGS)
        config['isolation_config']['evidence_root']=str(E/'isolation-preparation-v29-2')
        module.configure(config);module.Q=E/'q16c-continuation-recovery-1';_BASE=module
    return _BASE


def __getattr__(name):
    if name in ('main','capture'):raise AttributeError(name)
    return getattr(load_base(),name)
