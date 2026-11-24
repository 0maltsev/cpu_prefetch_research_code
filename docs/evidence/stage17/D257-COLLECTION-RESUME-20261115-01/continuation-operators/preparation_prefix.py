"""D257 exact unsigned metadata adoption after the sole historical read error."""
import json
from pathlib import Path

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26')
PLAN = '53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486'
CAPACITY = str(E.parent/'local-authoring-cpuprefetchv5-25/formal-q16b-preparation-2/stand-program-capacity.json')


def require(ok, message):
    if not ok:
        raise ValueError('unsigned preparation prefix: '+message)


def adopt(binding, read, original_write, canonical, out, packet):
    d = json.loads(read(binding))
    require(set(d) == set('schema_version plan_sha256 failed_study failed_audit prefix_members '
                         'reusable_files original_preparation_deadline_ns execution_authority phase18_authority'.split()),
            'closed prefix fields')
    require(d['schema_version'] == 'software-d257-unsigned-preparation-prefix/1'
            and d['plan_sha256'] == PLAN and d['execution_authority'] is False
            and d['phase18_authority'] is False
            and d['original_preparation_deadline_ns'] == 1210558041457866, 'prefix scope differs')
    require(out == E/'daycap-collection-preparation-1'
            and packet == E/'daycap-resume-configuration-1', 'exact unexecuted prefix namespace')
    require(d['failed_study']['path'] == str(E/'daycap-resume-study-1/study-result.json'), 'failed supervisor differs')
    failed = json.loads(read(d['failed_study']))
    require(failed['success'] is False and failed['automatic_retries'] == 0
            and failed['source_revision'] == 'aa3285f15acbd3314cae64a628c113488a8438b8'
            and failed['reduced_q16b_calibration_done'] is False
            and [r['phase'] for r in failed['phases']] == ['retained-admission','preparation']
            and failed['partition_restoration'] == dict(errors=[],not_rearmed=True,verified=True),
            'no precollection metadata-only failure proof')
    require(d['failed_audit']['path'] == str(out/'stand-namespace-audit.json'), 'failed audit differs')
    audit = json.loads(read(d['failed_audit']))
    require(audit['status'] == 'FAIL' and audit['matches'] == [] and len(audit['errors']) == 1,
            'failure was not the sole read-permission error')
    error = audit['errors'][0]
    require(error['path'] == CAPACITY and '[Errno 13] Permission denied:' in error['reason'],
            'different audit error; no automatic continuation')
    members = d['prefix_members']
    names = {'plan.json','namespace_registry.json','action-inputs.json',
             'stand-namespace-audit.json','stand-namespace-audit.stderr'}
    require(len(members) == len(names) and {Path(b['path']) for b in members} == {out/n for n in names}
            and {p.name for p in out.iterdir()} == names, 'partial prefix changed or expanded')
    for b in members:
        read(b)
    require(not (E/'admission-root/evidence/formal-q16b-daycap-1').exists(), 'request authority already exists')
    require(not (E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1/working'/PLAN).exists(),
            'family already registered or attempted')
    expected = {out/n for n in ('plan.json','namespace_registry.json','action-inputs.json')} | {
        packet/n for n in ('q16a-compatibility.json','historical-inputs.json')}
    bindings = {Path(b['path']):b for b in d['reusable_files']}
    require(len(d['reusable_files']) == len(expected) and set(bindings) == expected, 'reuse population differs')
    for b in bindings.values():
        read(b)
    def write(path, value):
        path = Path(path)
        if path not in bindings:
            return original_write(path,value)
        wanted = value if isinstance(value,bytes) else canonical(value)
        require(read(bindings[path]) == wanted, 'recomputed metadata differs: '+str(path))
        return bindings[path]
    return write
