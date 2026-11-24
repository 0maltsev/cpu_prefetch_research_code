"""Read-only bounded compression samples; no experiment or custody change."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,time
root=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-20/discovery-output-r3-1')
os.nice(19)
allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{max(allowed)})
print(json.dumps({'event':'start','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'READ_ONLY_STORAGE_PLANNING_SAMPLES_NOT_FORMAL_RATE_OR_COMPLETE_ARCHIVE_PROOF','cpu':max(allowed),'sample_segment_bytes':4*1024**2,'levels':[3,9],'version':subprocess.check_output(['/usr/bin/zstd','--version'],text=True).strip()}),flush=True)
totals={3:[0,0],9:[0,0]}
for ordinal in range(0,36,3):
 for suffix in ['control.json','warmup-producer.bin','warmup-consumer.bin','warmup-demand.bin']:
  path=root/f'discovery-c{ordinal:02d}-{suffix}'
  before=path.stat();n=min(4*1024**2,before.st_size//2)
  with path.open('rb') as stream:
   first=stream.read(n);stream.seek(before.st_size-n);last=stream.read(n)
  sample=first+last;source_digest=hashlib.sha256(sample).hexdigest()
  for level in (3,9):
   started=time.monotonic()
   packed=subprocess.run(['/usr/bin/zstd',f'-{level}','-T1','--no-progress','-q','-c'],input=sample,capture_output=True,check=True,timeout=45).stdout
   unpacked=subprocess.run(['/usr/bin/zstd','-d','-q','-c'],input=packed,capture_output=True,check=True,timeout=30).stdout
   if unpacked!=sample:raise RuntimeError('roundtrip mismatch')
   totals[level][0]+=len(sample);totals[level][1]+=len(packed)
   print(json.dumps({'event':'sample','file':path.name,'file_bytes':before.st_size,'offsets':[0,before.st_size-n],'segment_bytes':n,'sample_bytes':len(sample),'sample_sha256':source_digest,'level':level,'compressed_bytes':len(packed),'compressed_sha256':hashlib.sha256(packed).hexdigest(),'roundtrip_verified':True,'elapsed_seconds':round(time.monotonic()-started,4)}),flush=True)
  after=path.stat()
  fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  if fields(before)!=fields(after):raise RuntimeError('source identity changed')
print(json.dumps({'event':'complete','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sample_file_count':48,'roundtrip_cases':96,'totals':totals,'original_files_changed':False,'execution_authority':False}),flush=True)
