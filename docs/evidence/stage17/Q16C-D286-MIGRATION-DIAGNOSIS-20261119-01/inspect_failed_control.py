"""Stand-only diagnostic readback of failed capture86 control metadata."""
import collections,dataclasses,hashlib,json,os,sys,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');P=E/'q16c-configuration-1';D=Path(__file__).resolve().parent
sys.path.insert(0,str(E/'admission-root/tools'));sys.path.insert(0,str(P))
import stage17_formal_archive_runtime_v1 as runtime
import stage17_q16c_archive_scope_v1 as images
G=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1';F=G/'working/36c15f402c7f20240da6b36472b9d0c56bcade8c1024604d0b1bd3deaef19a44'
custody=json.loads((F/'formal-capture-86-archive-custody.json').read_bytes());row=next(r for r in custody['artifacts'] if r['logical']['file_name']=='q16c-c86-control.json')
b=row['released_record'];raw=(G/'ledger'/b['file_name']).read_bytes();assert len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'];record=json.loads(raw);payload=record['payload'];assert payload['archive_name']==row['archive_name'] and payload['physical']==row['physical']
prepared=json.loads((P/'archive-preparation.json').read_bytes());b=prepared['overlay_profile'];deadline=time.monotonic_ns()+120*10**9
profile=runtime.load_runtime_profile(Path(b['path']),expected=runtime.archive.PhysicalBinding(b['size_bytes'],b['sha256']),bundle_root=Path(b['path']).parents[2],runtime_root=Path('/'),max_profile_bytes=1048576,deadline_ns=deadline)
archive,_=images.selected_archive_modules(profile,deadline);decoder=archive.DecoderProfile(**dataclasses.asdict(profile.decoder));header=payload['header']
limits=archive.DecodeLimits(max_header_bytes=32768,max_frame_bytes=64*1024**2,max_decoded_block_bytes=64*1024**2,max_archive_bytes=row['physical']['size_bytes'],max_canonical_bytes=row['logical']['size_bytes'],max_blocks=4096,max_window_bytes=1<<decoder.window_log,deadline_ns=deadline)
out=D/'control.json'
with out.open('xb') as sink:
 verified=archive.verify_archive(G/'archives'/row['archive_name'],expected_header=header,role=archive.RoleProfile(**payload['role']),physical=archive.PhysicalBinding(**row['physical']),profile=decoder,limits=limits,sink=sink)
raw=out.read_bytes();assert len(raw)==row['logical']['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['logical']['sha256'];data=json.loads(raw)
def shape(x,depth=0):
 if isinstance(x,dict):return {k:shape(v,depth+1) for k,v in x.items()} if depth<2 else dict(keys=list(x))
 if isinstance(x,list):return dict(length=len(x),first=shape(x[0],depth+1) if x else None)
 return x
report=dict(control_sha256=hashlib.sha256(raw).hexdigest(),control_size_bytes=len(raw),verified_archive=dataclasses.asdict(verified),shape=shape(data),experimental_actions=0)
(D/'control-shape.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps(report),flush=True)
