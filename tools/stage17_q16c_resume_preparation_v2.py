"""D285 manual continuation of the unarmed D282 constructor, using D284.

Reuse only exact deterministic partial JSON; original packet and failure stay
immutable. The original constructor/signature and every validator still run.
"""
import hashlib
import json
from pathlib import Path
import types

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29')
PACKET=E/'q16c-configuration-1'
BASE=PACKET/'stage17_q16c_prepare_v3.py'
BASE_SHA='22a6e50707541f3ae770be805ef1d0282ec5ac933dc97a0e99f5c779b6635cea'
REUSED=frozenset(('q16a-context.json','q16b-context.json','q16a-compatibility.json',
    'q16b-compatibility.json','historical-inputs.json','archive-overlay.json',
    'cli-configuration.json','namespace-registry.json'))
_BASE=None


def require(ok,message):
    if not ok:raise ValueError('D285 metadata continuation: '+message)


def load_base():
    global _BASE
    if _BASE is None:
        raw=BASE.read_bytes()
        require(not any(p.is_symlink() for p in (BASE,*BASE.parents))
            and hashlib.sha256(raw).hexdigest()==BASE_SHA,'exact original constructor')
        module=types.ModuleType('q16c_d285_original_constructor');module.__file__=str(BASE)
        exec(compile(raw,str(BASE),'exec'),module.__dict__);_BASE=module
    return _BASE


def __getattr__(name):return getattr(load_base(),name)


def loader_for(c):return load_base().loader_for(c)


def validate_incident(stopped,restored,verified,construct_log):
    require(stopped['success'] is False and len(stopped['phases'])==1
        and stopped['phases'][0]['role']=='construct' and stopped['phases'][0]['exit_code']==1
        and stopped['phases'][0]['leader_reaped'] is True
        and stopped['errors']==["RuntimeError('Q16c study: construct failed')"]
        and 'construct failed' in stopped['failure_traceback']
        and b"unsupported JSON value: <class 'set'>" in construct_log,
        'exact stopped pre-arm constructor incident')
    require(restored['verified'] is True and restored['errors']==[],'actual previous restoration')
    require(verified['status']=='PASS' and verified['full_constructor_validation_passed'] is True
        and verified['actual_qualified_source']=='7fb894425c82fa7d7f1891f52b3bcdacc2c83585'
        and verified['actual_qualified_worker_sha256']=='7455fa2802ca5f655c41faddd070da51b0cf98ac9c8b2360152dc1a480f85f2a'
        and verified['experimental_actions']==0 and verified['collection_restarted'] is False
        and verified['original_ledger_before']==verified['original_ledger_after'],
        'actual successful D284 complete constructor validation')


def publisher(base,c):
    packet=Path(c['packet_root']);require(packet==PACKET,'original packet namespace')
    retained=c['retained_metadata'];require(set(retained)==REUSED,'exact eight partial outputs')
    def save(path,value):
        p=Path(path)
        if p.parent==packet and p.name in REUSED:
            bound=retained[p.name]
            require(bound['path']==str(p),'original retained output path')
            raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            require(base.read(bound)==raw,'retained output differs: '+p.name)
            return bound
        return base.save(p,value)
    return save


def construct(c):
    base=load_base()
    require(c['output_root']==str(E/'q16c-authoring-2') and c['packet_root']==str(PACKET),
        'fresh continuation authoring and unchanged packet')
    validate_incident(*(base.document(c['files'][k]) for k in
        ('prior_study_complete','prior_partition_restoration','verified_repair')),
        base.read(c['files']['prior_construct_log']))
    for b in c['retained_metadata'].values():base.read(b)
    scope=dict(vars(base),save=publisher(base,c))
    return types.FunctionType(base.construct.__code__,scope)(c)


def main():
    base=load_base()
    types.FunctionType(base.main.__code__,dict(vars(base),construct=construct))()


if __name__=='__main__':main()
