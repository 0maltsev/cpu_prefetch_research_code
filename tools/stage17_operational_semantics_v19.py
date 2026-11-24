"""D308 complete chronological/categorical membership; preserve frozen v18."""
import hashlib
import inspect
from pathlib import Path
import stage17_operational_semantics_v18 as previous

PARENT_SHA = '9f22d8cac35779f97e0ab8c9a3eb405a1c335e83687457ce2a2e6879f6657a53'


def verify_manifest_v19(**arguments):
    previous.require(hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() == PARENT_SHA,'exact preserved semantics18')
    text = inspect.getsource(previous.verify_manifest_v18)
    old = "exact([r['sha256'] for r in journal['resolution_records']],[p['sha256'] for p in predecessors],"
    new = "exact(sorted(r['sha256'] for r in journal['resolution_records']),sorted(p['sha256'] for p in predecessors),"
    previous.require(text.count(old) == 1,'exact journal-membership comparison seam')
    text = text.replace(old,new).replace('def verify_manifest_v18(','def verify_manifest_v19(',1)
    scope = dict(vars(previous)); exec(compile(text,__file__+':preserved-verifier','exec'),scope)
    return scope['verify_manifest_v19'](**arguments)


verify_manifest_v18 = verify_manifest_v19


def __getattr__(name): return getattr(previous,name)
