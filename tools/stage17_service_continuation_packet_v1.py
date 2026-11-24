"""D260 verified cold-source loader; never replaces qualified release modules.

An explicit caller-bound configuration/manifest is required. This loader grants
no phase authority: all journal, signature, source, prefix, hardware, namespace,
one-attempt and deadline gates still run in the returned operational CLI.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import stat
import sys
import types

EVIDENCE=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27')
BOOT='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
POLICY_SHA256='fae20402744131dcb24b1e814b5bf7199742b2e149c03f061fc67c1ec5eb8aa7'
POLICY_SIZE=211702
MODULES=('stage17_formal_service_continuation_v2','stage17_service_continuation_execution_v1',
 'stage17_q16a_service_continuation_handoff_v1','stage17_service_prefix_admission_v1',
 'stage17_public_namespace_audit_v1','stage17_service_continuation_namespace_v1',
 'stage17_service_continuation_administration_v1')
_LOADED={}
_ACTIVE=None


def require(ok,message):
    if not ok:raise ValueError('D260 packet: '+message)


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate JSON key');result[key]=value
        return result
    def invalid(value):raise ValueError('non-integer JSON '+value)
    return json.loads(raw,object_pairs_hook=pairs,parse_float=invalid,parse_constant=invalid)


def read(binding,maximum=32*1024**2):
    require(type(binding) is dict and set(binding)=={'path','size_bytes','sha256'},'exact file binding')
    p=pathlib.Path(binding['path']);size=binding['size_bytes'];digest=binding['sha256']
    require(p.is_absolute() and '..' not in p.parts and all(not q.is_symlink() for q in (p,*p.parents)),'canonical nonsymlink path')
    require(type(size) is int and 0<size<=maximum and type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest),'finite file size/hash')
    def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and before.st_size==size,'regular bound source')
        raw=stream.read(size+1)
        require(len(raw)==size and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(p.stat(follow_symlinks=False)),'source changed during read')
    require(hashlib.sha256(raw).hexdigest()==digest,'source SHA256 differs')
    return raw


def verify_packet(root,expected_sha):
    p=root/'manifest.json'
    raw=read(dict(path=str(p),size_bytes=p.stat().st_size,sha256=expected_sha),131072)
    document=strict_json(raw)
    require(set(document)=={'schema_version','administrative_source_revision','qualified_source_revision','qualified_worker_sha256','files','execution_authority','phase18_authority'},'manifest fields')
    require(document['schema_version']=='cpu-prefetch-stage17-d260-cold-packet/1','manifest schema')
    require(document['qualified_source_revision']=='07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8'
        and document['qualified_worker_sha256']=='5497678d637578843abaf5e9d708cecaebe3b26acd4f5b1da48c8fbf91835cb8','actual new native release')
    require(type(document['administrative_source_revision']) is str and re.fullmatch('[0-9a-f]{40}',document['administrative_source_revision']),'administrative source commit')
    require(document['execution_authority'] is False and document['phase18_authority'] is False,'manifest grants no authority')
    rows=document['files'];require(type(rows) is list and len(MODULES)<=len(rows)<=64,'bounded source closure')
    loaded={};total=0
    for row in rows:
        require(type(row) is dict and set(row)=={'name','size_bytes','sha256'},'manifest member fields')
        name=row['name'];require(type(name) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',name) and name not in loaded and name!='manifest.json','unique flat source member')
        data=read(dict(path=str(root/name),size_bytes=row['size_bytes'],sha256=row['sha256']),2*1024**2)
        total+=len(data);require(total<=16*1024**2,'aggregate source closure')
        loaded[name]=data
    require({n+'.py' for n in MODULES}|{'stage17_service_continuation_packet_v1.py'}<=set(loaded),'complete new module closure')
    code={p.name for p in root.iterdir() if p.is_dir() or p.suffix in ('.py','.pyc','.so')}
    require(code=={n for n in loaded if pathlib.Path(n).suffix in ('.py','.pyc','.so')},'unlisted executable/cache packet member')
    return document,loaded


def load_source(name,path,raw):
    require(name not in sys.modules,'unverified cached module '+name)
    module=types.ModuleType(name);module.__file__=str(path);module.__package__='';sys.modules[name]=module
    try:exec(compile(raw,str(path),'exec'),module.__dict__)
    except BaseException:
        if sys.modules.get(name) is module:del sys.modules[name]
        raise
    functions={k:(v,v.__code__) for k,v in vars(module).items() if isinstance(v,types.FunctionType)}
    imports={k:v for k,v in vars(module).items() if isinstance(v,types.ModuleType)}
    constants={k:v for k,v in vars(module).items() if re.fullmatch('[A-Z][A-Z0-9_]*',k)
               and isinstance(v,(str,int,bool,tuple,frozenset,pathlib.Path))}
    _LOADED[name]=(module,str(path),functions,imports,constants)
    return module


def check_loaded():
    for name,(module,path,functions,imports,constants) in _LOADED.items():
        require(sys.modules.get(name) is module and module.__file__==path,'loaded module replaced '+name)
        for key,(function,code) in functions.items():
            require(vars(module).get(key) is function and function.__code__ is code,'loaded function replaced '+name+'.'+key)
        for key,value in imports.items():require(vars(module).get(key) is value,'loaded import replaced '+name+'.'+key)
        for key,value in constants.items():require(vars(module).get(key)==value and type(vars(module).get(key)) is type(value),'loaded constant replaced '+name+'.'+key)


def verify_archive(binding):
    require(type(binding) is dict and set(binding)=={'path','size_bytes','sha256'},'archive binding fields')
    path=pathlib.Path(binding['path']);size=binding['size_bytes']
    require(type(size) is int and 0<size<=128*1024**2,'archive size bound')
    require(path.is_absolute() and all(not p.is_symlink() for p in (path,*path.parents)),'archive nonsymlink path')
    def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    digest=hashlib.sha256();count=0
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and before.st_size==size,'regular archive size')
        while chunk:=stream.read(1024**2):
            count+=len(chunk);require(count<=size,'archive grew');digest.update(chunk)
        require(count==size and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.stat(follow_symlinks=False)),'archive changed')
    require(digest.hexdigest()==binding['sha256'],'archive digest differs')


def activate(configuration_path,configuration_sha256):
    global _ACTIVE
    require(os.getuid()==os.geteuid()==1000,'actual evidence owner required')
    require(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'same approved boot required')
    raw=read(dict(path=str(configuration_path),size_bytes=configuration_path.stat().st_size,sha256=configuration_sha256),131072)
    cfg=strict_json(raw)
    require(set(cfg)=={'schema_version','repository_root','packet_root','policy','manifest','overlay','historical_inputs','archive','sidecar','window','boot_id','execution_authority'},'configuration fields')
    require(cfg['schema_version']=='cpu-prefetch-stage17-d260-cli-configuration/1' and cfg['execution_authority'] is False and cfg['boot_id']==BOOT,'configuration identity/authority')
    root=pathlib.Path(cfg['repository_root']);packet=pathlib.Path(cfg['packet_root'])
    require(root==EVIDENCE/'admission-root' and packet==EVIDENCE/'d260-configuration-1','incident-bound roots required')
    require(cfg['policy']==dict(path=str(root/'config/stage17/stage17-operational-evidence-admission-policy-v60.json'),size_bytes=POLICY_SIZE,sha256=POLICY_SHA256),'actual qualified policy60 required')
    policy=strict_json(read(cfg['policy']))
    for group in ('bindings','runtime_closure'):
        for bound in policy[group].values():read(dict(bound,path=str(root/bound['path'])))
    require(cfg['manifest']['path']==str(packet/'manifest.json'),'manifest namespace')
    manifest,members=verify_packet(packet,cfg['manifest']['sha256'])
    require(pathlib.Path(cfg['window']['path'])==EVIDENCE/'continuation-window-1.json','original absolute window')
    window=strict_json(read(cfg['window']))
    require(window['boot_id']==BOOT and window['deadline_monotonic_ns']-window['started_monotonic_ns']==86400*10**9,'unchanged24h window')
    verify_archive(cfg['archive'])
    for key in ('sidecar','overlay','historical_inputs'):read(cfg[key])
    key=(str(configuration_path),configuration_sha256,raw)
    if _ACTIVE is not None:
        require(key==_ACTIVE[0],'different packet reentry');check_loaded();return _ACTIVE[1],cfg
    for name,module in tuple(sys.modules.items()):
        if name.startswith('stage17_'):require(name==__name__ and vars(module) is globals(),'unverified project module cache')
    sys.path.insert(0,str(root/'tools'));sys.path.insert(1,str(packet))
    for name in MODULES:load_source(name,packet/(name+'.py'),members[name+'.py'])
    cli=sys.modules[MODULES[-1]].make_cli()
    cli.controller.configure_verified_descriptor(read(cfg['overlay']),packet)
    cli.controller.configure_historical_inputs(strict_json(read(cfg['historical_inputs'])),packet)
    cli.activate();check_loaded();_ACTIVE=(key,cli)
    return cli,cfg


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--configuration',type=pathlib.Path,required=True);parser.add_argument('--configuration-sha256',required=True)
    args,remaining=parser.parse_known_args();cli,_=activate(args.configuration,args.configuration_sha256)
    sys.argv=[__file__,*remaining];return cli.main()


if __name__=='__main__':raise SystemExit(main())
