"""Read-only deployment admission before Stage17 qualification or collection.

Reproducible archives may legitimately store UID0. Their extracted deployment
must satisfy the actual execution owner's immutable worker-snapshot contract.
This checker changes no permissions and executes no packaged code.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

MAX_ENTRIES=8192
MAX_FILE_BYTES=128*1024**2
MAX_TOTAL_BYTES=2*1024**3


def require(ok,message):
    if not ok:raise ValueError('Stage17 execution owner: '+message)


def stamp(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def owned(path,uid,*,directory=False,executable=False):
    s=path.lstat()
    require((stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
        and s.st_uid==uid,'not an execution-owner '+('directory: ' if directory else 'regular file: ')+str(path))
    require(stat.S_IMODE(s.st_mode)&0o022==0,'group/world writable deployment member: '+str(path))
    if executable:require(stat.S_IMODE(s.st_mode)&0o111!=0,'worker is not executable')
    return s


def hashed(path,uid,deadline):
    before=owned(path,uid);require(0<=before.st_size<=MAX_FILE_BYTES,'finite deployment member size')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK);digest=hashlib.sha256();count=0
    with os.fdopen(fd,'rb') as stream:
        require(stamp(before)==stamp(os.fstat(stream.fileno())),'deployment file replaced before read')
        while block:=stream.read(1024**2):
            require(time.monotonic_ns()<deadline,'deployment audit deadline')
            count+=len(block);require(count<=before.st_size,'deployment member grew');digest.update(block)
        require(count==before.st_size and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.lstat()),
            'deployment file changed during read')
    return dict(size_bytes=count,sha256=digest.hexdigest())


def check(root,*,uid,inventory_sha256,source_revision,worker_sha256,timeout_seconds=120):
    require(type(uid) is int and uid==os.geteuid(),'run admission as the actual execution owner')
    require(type(timeout_seconds) is int and 0<timeout_seconds<=120,'finite read-only audit timeout')
    for value,width in ((inventory_sha256,64),(source_revision,40),(worker_sha256,64)):
        require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(width)+'}',value),'explicit qualified byte identity')
    root=Path(root);require(root.is_absolute() and root.resolve(strict=True)==root
        and not any(p.is_symlink() for p in (root,*root.parents)),'canonical nonsymlink deployment root')
    started=time.monotonic_ns();deadline=started+timeout_seconds*10**9;owned(root,uid,directory=True)
    inventory_path=root/'BUNDLE_INVENTORY.json';physical=hashed(inventory_path,uid,deadline)
    require(physical['sha256']==inventory_sha256,'qualified inventory hash differs')
    raw=inventory_path.read_bytes();require(hashlib.sha256(raw).hexdigest()==inventory_sha256,'inventory changed after admission')
    def pairs(rows):
        d={}
        for key,value in rows:require(key not in d,'duplicate inventory key');d[key]=value
        return d
    inventory=json.loads(raw,object_pairs_hook=pairs)
    require(inventory['source_revision']==source_revision,'actual qualified source differs')
    rows=inventory['files'];require(type(rows) is list and 0<len(rows)<=MAX_ENTRIES-2,'finite complete inventory')
    expected={}
    for row in rows:
        require(type(row) is dict and set(row)=={'path','size_bytes','sha256'},'closed inventory member binding')
        name=row['path'];p=Path(name)
        require(type(name) is str and not p.is_absolute() and '..' not in p.parts and str(p)==name
            and name not in ('','.','BUNDLE_INVENTORY.json','SHA256SUMS') and name not in expected,'unique canonical inventory path')
        require(type(row['size_bytes']) is int and 0<=row['size_bytes']<=MAX_FILE_BYTES
            and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'finite inventory member values')
        expected[name]={k:row[k] for k in ('size_bytes','sha256')}
    files={};directories=0;total=0
    for directory,dirs,names in os.walk(root,followlinks=False):
        require(time.monotonic_ns()<deadline,'deployment traversal deadline')
        owned(Path(directory),uid,directory=True);directories+=1
        for name in dirs:owned(Path(directory)/name,uid,directory=True)
        require(len(files)+directories+len(names)+len(dirs)<=MAX_ENTRIES,'finite closed deployment tree')
        for name in names:
            p=Path(directory)/name;relative=str(p.relative_to(root))
            require(relative in expected or relative in ('BUNDLE_INVENTORY.json','SHA256SUMS'),'unlisted deployment file: '+relative)
            observed=hashed(p,uid,deadline);files[relative]=observed;total+=observed['size_bytes']
            require(total<=MAX_TOTAL_BYTES,'aggregate deployment byte bound')
            if relative in expected:require(observed==expected[relative],'qualified deployment bytes differ: '+relative)
    require(set(files)==set(expected)|{'BUNDLE_INVENTORY.json','SHA256SUMS'},'missing qualified deployment file')
    require(files['BUNDLE_INVENTORY.json']['sha256']==inventory_sha256,'inventory changed during complete audit')
    worker='release/bin/cpu_prefetch_runner';require(worker in expected and expected[worker]['sha256']==worker_sha256,'actual qualified worker')
    owned(root/worker,uid,executable=True)
    return dict(schema_version='cpu-prefetch-stage17-execution-owner-admission/1',status='PASS',bundle_root=str(root),
        requested_execution_uid=uid,verified_execution_uid=os.geteuid(),source_revision=source_revision,
        inventory_sha256=inventory_sha256,worker=files[worker],inventory_entries=len(rows),checked_files=len(files),
        checked_directories=directories,checked_bytes=total,elapsed_ns=time.monotonic_ns()-started,
        worker_executed=False,permissions_changed=False,execution_authority=False,phase18_authority=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle-root',type=Path,required=True)
    p.add_argument('--uid',type=int,required=True);p.add_argument('--inventory-sha256',required=True)
    p.add_argument('--source-revision',required=True);p.add_argument('--worker-sha256',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=check(a.bundle_root,uid=a.uid,inventory_sha256=a.inventory_sha256,source_revision=a.source_revision,worker_sha256=a.worker_sha256)
    raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    with a.output.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
