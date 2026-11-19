import datetime,hashlib,json,os,sys,time,types
from pathlib import Path
p=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/d298-continuation-4')
cpath=p/'launch-configuration.json';sha='afef345d8a0183d51a469266ad159dc337d969d76ebb3770341ce44b66543c63'
assert hashlib.sha256(cpath.read_bytes()).hexdigest()==sha
sys.path.insert(0,str(p));import stage17_q16c_continuation_study_v1 as study
import stage17_q16c_qualified_continuation_v1 as resume
args=types.SimpleNamespace(configuration=cpath,configuration_sha256=sha)
c,h=study.configure(args)
record=resume.admit(args,c,software_check=True)
clock=study.module('d298_preflight_isolation',c['clock_adapter'])
assert clock.Q==resume.E/'clock-rearm-d298-1'
assert clock.BINDINGS['isolation_config']==json.loads(study.io.read(c['qualification_isolation_configuration']))
assert not clock.Q.exists() and not Path(clock.BINDINGS['isolation_config']['evidence_root']).exists()
assert not clock.CG.exists() and not (Path('/run/systemd/system')/clock.BINDINGS['isolation_config']['unit_name']).exists()
for pair in ('near','far'):
 clock.verify_raw(json.loads((resume.E/'clock-qualification-v32-1'/pair/'clock-raw.json').read_bytes()),pair)
assert Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip()=='1'
assert not (resume.E/'d298-study-1').exists() and not (resume.E/'platform-guard-d298-1').exists()
resume.check_time(time.monotonic_ns())
r=dict(status='D298_ACTUAL_INSTALLED_ADMISSION_PASS',checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),configuration_sha256=sha,administrative_source_revision=c['administrative_source_revision'],qualified_native_source_revision=c['source_revision'],same_original_window=True,original_total_deadline_ns=resume.DEADLINE,full_remaining_envelope_seconds=31460,retained_reports_verified=86,qualification_receipts_verified=7,near_far_retained_raw_verified=True,measured_libraries_verified=9,actual_owner_signature_verified=True,actual_uid1000_journal_and_inventory_audit_passed=True,hardware_prestate_verified=True,fresh_isolation_paths_verified=True,experiments_started=0,qualification_repeated=False,raw_validation_repeated=False,new_execution_window=False,execution_authority=False)
with (p/'prelaunch-check.json').open('x') as f:json.dump(r,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
print(json.dumps(r),flush=True)
