from pathlib import Path
import os,stat,json,time,datetime,hashlib
root=Path('/home/omaltsev/stage17-owner-evidence')
started=time.monotonic_ns();groups={};count=0;seen=set();links=[];h=hashlib.sha256()
for current,dirs,files in os.walk(root,followlinks=False):
 dirs.sort();files.sort()
 for name in [*dirs,*files]:
  path=Path(current)/name;st=path.stat(follow_symlinks=False);relative=path.relative_to(root)
  count+=1
  if count>500000:raise ValueError('bounded inventory exceeded')
  h.update(json.dumps([str(relative),st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_blocks,st.st_mtime_ns,st.st_ctime_ns],separators=(',',':')).encode()+b'\n')
  group='/'.join(relative.parts[:2]);row=groups.setdefault(group,dict(regular_files=0,logical_bytes=0,allocated_bytes=0,charged_bytes=0,directories=0,symlinks=0,largest_regular_files=[]))
  if stat.S_ISDIR(st.st_mode):row['directories']+=1;continue
  if stat.S_ISLNK(st.st_mode):row['symlinks']+=1;links.append(str(relative));continue
  if not stat.S_ISREG(st.st_mode):raise ValueError('nonregular evidence object '+str(relative))
  identity=(st.st_dev,st.st_ino)
  if identity in seen:continue
  seen.add(identity);row['regular_files']+=1;row['logical_bytes']+=st.st_size;row['allocated_bytes']+=512*st.st_blocks;row['charged_bytes']+=max(st.st_size,512*st.st_blocks)
  largest=row['largest_regular_files'];largest.append(dict(relative_path=str(relative),size_bytes=st.st_size));largest.sort(key=lambda r:r['size_bytes'],reverse=True);del largest[3:]
fs=os.statvfs(root)
print(json.dumps(dict(schema_version='cpu-prefetch-stage17-readonly-evidence-extent-survey/1',root=str(root),utc=datetime.datetime.now(datetime.UTC).isoformat(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),elapsed_ns=time.monotonic_ns()-started,objects_scanned=count,unique_regular_files=len(seen),metadata_inventory_sha256=h.hexdigest(),groups=groups,symlinks=links,free_bytes=fs.f_bavail*fs.f_frsize,free_inodes=fs.f_favail,payload_bytes_read=0,classification_established=False,execution_authority=False),sort_keys=True,indent=2))
