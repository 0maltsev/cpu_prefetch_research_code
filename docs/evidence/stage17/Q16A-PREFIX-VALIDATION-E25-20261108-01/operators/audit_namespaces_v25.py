#!/usr/bin/env python3
"""Read-only scoped public metadata audit, using the R3 root allowlists.

D240 numeric seeds are checked by the production parent contract, not collision-scanned.
No SSH, registration, raw payload reads, deletion or authority.
Report goes to stdout; only the caller chooses a new report file.
"""
import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import sys
import time

MAX_FILE=64*1024**2
MAX_TOTAL=2*1024**3
MAX_FILES=20000

def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key')
        result[key]=value
    return result
def parse(text):
    return json.loads(text,object_pairs_hook=unique,
        parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON '+s)))

class Matcher:
    def __init__(self,document):
        rows=document['phase_identities']
        if len(rows)!=1062:raise ValueError('exact531 warmup/measurement identity pairs required')
        if any(type(r) is not dict or set(r)!={'run_id','seed_id','seed_hex','namespace_id'} for r in rows):raise ValueError('exactphase identity fields required')
        for key in ('run_id','seed_id'):
            if len({r[key] for r in rows})!=1062:raise ValueError('fresh unique phase '+key+' required')
        self.wanted={r[k] for r in rows for k in ('run_id','seed_id','namespace_id')}
        self.namespaces=sorted({r['namespace_id'] for r in rows})
        if len(self.namespaces)!=2:raise ValueError('exacttwo phase namespaces required')
        prefixes=set()
        for r in rows:
            if not re.fullmatch(r'[A-Za-z0-9]{1,8}[WM][0-9]{8}',r['run_id']):raise ValueError('unsupported prospective run ID shape')
            prefixes.add(r['run_id'][:-8])
            if not re.fullmatch(re.escape(r['namespace_id'])+r'-SEED-[0-9]{4}',r['seed_id']):raise ValueError('unexpected seed ID shape')
            if not re.fullmatch('[0-9a-f]{64}',r['seed_hex']):raise ValueError('seed must be canonicalhex')
        # Zero-width lookahead finds embedded identities; numeric seeds are deliberately absent.
        alternatives=[re.escape(p)+r'[0-9]{8}' for p in sorted(prefixes)]
        alternatives += [re.escape(ns)+r'(?:-SEED-[0-9]{4})?' for ns in self.namespaces]
        self.pattern=re.compile('(?=('+'|'.join(alternatives)+'))')
    def text(self,value):
        found=set()
        for match in self.pattern.finditer(value):
            token=match.group(1)
            if token in self.wanted:found.add(token)
            for ns in self.namespaces:
                if token.startswith(ns):found.add(ns)
        return found
    def json(self,raw,lines=False):
        text=raw.decode('utf-8',errors='strict');found=self.text(text)
        records=[s for s in text.splitlines() if s.strip()] if lines else [text]
        if not records:raise ValueError('empty JSONL')
        visited=0
        for record in records:
            pending=[parse(record)]
            while pending:
                value=pending.pop();visited+=1
                if visited>10_000_000:raise ValueError('JSON node bound exceeded')
                if isinstance(value,str):found.update(self.text(value))
                elif isinstance(value,dict):pending.extend(value.keys());pending.extend(value.values())
                elif isinstance(value,list):pending.extend(value)
        return sorted(found)

def selected_roots(mode,base):
    base=base.absolute()
    if any(p.is_symlink() for p in (base,*base.parents)):raise ValueError('scope ancestor symlink')
    if mode=='local':
        if not (base/'AGENTS.md').is_file():raise ValueError('explicit repository root required')
        return [base/'docs/evidence',base/'build/stage17-step2-prep',base/'build/stage17-step3-prep']
    if base.name!='stage17-owner-evidence' or not base.is_dir():raise ValueError('explicit existing stand owner-evidence root required')
    roots=[]
    # Exact previous R3 selection: immediate context JSON, named public metadata
    # subtrees and discovery preparation. Never scan the whole context/root.
    for context in sorted(base.glob('local-authoring-*')):
        if context.is_symlink():raise ValueError('context symlink in scope')
        if not context.is_dir():continue
        roots.extend(sorted(context.glob('*.json')))
        for name in ('admission-root/evidence','journal','actions','authorizations','manifests','records','receipts'):
            path=context/name
            if path.exists() or path.is_symlink():roots.append(path)
        roots.extend(sorted(context.glob('discovery-preparation*')))
    return roots

def audit(roots,matcher,own,deadline):
    checked=[];matches=[];errors=[];excluded=[];seen=set();total=0;visited=0
    own=own.absolute()
    def visit(path):
        nonlocal total,visited
        path=path.absolute()
        if path in seen:return
        seen.add(path);visited+=1
        if time.monotonic()>=deadline:raise TimeoutError('audit wall deadline')
        if visited>100000:raise ValueError('metadata traversal entry bound')
        if path==own or own in path.parents:
            excluded.append(dict(path=str(path),reason='OWN_PROSPECTIVE_PREPARATION'));return
        try:
            mode=path.lstat().st_mode
            if stat.S_ISLNK(mode):raise ValueError('symlink in selected history; not followed')
            if stat.S_ISDIR(mode):
                with os.scandir(path) as scan:children=sorted((Path(e.path) for e in scan),key=str)
                for child in children:visit(child)
                return
            if path.suffix.lower() not in ('.json','.jsonl'):return
            if not stat.S_ISREG(mode):raise ValueError('nonregular metadata file')
            if len(checked)>=MAX_FILES:raise ValueError('metadata file count bound')
            with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
                before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):raise ValueError('opened metadata is not regular')
                if before.st_size>MAX_FILE or total+before.st_size>MAX_TOTAL:raise ValueError('explicit metadata byte bound')
                raw=stream.read(MAX_FILE+1);after=os.fstat(stream.fileno())
            stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if len(raw)!=before.st_size or stamp(before)!=stamp(after) or stamp(after)!=stamp(path.stat(follow_symlinks=False)):
                raise ValueError('metadata changed during read')
            total+=len(raw)
            found=matcher.json(raw,path.suffix.lower()=='.jsonl')
            item=dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            checked.append(item)
            if found:matches.append(dict(**item,matched=found))
        except (OSError,ValueError,RecursionError) as error:errors.append(dict(path=str(path),reason=str(error)))
    try:
        for root in roots:visit(root)
    except (TimeoutError,ValueError) as error:errors.append(dict(path='<scope>',reason=str(error)))
    if not checked:errors.append(dict(path='<scope>',reason='no public metadata checked'))
    return dict(status='PASS_SCOPED_HISTORY_AUDIT' if not errors and not matches else 'FAIL',
        observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        scope='R3 allowlisted operational/public JSON and JSONL only; no raw payload or whole-disk proof',
        roots=[str(p) for p in roots],needles=sorted(matcher.wanted),checked_files=len(checked),checked_bytes=total,
        checked_inventory=checked,checked_inventory_sha256=hashlib.sha256(
            json.dumps(checked,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        matches=matches,errors=errors,excluded=excluded,execution_authority=False,
        maximum_file_bytes=MAX_FILE,maximum_total_bytes=MAX_TOTAL,maximum_files=MAX_FILES)

def validate_prospective_directory(mode,base,own):
    own=own.absolute();base=base.absolute()
    parents=({base/'build/stage17-step5-prep'} if mode=='local' else
             {base/'local-authoring-cpuprefetchv5-25'})
    if own.name!='formal-q16a-continuation-authoring-1' or own.parent not in parents:
        raise ValueError('only the exact E25 continuation prospective directory may be excluded')

def bound_input(path,expected_sha,maximum):
    path=path.absolute()
    if path.resolve(strict=True)!=path:raise ValueError('bound input symlink')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>maximum:raise ValueError('bound input size/type')
        raw=stream.read(maximum+1);after=os.fstat(stream.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    if len(raw)!=before.st_size or stamp(before)!=stamp(after) or stamp(after)!=stamp(path.lstat()):raise ValueError('bound input changed')
    if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('exact input SHA256 binding')
    return raw


def validate_prospective(identities,plan_raw,parent_raw,contract):
    """The production D240 contract proves original numeric seeds and science."""
    plan=parse(plan_raw)
    contract.validate_parent(plan,parent_raw)
    if set(identities)!={'schema_version','plan_sha256','stand_id','phase_identities','schedule_namespaces','execution_authority'}:raise ValueError('namespace registration fields')
    expected=[item['capture'][phase] for item in plan['captures'] for phase in ('warmup','measurement')]
    if (identities['schema_version']!='cpu-prefetch-stage17-formal-namespace-registration/1'
            or identities['plan_sha256']!=hashlib.sha256(plan_raw).hexdigest()
            or identities['stand_id']!=plan['stand_id'] or identities['phase_identities']!=expected
            or identities['schedule_namespaces']!=[] or identities['execution_authority'] is not False):
        raise ValueError('namespace registration differs from exact continuation plan')
    if plan_raw!=contract.ring.canonicalize(plan).encode('utf-8'):
        raise ValueError('canonical no-LF plan bytes required')
    return dict(status='PASS',original_numeric_seeds_preserved=True,captures=531,phase_identities=1062,
        collision_fields=['run_id','seed_id','namespace_id'],numeric_seeds_collision_scanned=False,
        execution_authority=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository-root',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--plan-sha256',required=True)
    p.add_argument('--parent-plan',type=Path,required=True)
    p.add_argument('--parent-plan-sha256',required=True)
    p.add_argument('--mode',choices=('local','stand'),required=True)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--identities',type=Path,required=True)
    p.add_argument('--identities-sha256',required=True)
    p.add_argument('--prospective-directory',type=Path,required=True)
    p.add_argument('--wall-seconds',type=int,required=True)
    args=p.parse_args()
    if not 1<=args.wall_seconds<=300:raise ValueError('wall bound1..300seconds')
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    def timeout(_signal,_frame):raise TimeoutError('audit wall deadline')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,args.wall_seconds)
    try:
        raw=bound_input(args.identities,args.identities_sha256,2*1024**2)
        plan_raw=bound_input(args.plan,args.plan_sha256,32*1024**2)
        parent_raw=bound_input(args.parent_plan,args.parent_plan_sha256,32*1024**2)
        root=args.repository_root.resolve(strict=True)
        sys.path.insert(0,str(root/'tools'))
        contract=importlib.import_module('stage17_formal_ring_continuation_v1')
        if Path(contract.__file__).resolve()!=root/'tools/stage17_formal_ring_continuation_v1.py':raise ValueError('contract outside supplied repository')
        proof=validate_prospective(parse(raw),plan_raw,parent_raw,contract)
        matcher=Matcher(parse(raw));roots=selected_roots(args.mode,args.base)
        validate_prospective_directory(args.mode,args.base,args.prospective_directory)
        report=audit(roots,matcher,args.prospective_directory,time.monotonic()+args.wall_seconds)
        report['identities_binding']=dict(path=str(args.identities),size_bytes=len(raw),sha256=args.identities_sha256)
        report['parent_contract']=proof
        report['plan_binding']=dict(path=str(args.plan),size_bytes=len(plan_raw),sha256=args.plan_sha256)
        report['parent_plan_binding']=dict(path=str(args.parent_plan),size_bytes=len(parent_raw),sha256=args.parent_plan_sha256)
        report['contract_binding']=dict(path=str(Path(contract.__file__).resolve()),sha256=hashlib.sha256(Path(contract.__file__).read_bytes()).hexdigest())
        report['helper_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        print(json.dumps(report,sort_keys=True,indent=2))
        return 0 if report['status']=='PASS_SCOPED_HISTORY_AUDIT' else 1
    finally:signal.setitimer(signal.ITIMER_REAL,0)

if __name__=='__main__':raise SystemExit(main())
