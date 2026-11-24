"""Install exact D282 software packets; no qualification/window/native action."""
import hashlib,json,os,subprocess,sys,tarfile
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29')
assert os.geteuid()==0 and Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def save(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,separators=(',',':'));f.flush();os.fsync(f.fileno())
 os.chown(p,1000,1000)
for name,dest,digest in [('collection-packet-3.tar','q16c-configuration-1','46a84da30fc738b22bde3a314813956c003a692ab7ac6f50d42b253c8f75cb81'),('qualification-packet-2.tar','operator-preparation-v29','0d88977b24c355ea3f4c1f7dd3a11e08e4cfcf9bb98e0d91c0370e80e94d0711')]:
 src=E/name;assert sha(src)==digest;dst=E/dest;dst.mkdir(mode=0o700);os.chown(dst,1000,1000)
 with tarfile.open(src) as t:
  for m in t.getmembers():
   assert m.isfile() and Path(m.name).name==m.name
   p=dst/m.name
   with p.open('xb') as f:f.write(t.extractfile(m).read())
   os.chown(p,1000,1000);os.chmod(p,0o444)
Q=E/'operator-preparation-v29';P=E/'q16c-configuration-1';sys.path.insert(0,str(Q))
from install_v29 import PUBLIC,verify_packet,copy_exclusive,CORE_DIRECTORY
rows=[];old=E.parent/'local-authoring-cpuprefetchv5-21/operator-preparation-v21'
for name,dest,digest in PUBLIC:
 assert sha(old/name)==digest;copy_exclusive(old/name,Q/dest);rows.append(dict(original_path=str(old/name),path=str(Q/dest),size_bytes=(Q/dest).stat().st_size,sha256=digest))
save(Q/'original-public-inputs-reuse.json',dict(original_records_unchanged=True,new_search_claimed=False,files=rows))
verify_packet(Q,sha(Q/'preparation-inventory.json'),installed=True)
CORE_DIRECTORY.mkdir(mode=0o755);copy_exclusive(Q/'isolation_core.py',CORE_DIRECTORY/'isolation_core.py',uid=0)
assert not (E/'admission-root').exists()
with (E/'initialize-admission-root-1.log').open('xb') as log:
 subprocess.run(['/usr/bin/python3','-B',str(Q/'initialize-v29.py')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
print('D282_PREPARATION_INSTALLED_NO_WINDOW_OR_EXPERIMENT',sha(Q/'preparation-inventory.json'),flush=True)
