"""D288 root-held guard readback at each qualification packet boundary."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-30')
OPERATORS = frozenset(('stage17_q16c_continuation_operator_v1','stage17_q16c_continuation_study_v1',
    'stage17_q16c_continuation_recovery_v1','stage17_q16c_prefix_operator_v1',
    'stage17_q16c_continuation_plan_v1','stage17_q16c_qualification_guard_v1'))


def release():
    # The root supervisor authenticates the complete qualification packet and
    # pins this actual release record before any step. Never infer a revision
    # or binary digest from a checkout, an old candidate or a default value.
    packet=Path(__file__).resolve().parent
    record=json.loads((packet/'release-bindings.json').read_bytes())
    inventory=json.loads((packet/'preparation-inventory.json').read_bytes())
    rows=[r for r in inventory['files'] if r['path']=='release-bindings.json']
    raw=(packet/'release-bindings.json').read_bytes()
    assert len(rows)==1 and rows[0]['size_bytes']==len(raw) and rows[0]['sha256']==hashlib.sha256(raw).hexdigest()
    assert Path(record['bundle_name']).name==record['bundle_name']
    return record


def project(name):
    # Before ordinary admission exists, accept only actual verified bundle bytes.
    import importlib
    selected=release();B=E/'local-bundle-extract'/selected['bundle_name']
    sys.path.insert(0, str(B / 'tools'))
    module = importlib.import_module(name)
    inventory = json.loads((B / 'BUNDLE_INVENTORY.json').read_bytes())
    assert inventory['source_revision'] == selected['source_revision']
    for key, item in tuple(sys.modules.items()):
        if key.startswith('stage17_') and key not in OPERATORS:
            path = Path(item.__file__)
            assert path.parent in (B / 'tools',E/'admission-root/tools'), 'foreign qualification project module'
            member = 'tools/'+path.name
            rows = [r for r in inventory['files'] if r['path'] == member]
            assert len(rows) == 1
            data = path.read_bytes()
            assert len(data) == rows[0]['size_bytes'] and hashlib.sha256(data).hexdigest() == rows[0]['sha256']
    return module


def verify():
    import fcntl
    # Avoid importing the entire execution graph in each root qualification step.
    controls = project('stage17_locked_compaction_guard_v1')
    record = json.loads((E / 'platform-guard-1/witness.json').read_bytes())
    fd = os.open(controls.LEASE, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        actual = os.fstat(fd)
        assert [actual.st_dev, actual.st_ino] == record['lease_identity']
        raw = os.pread(fd, 4097, 0)
        assert len(raw) <= 4096 and hashlib.sha256(raw).hexdigest() == record['lease_sha256']
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            raise RuntimeError('root guard lock is not held')
        fields = Path('/proc/' + str(record['supervisor_pid']) + '/stat').read_text().rsplit(')', 1)[1].split()
        assert fields[0] not in ('Z', 'X', 'x') and int(fields[19]) == record['supervisor_start_ticks']
        assert time.monotonic_ns() < record['deadline_monotonic_ns']
        control = controls.LinuxControl()
        assert control.boot() == record['boot_id'] and control.read() == 0
        return record
    finally:
        os.close(fd)


def infrastructure(configuration):
    verify()
    window = project('stage17_q16c_execution_window_v3')
    record = json.loads((E / 'd288-execution-window-1/window.json').read_bytes())
    selected=release()
    return window.infrastructure(record, configuration['isolation_config'], now=time.monotonic_ns(),
        expected_source=selected['source_revision'], expected_worker=selected['worker_sha256'],
        expected_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
