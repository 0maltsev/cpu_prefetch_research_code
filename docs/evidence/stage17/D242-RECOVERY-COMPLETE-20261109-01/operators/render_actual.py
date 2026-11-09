"""Render only the already approved D240 suffix after successful D242 recovery."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
OLD = E.parent/'local-authoring-cpuprefetchv5-23'
NAME = 'cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a'
ADMIN = E/'d242-admin-1'
sys.path.insert(0, str(ADMIN))
import stage17_state_journal_v53 as recovery


def main():
    assert json.loads((E/'d242-commit-1.json').read_bytes())['exit_code'] == 0
    recovery.admin_binding()
    archive = E.parent/(NAME+'.tar.gz')
    def bound(path):
        return dict(path=str(path),size_bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    parent = OLD/'formal-q16a-authoring-v23-1/plan.json'
    parent_binding = bound(parent)
    assert parent_binding['sha256'] == 'a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7'
    document = json.loads(parent.read_bytes())
    names = {'cpuset.cpus','cpuset.cpus.effective','cpuset.cpus.exclusive',
             'cpuset.cpus.partition','cpuset.mems.effective'}
    paths = [row['path'] for row in document['captures'][177]['monitoring']['environment_sources']
             if Path(row['path']).name in names]
    assert len(paths) == 5 and len(set(paths)) == 5
    spec = dict(schema_version='software-q16a-continuation-authoring/1',
        qualification=dict(evidence_root=str(E),journal=str(E/recovery.NEXT_NAME),
            journal_directory=str(E/'journal'),pilot_archive=bound(archive),
            pilot_sidecar=bound(Path(str(archive)+'.sha256'))),
        parent_plan=parent_binding,
        failed_family_receipt=bound(OLD/'formal-archive-program-1/working'/parent_binding['sha256']/'stage17-q16a-failure-v6.json'),
        accepted_prefix_manifest=bound(recovery.PREFIX_PATH),
        original_bundle_root=str(OLD/'local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-dd981b4-clean-d9e61e67bfa8'),
        continuation_bundle_root=str(E/'local-bundle-extract'/NAME),
        monitor_path_replacements=[dict(original_path=p,continuation_path='/sys/fs/cgroup/cpu-prefetch-recovery-v25-qualified-1.service/reserved/'+Path(p).name) for p in paths],
        output_directory=str(E/'formal-q16a-continuation-authoring-1'))
    path = E/'continuation-spec-d242-1.json'
    raw = recovery.canonical(spec)
    recovery.write_exclusive(path, raw)
    bootstrap = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));import stage17_operational_cli_v18 as cli;cli.activate();sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
    subprocess.run(['/usr/bin/python3.14','-B','-c',bootstrap,str(E/'admission-root/tools'),str(ADMIN/'render_continuation.py'),
        '--repository-root',str(E/'admission-root'),'--spec',str(path),
        '--spec-sha256',hashlib.sha256(raw).hexdigest()],check=True,timeout=600)


if __name__ == '__main__': main()
