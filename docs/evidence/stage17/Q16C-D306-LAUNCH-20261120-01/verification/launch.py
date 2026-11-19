"""One owner-approved launch, with a durable exclusive intent before systemd."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
import types

e = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
ops = e/'d306-continuation-1'; configuration = ops/'launch-configuration.json'
sha = 'bf817971e193d8e4fa1e1ba0ba947583467561aa95a6a1f64db259571c43d6c0'
assert hashlib.sha256(configuration.read_bytes()).hexdigest() == sha
sys.path.insert(0, str(ops))
import stage17_q16c_continuation_study_v1 as study
import stage17_q16c_handoff_continuation_v1 as resume
args = types.SimpleNamespace(configuration=configuration, configuration_sha256=sha)
c, core = study.configure(args)
check = json.loads((ops/'prelaunch-check.json').read_bytes())
assert check['status'] == 'D306_ACTUAL_INSTALLED_ADMISSION_PASS' and check['configuration_sha256'] == sha
assert check['d301_d302_d306_owner_signatures_verified'] is True
assert check['stopped_signed_handoff_preserved'] is True
resume.validate_handoff(c)
resume.check_time(time.monotonic_ns(), c)
for unit in ('cpu-prefetch-d301-v32-1.service', 'cpu-prefetch-d306-v32-1.service'):
    facts = dict(x.split('=',1) for x in subprocess.check_output([
        'systemctl','show',unit,'-p','MainPID','-p','ControlGroup'],text=True).splitlines())
    assert facts == {'MainPID':'0','ControlGroup':''}, facts
for name in ('d306-study-1','platform-guard-d306-1','d306-independent-recovery-1.json'):
    assert not (e/name).exists(), name
assert Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip() == '1'
mem = int(next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')).split()[1])*1024
v = os.statvfs(e); free = v.f_bavail*v.f_frsize
assert mem >= 112*1024**3 and free >= (512+256+16)*1024**3
recovery = f'/usr/bin/python3 -B {ops}/stage17_q16c_continuation_recovery_v1.py --configuration {configuration} --configuration-sha256 {sha}'
argv = ['systemd-run','--unit=cpu-prefetch-d306-v32-1.service',
    '--property=Type=exec','--property=RuntimeMaxSec=31460','--property=TimeoutStopSec=2400',
    '--property=KillMode=process','--property=Restart=no','--property=CPUAffinity=3',
    '--property=LimitMEMLOCK=8388608','--property=NoNewPrivileges=no',
    '--property=WorkingDirectory='+str(ops),'--property=ExecStopPost='+recovery,
    '--property=StandardOutput=append:'+str(e/'d306-service-console-1.log'),
    '--property=StandardError=inherit','--property=UMask=0077',
    '--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=PYTHONOPTIMIZE=0',
    '/usr/bin/python3','-B',str(ops/'stage17_q16c_continuation_study_v1.py'),
    '--run','--configuration',str(configuration),'--configuration-sha256',sha]
resume.check_time(time.monotonic_ns(),c)
intent = dict(schema_version='cpu-prefetch-d306-root-launch-intent/1',
    recorded_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), recorded_monotonic_ns=time.monotonic_ns(),
    unit='cpu-prefetch-d306-v32-1.service', configuration_sha256=sha,
    estimated_elapsed_seconds=[14400,25200], continuation_maximum_seconds=31460,
    admitted_day_deadline_ns=resume.runtime_deadline(c), reused_capture_count=86, remaining_capture_count=94,
    automatic_retries=0,new_execution_window=False,qualification_repeated=False,
    raw_validation_repeated=False,phase18_authority=False,
    available_memory_bytes=mem,free_filesystem_bytes=free,argv=argv)
study.io.save(e/'d306-root-launch-intent-1.json',intent)
p = subprocess.run(argv,capture_output=True,text=True,timeout=30)
result = dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,
    recorded_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
study.io.save(e/'d306-root-launch-result-1.json',result)
print(json.dumps(result),flush=True)
assert p.returncode == 0, result
