#!/usr/bin/env python3
"""Generate an exclusive install/start payload locally; never connects or executes it."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
OLD = HERE.parent / 'd213-reanalysis/run_reanalysis.py'
REMOTE_PARENT = '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-20'
REMOTE_ROOT = REMOTE_PARENT + '/discovery-analysis-r3-d224-1'
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
NAMES = ('stage17_discovery_validation_v3.py', 'stage17_discovery_validation_parallel_v1.py',
    'validate_d207_retained_study_parallel_v1.py', '0213-discovery-whole-plot-readback-validation.md',
    '0224-parallel-retained-discovery-validation.md', 'run_parallel_analysis.py')


def original_argv(path):
    tree = ast.parse(path.read_text())
    found = [node.value for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == 'ARGV' for target in node.targets)]
    if len(found) != 1:
        raise ValueError('exact one original ARGV literal required')
    value = ast.literal_eval(found[0])
    if type(value) is not list or not all(type(item) is str for item in value):
        raise ValueError('original ARGV must be a literal string list')
    return value


def adapted_argv(path=OLD):
    original = original_argv(path)
    if original[:3] != ['/usr/bin/python3', '-B', REMOTE_PARENT + '/discovery-analysis-r3-d213-1/validate_d207_retained_study_v2.py']:
        raise ValueError('original executable/wrapper differs')
    if len(original[3:]) % 2 or len(set(original[3::2])) != len(original[3::2]):
        raise ValueError('original flags malformed/duplicated')
    result = original.copy()
    result[2] = REMOTE_ROOT + '/validate_d207_retained_study_parallel_v1.py'
    for key, value in (('--scratch-directory', REMOTE_ROOT + '/scratch'),
                       ('--output', REMOTE_ROOT + '/scratch/full-study-validation-parallel-v1.json')):
        result[result.index(key) + 1] = value
    changed = [i for i in range(len(original)) if result[i] != original[i]]
    expected = [2, original.index('--scratch-directory') + 1, original.index('--output') + 1]
    if sorted(changed) != sorted(expected):
        raise ValueError('only three analysis-local argv paths may change')
    return result


INSTALL = '''#!/usr/bin/env python3
# Generated install/start payload. Execute only after main's review, as UID1000.
import base64,datetime,hashlib,json,os,pathlib,subprocess
V=pathlib.Path(REMOTE_LITERAL)
ROWS=ROWS_LITERAL
MANIFEST_SHA=MANIFEST_LITERAL
def require(ok,message):
 if not ok:raise ValueError(message)
def write(name,data):
 fd=os.open(V/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
require(os.getuid()==os.geteuid()==1000,'UID1000 required')
os.umask(0o077)
for part in (V,*V.parents):require(not part.is_symlink(),'symlink destination')
decoded=[]
for row in ROWS:
 require('/' not in row['name'] and row['name'] not in ('.','..'),'flat installed name')
 data=base64.b64decode(row['base64'],validate=True)
 require(len(data)==row['size_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],'payload binding differs')
 decoded.append((row['name'],data))
require(len({name for name,data in decoded})==len(decoded),'duplicate installed file')
V.mkdir(mode=0o700)
(V/'scratch').mkdir(mode=0o700)
for name,data in decoded:write(name,data)
for row in ROWS:require(hashlib.sha256((V/row['name']).read_bytes()).hexdigest()==row['sha256'],'installed readback differs')
directory=os.open(V,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
try:os.fsync(directory)
finally:os.close(directory)
argv=['/usr/bin/python3','-B',str(V/'run_parallel_analysis.py'),'--manifest-sha256',MANIFEST_SHA]
fd=os.open(V/'supervisor-console.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
with os.fdopen(fd,'wb') as out:
 proc=subprocess.Popen(argv,cwd=V,stdin=subprocess.DEVNULL,stdout=out,stderr=out,start_new_session=True,close_fds=True,
   env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'})
record=dict(supervisor_pid=proc.pid,argv=argv,installation_sha256=MANIFEST_SHA,analysis_root=str(V),
 started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution_authority=False,raw_mutation=False)
write('analysis-supervisor-pid.json',(json.dumps(record,sort_keys=True,indent=2)+'\\n').encode())
print(json.dumps(record,sort_keys=True))
'''


def prepare(destination):
    files = {name:(HERE/name).read_bytes() for name in NAMES}
    # The copied code and decisions must still be the reviewed source bytes.
    for name, directory in ((NAMES[0], 'tools'), (NAMES[1], 'tools'),
                            (NAMES[3], 'docs/decisions'), (NAMES[4], 'docs/decisions')):
        if files[name] != (REPOSITORY / directory / name).read_bytes():
            raise ValueError('stale copied dependency: ' + name)
    wrapper = files[NAMES[2]].decode()
    for key, name in (('SUCCESSOR_SHA256',NAMES[0]), ('PARALLEL_SHA256',NAMES[1]),
                      ('CORRECTION_SHA256',NAMES[3]), ('PARALLEL_DECISION_SHA256',NAMES[4])):
        value = re.search(r'^' + key + r" = '([0-9a-f]{64})'$", wrapper, re.MULTILINE)
        if value is None or value.group(1) != hashlib.sha256(files[name]).hexdigest():
            raise ValueError('stale wrapper binding: ' + key)
    bindings = [dict(name=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                for name,raw in files.items()]
    argv = adapted_argv()
    manifest = dict(schema_version='d224-analysis-installation/1', analysis_root=REMOTE_ROOT,
        expected_boot_id=BOOT, argv=argv, files=bindings,
        original_launcher=dict(path=str(OLD.relative_to(REPOSITORY)),sha256=hashlib.sha256(OLD.read_bytes()).hexdigest()),
        changed_argv_fields=['wrapper','--scratch-directory','--output'],execution_authority=False,raw_mutation=False)
    raw = (json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    digest = hashlib.sha256(raw).hexdigest()
    files['installed-bindings.json'] = raw
    rows = [dict(name=name,size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                 base64=base64.b64encode(data).decode()) for name,data in files.items()]
    script = INSTALL.replace('REMOTE_LITERAL',repr(REMOTE_ROOT)).replace('ROWS_LITERAL',repr(rows)).replace('MANIFEST_LITERAL',repr(digest))
    compile(script, 'install-and-start.py', 'exec')
    destination.mkdir(mode=0o700)
    for name,data in (('install-and-start.py',script.encode()),('installed-bindings.json',raw)):
        with (destination/name).open('xb') as stream:
            stream.write(data)
    summary = dict(installation_sha256=digest,installer_sha256=hashlib.sha256(script.encode()).hexdigest(),
        installer_path=str(destination/'install-and-start.py'),files=bindings,remote_root=REMOTE_ROOT,
        expected_uid=1000,execution_authority=False,raw_mutation=False,executed=False)
    (destination/'preparation-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output),sort_keys=True,indent=2))
