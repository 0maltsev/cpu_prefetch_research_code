"""Bounded read-only storage prototype, not an approved archive implementation."""
from pathlib import Path
from array import array
import datetime,hashlib,json,os,subprocess,sys,time,struct
root=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-20/discovery-output-r3-1')
os.nice(19);allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{max(allowed)})
MASK=(1<<64)-1

def encode(raw,words):
 values=array('Q');values.frombytes(raw)
 if sys.byteorder!='little':values.byteswap()
 count=len(values)//words;output=bytearray()
 for column in range(words):
  delta=array('Q');previous=0
  for index in range(column,len(values),words):
   value=values[index];delta.append((value-previous)&MASK);previous=value
  if sys.byteorder!='little':delta.byteswap()
  output.extend(delta.tobytes())
 return bytes(output)

def decode(raw,words):
 values=array('Q');values.frombytes(raw)
 if sys.byteorder!='little':values.byteswap()
 count=len(values)//words;output=array('Q',[0])*len(values)
 for column in range(words):
  previous=0
  for row in range(count):
   previous=(previous+values[column*count+row])&MASK;output[row*words+column]=previous
 if sys.byteorder!='little':output.byteswap()
 return output.tobytes()

print(json.dumps({'event':'start','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'READ_ONLY_REVERSIBLE_STORAGE_PROTOTYPE_NOT_ARCHIVE_AUTHORITY','transform':'BLOCK-ROW-U64LE-MODDELTA-COLUMNS-PROTOTYPE-v1','rows_per_block':8192,'zstd_version':subprocess.check_output(['/usr/bin/zstd','--version'],text=True).strip()}),flush=True)
totals={3:[0,0],9:[0,0]}
for ordinal in range(0,36,3):
 for role,body in [('producer',120),('consumer',80)]:
  path=root/f'discovery-c{ordinal:02d}-warmup-{role}.bin';before=path.stat()
  with path.open('rb') as stream:
   identity_length=struct.unpack('<I',stream.read(4))[0]
   if not 0<identity_length<=256:raise RuntimeError('invalid identity size')
   row_bytes=((4+identity_length+7)//8)*8+body
   if before.st_size%row_bytes:raise RuntimeError('nonintegral rows')
   size=min(before.st_size//row_bytes,8192)*row_bytes
   for offset in (0,before.st_size-size):
    stream.seek(offset);original=stream.read(size);transformed=encode(original,row_bytes//8)
    if decode(transformed,row_bytes//8)!=original:raise RuntimeError('transform roundtrip')
    for level in (3,9):
     started=time.monotonic()
     packed=subprocess.run(['/usr/bin/zstd',f'-{level}','-T1','--no-progress','-q','-c'],input=transformed,capture_output=True,check=True,timeout=45).stdout
     unpacked=subprocess.run(['/usr/bin/zstd','-d','-q','-c'],input=packed,capture_output=True,check=True,timeout=30).stdout
     if decode(unpacked,row_bytes//8)!=original:raise RuntimeError('archive roundtrip')
     totals[level][0]+=len(original);totals[level][1]+=len(packed)
     print(json.dumps({'event':'sample','file':path.name,'file_bytes':before.st_size,'offset':offset,'row_bytes':row_bytes,'sample_bytes':len(original),'sample_sha256':hashlib.sha256(original).hexdigest(),'level':level,'compressed_bytes':len(packed),'compressed_sha256':hashlib.sha256(packed).hexdigest(),'roundtrip_verified':True,'elapsed_seconds':round(time.monotonic()-started,4)}),flush=True)
  after=path.stat();fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  if fields(before)!=fields(after):raise RuntimeError('source changed')
print(json.dumps({'event':'complete','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'primary_file_count':24,'sample_blocks':48,'roundtrip_cases':96,'totals':totals,'original_files_changed':False,'execution_authority':False}),flush=True)
