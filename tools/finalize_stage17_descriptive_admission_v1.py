"""D309 preserve the noncanonical preview and replay the already appended EXT007."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess

import admit_stage17_descriptive_freeze_v2 as entry
from prepare_stage17_descriptive_freeze_v1 import E,load_io

PREVIEW_SHA = '3dfcbdfb3efdf7b5d9c26ad5b8cc32dcd672473e1088bb288ae652e63da7d935'
JOURNAL_SHA = '9a7766e806b872133dbd0f6a746d75ae315dae69bc8c5e7b9bad9f95c9c003e0'
RESOLUTION_SHA = 'fd4a2b1a1c0c9cf0ab6ecf47fa838de81e67746c67caebad8b15779f4c70f104'
OLD_SHA = '2fab0d69e3350dea0106a1fd5a0aa0ddd04dab8bae1956815e66ad47a378f5aa'


def utc(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def sync_directory(path):
    fd = os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def preserve_preview(source,destination,expected_sha):
    """Durable exclusive copy by hard link, then remove only the live locator."""
    entry.scoped.require(not source.is_symlink() and stat.S_ISREG(source.stat().st_mode),'regular preview')
    raw = source.read_bytes()
    entry.scoped.require(hashlib.sha256(raw).hexdigest() == expected_sha,'exact preview to preserve')
    os.link(source,destination,follow_symlinks=False)
    sync_directory(destination.parent)
    entry.scoped.require(destination.read_bytes() == raw,'durable unchanged preserved preview')
    source.unlink(); sync_directory(source.parent)
    return dict(old_path=str(source),new_path=str(destination),size_bytes=len(raw),sha256=expected_sha,
                bytes_unchanged=True,canonical_journal_modified=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository-root',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    a = p.parse_args()
    require = entry.scoped.require
    require(os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups(),'actual owner')
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2); os.sched_setaffinity(0,{3}); signal.alarm(600)
    io,c = load_io(); root = a.repository_root
    require(root == Path(c['repository_root']) and a.output_root == E/'d309-ext007-final-replay-1'
            and not a.output_root.exists(),'exact fresh recovery scope')
    status = dict(line.split('=',1) for line in subprocess.check_output(['systemctl','show',
        'cpu-prefetch-d308-admit-1.service','-p','MainPID','-p','ExecMainStatus'],text=True).splitlines())
    require(status == dict(MainPID='0',ExecMainStatus='1'),'original metadata writer exited')
    paths = dict(old=E/'journal/stage17-state-journal-000009.json',
                 journal=E/'journal/stage17-state-journal-000010.json',
                 resolution=E/'records/resolution-007-s17-ext-007.json')
    snapshots = {k:io.read(io.binding(v)) for k,v in paths.items()}
    for key,digest in (('old',OLD_SHA),('journal',JOURNAL_SHA),('resolution',RESOLUTION_SHA)):
        require(hashlib.sha256(snapshots[key]).hexdigest() == digest,'exact existing '+key)
    old,journal = (json.loads(snapshots[k]) for k in ('old','journal'))
    require(journal['resolution_records'][:-1] == old['resolution_records'] and
            journal['transition_records'] == old['transition_records'],'immutable six predecessors and transitions')
    failure = io.document(io.binding(E/'d308-ext007-admission-1/failure.json'))
    require(failure['message'] == 'journal fork detected','exact post-publication failure')
    preview = E/'journal/d308-scoped-admission-preview.json'
    preview_proof = io.document(io.binding(E/'d308-ext007-admission-1/preview-verified.json'))
    require(preview_proof['preview'] == io.binding(preview),'actual successful preview binding')
    a.output_root.mkdir(mode=0o700)
    try:
        io.save(a.output_root/'relocation-intent.json',dict(source=io.binding(preview),
            destination=str(a.output_root/'preserved-preview.json'),canonical_journal=io.binding(paths['journal']),
            resolution=io.binding(paths['resolution']),source_code=io.binding(Path(__file__).resolve()),
            created_at_utc=utc(),new_measurements=0,execution_authority=False,phase18_authority=False))
        moved = preserve_preview(preview,a.output_root/'preserved-preview.json',PREVIEW_SHA)
        io.save(a.output_root/'relocation.json',dict(moved,completed_at_utc=utc(),phase18_authority=False))
        cli = entry.cloning._clone_module(entry.original_cli,dict(journal_runtime=entry.journal))
        after = cli.validate_journal(repository_root=root,evidence_root=E,
            pilot_archive=Path(c['archive']['path']),pilot_sidecar=Path(c['sidecar']['path']))
        require(len(after.resolutions) == 7 and len(after.transitions) == 3 and after.pilot_ready is False,
                'actual full existing canonical replay')
        resolution = after.resolutions['S17-EXT-007']
        require(resolution.sha256 == RESOLUTION_SHA and
                resolution.semantic_context['calibration_scope'] == entry.scoped.freeze.SCOPE and
                resolution.semantic_context['data_provenance_accepted'] is True,'actual scoped accepted EXT007')
        for key,path in paths.items(): require(io.read(io.binding(path)) == snapshots[key],'unchanged canonical '+key)
        data = E/'descriptive-calibration-freeze-1'
        result = dict(status='SCOPED_EXT007_OPERATIONALLY_ADMITTED',completed_at_utc=utc(),
            journal=io.binding(paths['journal']),resolution=io.binding(resolution.path),
            policy=io.binding(root/entry.semantic.POLICY_PATH),manifest=io.binding(data/'ext007-manifest-v5.json'),
            custody_receipt=io.binding(E/'receipts/d308-ext007-descriptive-freeze-1.json'),
            freeze=io.binding(data/'calibration-freeze.json'),resolved_inputs=list(after.resolutions),
            unresolved_inputs=[f'S17-EXT-{i:03d}' for i in (8,9,10)],current_state=after.current_state,
            preserved_predecessor_count=6,transition_count=3,calibration_scope=entry.scoped.freeze.SCOPE,
            legacy_statistical_freeze_satisfied=False,pilot_ready=False,stage17_complete=False,
            new_measurements=0,raw_decoding_repeated=False,new_qualification=False,
            new_resolution_appended=False,canonical_journal_modified=False,phase18_authority=False)
        io.save(a.output_root/'complete.json',result); print(json.dumps(result),flush=True)
    except BaseException as error:
        io.save(a.output_root/'failure.json',dict(type=type(error).__name__,message=str(error),
            new_measurements=0,execution_authority=False,phase18_authority=False))
        raise


if __name__ == '__main__': main()
