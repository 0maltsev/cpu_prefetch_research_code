import datetime, hashlib, json, subprocess
from pathlib import Path

base = Path('/home/omaltsev/stage17-owner-evidence')
e = base / 'local-authoring-cpuprefetchv5-32'
result = json.loads((e / 'd301-study-1/result.json').read_bytes())
recovery = json.loads((e / 'd301-independent-recovery-1.json').read_bytes())
unit = dict(line.split('=', 1) for line in subprocess.check_output([
    'systemctl', 'show', 'cpu-prefetch-d301-v32-1.service', '-p', 'ActiveState',
    '-p', 'SubState', '-p', 'MainPID', '-p', 'ControlGroup', '-p', 'ExecMainStatus',
    '-p', 'InvocationID'], text=True).splitlines())
family = base / 'local-authoring-cpuprefetchv5-23/formal-archive-program-1/working/1212db59b9c12dd50837ca4b79897ddcd76a06fc4c3ea99b1fabd9b2b23b36a6'
assert unit['MainPID'] == '0' and unit['ControlGroup'] == ''
assert unit['ActiveState'] == 'failed' and unit['ExecMainStatus'] == '1'
assert result['success'] is False and result['partition_restoration']['verified'] is True
assert recovery['verified'] is True and recovery['errors'] == []
assert [p['role'] for p in result['phases']] == ['authorize', 'sign-collect']
assert [p['exit_code'] for p in result['phases']] == [0, 1]
assert all(p['leader_reaped'] is True for p in result['phases'])
assert not family.is_symlink() and not list(family.iterdir())
assert (family.stat().st_dev, family.stat().st_ino) == (2307, 211681674)
guard = Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip()
assert guard == '1'
bindings = {}
for name, expected in {
    'admission-root/evidence/formal-q16c-d295-1/authorization.json': 'd79d9be2fbcd86e4aebf953fdea4ee6f4e3a4a760ec9ba1107c29e3aa42e6b70',
    'admission-root/evidence/formal-q16c-d295-1/authorization.json.sig': '3a40999a3845e004c3ae7d83034649200c44cd2c4b512c416129ad286b2eb18a',
    'd297-software-preparation-2/constructed-output/prepared.json': 'dd9a57a78c6030c0275e60ac369c294eba88b693788d13f1e29ae1239e9c402a',
}.items():
    raw = (e / name).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == expected, name
    bindings[name] = dict(size_bytes=len(raw), sha256=digest)
print(json.dumps(dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    unit=unit, stopped_two_phase_result_verified=True, supervisor_restoration_verified=True,
    independent_restoration_verified=True, empty_family_verified=True,
    family_device_inode=[2307, 211681674], guard_value=guard, preserved_handoff=bindings,
    execution_started=False, controls_rearmed=False, raw_data_transferred=False), sort_keys=True, indent=2))
