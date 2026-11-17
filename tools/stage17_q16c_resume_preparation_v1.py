"""D279 resume only unarmed Q16c metadata; keep the admitted packet immutable.

The original packet2 constructor/signature code executes in private scopes.
Identical partial metadata may be reused; the failed archive descriptor is
preserved and its corrected successor receives a new name. No measurement,
qualification, old raw validation or archive-program initialization occurs.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import types

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28')
PACKET=E/'q16c-configuration-2'
BASE_SHA='4ea6055c4c005a0bc277be7738bbf6b784c10234507bf3e7f4c6596b34ea3c34'
REUSED=frozenset(('q16a-context.json','q16b-context.json','q16a-compatibility.json','q16b-compatibility.json','historical-inputs.json'))
_BASE=None


def require(ok,message):
    if not ok:raise ValueError('Q16c metadata continuation: '+message)


def load_base(c):
    global _BASE
    b=c['files']['preparation_base'];p=Path(b['path'])
    require(p==PACKET/'stage17_q16c_prepare_v2.py' and b['sha256']==BASE_SHA,'unchanged admitted constructor required')
    require(all(not q.is_symlink() for q in (p,*p.parents)),'nonsymlink constructor')
    raw=p.read_bytes();require(len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==BASE_SHA,'constructor bytes changed')
    if _BASE is None:
        _BASE=types.ModuleType('q16c_retained_preparation_base');_BASE.__file__=str(p)
        exec(compile(raw,str(p),'exec'),_BASE.__dict__)
    return _BASE


def loader_for(c):return load_base(c).loader_for(c)


def __getattr__(name):
    if _BASE is None:raise AttributeError(name)
    return getattr(_BASE,name)


def relocate_sources(original,packet,read_binding):
    """Alias the same seven verified bytes; never change a profile or library."""
    packet=Path(packet);fixed=copy.deepcopy(original)
    expected={'stage17_archive_'+n for n in ('canonical_fast_v1','inventory_image_v1','inventory_native_v1',
        'inverse_image_v1','inverse_native_v1','metadata_fast_v1','metadata_fast_v2')}
    require(set(original['sources'])==expected,'exact seven archive helpers')
    for name,b in fixed['sources'].items():
        read_binding(b)
        target=dict(b,path=str(packet/(name+'.py')));read_binding(target)
        b['path']=target['path']
    return fixed


def publisher(base,c):
    """Continue deterministic partial output, without replacing any old bytes."""
    packet=Path(c['packet_root']);require(packet==PACKET,'admitted packet2 namespace')
    def save(path,value):
        p=Path(path)
        if p==packet/'archive-overlay.json':
            return base.save(packet/'archive-overlay-continuation-1.json',value)
        if p.parent==packet and p.name in REUSED:
            previous=c['retained_metadata'][p.name]
            require(previous['path']==str(p),'retained output namespace')
            raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            require(base.read(previous)==raw,'retained metadata differs: '+p.name)
            return previous
        return base.save(p,value)
    return save


def construct(c):
    base=load_base(c)
    require(c['output_root']==str(E/'q16c-authoring-2') and c['packet_root']==str(PACKET),'fresh authoring namespace')
    require(set(c['retained_metadata'])==REUSED,'complete exact retained metadata set')
    stopped=base.document(c['files']['prior_study_complete'])
    restored=base.document(c['files']['prior_partition_restoration'])
    require(stopped['success'] is False and stopped['errors']==["RuntimeError('Q16c study: construct failed')"]
        and len(stopped['phases'])==1 and stopped['phases'][0]['role']=='construct'
        and stopped['phases'][0]['exit_code']==1 and stopped['phases'][0]['leader_reaped'] is True,
        'exact stopped pre-arm incident')
    require(restored['verified'] is True and restored['errors']==[],'prior restoration incomplete')
    old=base.document(c['files']['original_archive_preparation']);new=base.document(c['files']['archive_preparation'])
    require(new==relocate_sources(old,PACKET,base.read),'only verified archive paths may change')
    scope=dict(vars(base),save=publisher(base,c))
    function=types.FunctionType(base.construct.__code__,scope,base.construct.__name__,base.construct.__defaults__,base.construct.__closure__)
    function.__kwdefaults__=base.construct.__kwdefaults__
    return function(c)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('construct','sign'))
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True);a=p.parse_args()
    raw=a.configuration.read_bytes();require(hashlib.sha256(raw).hexdigest()==a.configuration_sha256,'configuration changed')
    c=json.loads(raw);base=load_base(c)
    base.require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
    require(c['files']['preparation_operator']==base.binding(Path(__file__).resolve()),'bound continuation operator')
    require(c['execution_authority'] is False and c['phase18_authority'] is False,'metadata grants no authority')
    for key,b in c['files'].items():
        if key!='archive':base.read(b)
    for b in c['retained_metadata'].values():base.read(b)
    print(json.dumps(construct(c) if a.mode=='construct' else base.sign(c)),flush=True)


if __name__=='__main__':main()
