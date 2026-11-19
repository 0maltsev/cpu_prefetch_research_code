"""Read only public administrative receipts; never inspect or transfer raw data."""
from pathlib import Path
import base64
import datetime as dt
import hashlib
import json
import os
import subprocess
import time

os.sched_setaffinity(0, {3})
e = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
names = [
    'd306-root-launch-intent-1.json', 'd306-root-launch-result-1.json',
    'd306-continuation-1/administrative-packet.json', 'd306-continuation-1/operator-sources.json',
    'd306-continuation-1/authority/owner-acceptance.json', 'd306-continuation-1/authority/owner-acceptance.json.sig',
    'd306-continuation-1/prelaunch-check.json', 'd306-continuation-1/acceptance-signing-result.json',
    'd306-continuation-1/runtime-output/constructed.json', 'd306-continuation-1/runtime-output/prepared.json',
    'd306-continuation-1/authorization.json', 'd306-continuation-1/authorization.json.sig',
    'd306-study-1/intent.json', 'd306-study-1/authorize-result.json', 'd306-study-1/sign-collect-result.json',
    'd306-study-1/result.json', 'd306-independent-recovery-1.json',
    'q16c-study-d306-1/partition-restoration.json', 'clock-rearm-d306-1/restoration.json',
]
files = {}
for name in names:
    p = e/name
    if p.is_file():
        assert not p.is_symlink() and p.stat().st_size < 131072
        raw = p.read_bytes()
        files[name] = dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), data=base64.b64encode(raw).decode())
unit = dict(x.split('=',1) for x in subprocess.check_output([
    'systemctl','show','cpu-prefetch-d306-v32-1.service','-p','ActiveState','-p','SubState','-p','MainPID',
    '-p','ControlGroup','-p','ExecMainStatus','-p','InvocationID','-p','ExecMainStartTimestamp','-p','ExecMainExitTimestamp'],text=True).splitlines())
family = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-23/formal-archive-program-1/working/1212db59b9c12dd50837ca4b79897ddcd76a06fc4c3ea99b1fabd9b2b23b36a6')
checkpoints = sorted(family.glob('formal-capture-*-final-checkpoint.json'))
complete = failed = 0
for p in checkpoints:
    assert p.stat().st_size < 131072
    x = json.loads(p.read_bytes())
    complete += x['native_complete'] is True
    failed += x['native_complete'] is False
snapshot = e/'d306-study-1/owned-process-snapshot.json'; native = []
if snapshot.exists():
    s = json.loads(snapshot.read_bytes())
    for p in s['processes']:
        pid = p['pid']; proc = Path('/proc')/str(pid)
        try:
            stat = (proc/'stat').read_text().rsplit(')',1)[1].split()
            if int(stat[19]) != p['start_ticks'] or stat[0] in ('Z','X','x'): continue
            exe = proc/'exe'
            if exe.stat().st_size != 5052696: continue
            sha = hashlib.sha256(exe.read_bytes()).hexdigest()
            if sha != 'bc064c13afd7eb5142ae8ee434e95962e9b3fc3095c6c159d83376c3e7e8c019': continue
            status = dict(x.split(':',1) for x in (proc/'status').read_text().splitlines() if ':' in x)
            native.append(dict(pid=pid,start_ticks=p['start_ticks'],sha256=sha,uid=status['Uid'].strip().split(),
                               cgroup=(proc/'cgroup').read_text().strip()))
        except (FileNotFoundError, ProcessLookupError): pass
status = dict(checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), checked_monotonic_ns=time.monotonic_ns(),
    unit=unit, native_complete_checkpoints=complete, native_failed_checkpoints=failed,
    native_attempt_present=any(family.glob('stage17-q16c-attempt-v*.json')),
    family_entry_count=len(list(family.iterdir())), native_workers=native,
    guard_value=Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip(),raw_data_transferred=False)
print(json.dumps(dict(status=status,files=files)),flush=True)
