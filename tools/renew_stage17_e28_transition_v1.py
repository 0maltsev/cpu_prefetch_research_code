"""D278 one-shot administrative renewal after actual Q15 recovery; no experiments.

Called only after the ordinary policy61 third edge rejects its expired EXT001
interval. The original failed transition and candidate are retained unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28')
P=E/'operator-preparation-v28-3'
ADMIN=E/'d278-admin-1'
NAME='cpu-prefetch-pilot-candidate-2.0.0-919c486-clean-2dda11ec716e'


def require(ok,message):
    if not ok:raise RuntimeError('D278 renewal operator: '+message)


def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def binding(p):
    require(p.is_absolute() and all(not q.is_symlink() for q in (p,*p.parents)),'nonsymlink regular source')
    raw=p.read_bytes();require(0<len(raw)<=32*1024**2 and p.is_file(),'bounded regular source')
    return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def save(p,value):
    with p.open('xb') as f:f.write(canonical(value));f.flush();os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return binding(p)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inventory-sha256',required=True);a=parser.parse_args()
    require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
    inv=P/'preparation-inventory.json';require(binding(inv)['sha256']==a.inventory_sha256,'reviewed packet inventory')
    inventory=json.loads(inv.read_bytes());rows={r['path']:r for r in inventory['files']}
    for name in ('renew_stage17_e28_transition_v1.py','stage17_state_journal_v58.py','d278-decision.md','d278-owner-acceptance.json'):
        b=binding(P/name);require({k:b[k] for k in ('size_bytes','sha256')}=={k:rows[name][k] for k in ('size_bytes','sha256')},'bound operator member '+name)
    require(Path(__file__).resolve()==P/'renew_stage17_e28_transition_v1.py','installed operator namespace')
    require(not ADMIN.exists(),'one fresh administrative packet; no retry')
    ADMIN.mkdir(mode=0o700)
    for source,target in [('stage17_state_journal_v58.py','stage17_state_journal_v58.py'),('d278-decision.md','decision.md'),('d278-owner-acceptance.json','owner-acceptance.json')]:
        with (ADMIN/target).open('xb') as f:f.write((P/source).read_bytes());f.flush();os.fsync(f.fileno())
    sys.path.insert(0,str(E/'admission-root/tools'))
    raw=(ADMIN/'stage17_state_journal_v58.py').read_bytes();name='stage17_state_journal_v58'
    require(name not in sys.modules,'unverified renewal module cache')
    renewal=types.ModuleType(name);renewal.__file__=str(ADMIN/(name+'.py'));sys.modules[name]=renewal
    exec(compile(raw,renewal.__file__,'exec'),renewal.__dict__)
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==renewal.BOOT,'actual approved boot')
    paths=dict(journal=E/renewal.BASE_NAME,failed_transition=E/'records/transition-003.json',
        failed_candidate=E/'journal/stage17-state-journal-000009.json.candidate',
        q15r_result=E/'stage17-q15-r-result-v4.json',q15w_result=E/'stage17-q15-w-result-v4.json',
        q15w_completion=E/'stage17-q15_w-completion-v4.json',clocks=E/'clock-qualification-v28-1/complete.json',
        session=E/'q15-owned-session-success-3.json',isolation_handoff=E/'q15-continuation-recovery-1/q15w-isolation-handoff.json')
    cb=save(ADMIN/'incident.json',dict(schema_version='cpu-prefetch-stage17-d278-transition-incident/1',
        source_revision=renewal.SOURCE,worker_sha256=renewal.WORKER,boot_id=renewal.BOOT,
        files={k:binding(p) for k,p in paths.items()},execution_authority=False,phase18_authority=False))
    renewal.configure_verified_incident(Path(cb['path']),cb['sha256']);renewal.incident()
    save(ADMIN/'manifest.json',dict(schema_version='cpu-prefetch-stage17-d278-admin-manifest/1',
        administrative_source_revision=inventory['administrative_source_revision'],qualified_source_revision=renewal.SOURCE,
        files=[dict(name=p.name,**{k:v for k,v in binding(p).items() if k!='path'}) for p in sorted(ADMIN.iterdir())],execution_authority=False))
    archive=E.parent/(NAME+'.tar.gz');sidecar=Path(str(archive)+'.sha256')
    auth=renewal.author(archive,sidecar)
    signed=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',auth['path']],
        stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    save(renewal.TRANSACTION/'signing-result.json',dict(exit_code=signed.returncode,stdout=signed.stdout.decode(errors='replace'),stderr=signed.stderr.decode(errors='replace')))
    require(signed.returncode==0,'actual owner signing failed')
    receipt=renewal.commit(archive,sidecar)
    result=dict(schema_version='cpu-prefetch-stage17-d278-completion/1',status='ADMINISTRATIVE_THIRD_EDGE_RENEWED',
        incident=cb,manifest=binding(ADMIN/'manifest.json'),receipt=receipt,execution_authority=False,phase18_authority=False)
    save(renewal.TRANSACTION/'complete.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
