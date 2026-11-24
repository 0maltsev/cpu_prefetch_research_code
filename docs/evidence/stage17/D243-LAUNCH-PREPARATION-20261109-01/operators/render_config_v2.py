"""Build-only operator input authoring. Reads exact files; never launches/registers."""

import sys
from pathlib import Path
sys.path.insert(0, '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25/d242-admin-1')
import stage17_state_journal_v53 as d242
d242.activate()
import argparse
import hashlib
import json
import os
from pathlib import Path
import formal_launch_v2 as launcher


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root','evidence-root','bundle-root','program-root','launch-root','archive','sidecar','python','setpriv','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('gid','controller-cpu','supervisor-cpu'):
        p.add_argument('--'+name,type=int,required=True)
    p.add_argument('--input-file',nargs=2,action='append',required=True,metavar=('ROLE','ABSOLUTE_PATH'))
    a=p.parse_args();files={}
    for role,path in a.input_file:
        launcher.require(role in launcher.FILES and role not in files,'unknown/duplicate input role')
        files[role]=launcher.bound(Path(path))
    launcher.require(set(files)==set(launcher.FILES),'all bound inputs required')
    c={k:str(getattr(a,k)) for k in ('repository_root','evidence_root','bundle_root','program_root','launch_root','archive','sidecar','python','setpriv')}
    for path in c.values():launcher.require(Path(path).is_absolute(),'absolute path required')
    launcher.require(not a.launch_root.exists(),'launch root already used')
    launcher.require(a.program_root.is_dir(),'existing program root required; never initialize')
    c.update(schema_version='software-formal-q16a-launch/1',uid=1000,gid=a.gid,
             controller_cpu=a.controller_cpu,supervisor_cpu=a.supervisor_cpu,files=files,
             setpriv_binding=launcher.bound(a.setpriv),launcher_sha256=launcher.digest(launcher.bytes_at(Path(launcher.__file__).resolve())))
    raw=launcher.canonical(c)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(a.output.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    print(json.dumps(dict(path=str(a.output),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),execution_authority=False),sort_keys=True))

if __name__=='__main__':main()
