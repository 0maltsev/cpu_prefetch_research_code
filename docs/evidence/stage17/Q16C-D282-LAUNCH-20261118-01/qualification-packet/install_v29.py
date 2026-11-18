"""Exclusive E29 admission-root/packet installation; no archive-program init."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path('/home/omaltsev/stage17-owner-evidence')
E=ROOT/'local-authoring-cpuprefetchv5-29'
CORE_DIRECTORY=Path('/run/cpu-prefetch-recovery-v29-qualified-1')
CORE_SHA='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
PUBLIC=(('d124-combined-search-v21.json','d124-combined-search-v26.json','d32b53488651f8b69b72ca0943124dca57f130f3b474ed908997688f334b478e'),
        ('known-hosts-exact-localhost','known-hosts-exact-localhost','e2a055ae082bb6c40dbac4e61d9253bbd45cf8451cbdf66aff62aa68bc2703fb'))


def require(ok,msg):
    if not ok:raise ValueError(msg)


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_exclusive(src,dst,uid=1000):
    require(not src.is_symlink() and src.is_file(),'regular source required')
    with src.open('rb') as source,dst.open('xb') as target:
        shutil.copyfileobj(source,target);target.flush();os.fsync(target.fileno())
    os.chown(dst,uid,uid);os.chmod(dst,0o444)
    require(sha(src)==sha(dst),'copy mismatch '+str(dst))


def verify_packet(packet,inventory_sha,*,installed=False):
    require(all(not p.is_symlink() for p in (packet,*packet.parents)),'packet path symlink')
    inventory=packet/'preparation-inventory.json'
    require(not inventory.is_symlink() and sha(inventory)==inventory_sha,'reviewed inventory hash differs')
    document=json.loads(inventory.read_bytes())
    names=set()
    for row in document['files']:
        name=row['path']
        require(type(name) is str and Path(name).name==name and name not in names,'packet membership/path')
        names.add(name)
        path=packet/name
        require(path.is_file() and not path.is_symlink(),'regular packet member required')
        require(path.stat().st_size==row['size_bytes'] and sha(path)==row['sha256'],'packet file binding differs')
    extras={'original-public-inputs-reuse.json',*(row[1] for row in PUBLIC)} if installed else set()
    actual={p.name for p in packet.iterdir()}
    required=names|{'preparation-inventory.json'}|extras
    generated={'d124-attestation-v26.json'} if installed else set()
    require(required<=actual and actual-required<=generated,'expanded/incomplete packet')
    require({'initialize-v29.py','run_clock_qualification_v29.py','isolation_core.py','release-bindings.json'}<=names,'required packet member missing')
    require('initialize_program.py' not in names and 'initialize-program.py' not in names,'archive program initialization forbidden')
    require(sha(packet/'isolation_core.py')==CORE_SHA,'frozen infrastructure differs')
    return document


def install(bootstrap,inventory_sha):
    require(os.geteuid()==0,'root installer required')
    require(bootstrap.parent==ROOT and bootstrap.name=='v29-bootstrap-1','fresh named E29 bootstrap required')
    packet=bootstrap/'packet-1'
    verify_packet(packet,inventory_sha)
    binding=json.loads((packet/'release-bindings.json').read_bytes())
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==binding['boot_id'],'boot changed')
    require(not E.exists() and not E.is_symlink() and not CORE_DIRECTORY.exists() and not CORE_DIRECTORY.is_symlink(),'fresh E29/root-core namespaces required')
    name=binding['bundle_name']+'.tar.gz'
    require(Path(name).name==name,'archive basename')
    require(sha(bootstrap/name)==binding['archive_sha256'],'archive binding differs')
    require((bootstrap/(name+'.sha256')).read_text()==binding['archive_sha256']+'  '+name+'\n','archive sidecar differs')
    for filename in (name,name+'.sha256'):
        require(not (bootstrap/filename).is_symlink(),'archive symlink')
        os.link(bootstrap/filename,ROOT/filename)
        os.chown(ROOT/filename,1000,1000);os.chmod(ROOT/filename,0o400)
    # initialize-v26 creates only a fresh qualification evidence/admission root.
    # It does not initialize ProgramStore or touch the existing E23 program.
    with (bootstrap/'initialize-v26.log').open('xb') as log:
        subprocess.run(['/usr/bin/python3','-B',str(packet/'initialize-v29.py')],
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    core_mode=0o755
    CORE_DIRECTORY.mkdir(mode=core_mode)
    os.chown(CORE_DIRECTORY,0,0)
    copy_exclusive(packet/'isolation_core.py',CORE_DIRECTORY/'isolation_core.py',uid=0)
    prep=E/'operator-preparation-v29'
    prep.mkdir(mode=0o700);os.chown(prep,1000,1000)
    for src in sorted(packet.iterdir()):copy_exclusive(src,prep/src.name)
    original=ROOT/'local-authoring-cpuprefetchv5-21/operator-preparation-v21'
    rows=[]
    for old,new,expected in PUBLIC:
        require(sha(original/old)==expected,'original public search/known-hosts binding differs')
        copy_exclusive(original/old,prep/new)
        rows.append(dict(original_path=str(original/old),path=str(prep/new),sha256=expected,size_bytes=(prep/new).stat().st_size))
    with (prep/'original-public-inputs-reuse.json').open('x') as stream:
        json.dump(dict(original_records_unchanged=True,new_search_claimed=False,files=rows),stream,sort_keys=True,indent=2)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.chown(prep/'original-public-inputs-reuse.json',1000,1000)
    print('V29_INSTALL_PASS_NO_ARCHIVE_PROGRAM_INITIALIZATION',E,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bootstrap',type=Path,required=True)
    p.add_argument('--packet-inventory-sha256',required=True)
    args=p.parse_args();install(args.bootstrap,args.packet_inventory_sha256)


if __name__=='__main__':main()
