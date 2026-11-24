import datetime as dt,hashlib,json,os,sys,time,types
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32');p=E/'d301-continuation-1'
f=p/'launch-configuration.json';sha='7b14ddd9989cfc779cc2959e94b0d2e7a71420ce73a3b565382935de1e1b23a1'
assert hashlib.sha256(f.read_bytes()).hexdigest()==sha
sys.path.insert(0,str(p));import stage17_q16c_continuation_study_v1 as study
import stage17_q16c_saved_request_v1 as saved
args=types.SimpleNamespace(configuration=f,configuration_sha256=sha)
c,h=study.configure(args)
try:saved.check_time(time.monotonic_ns())
except ValueError:pass
else:raise ValueError('Expired D301 unexpectedly became launchable')
record=saved.admit(args,c,software_check=True)
clock=study.module('d301_isolation_software_probe',c['clock_adapter'])
assert clock.Q==E/'clock-rearm-d301-1' and not clock.Q.exists()
assert clock.BINDINGS['isolation_config']==study.io.document(c['qualification_isolation_configuration'])
assert not Path(clock.BINDINGS['isolation_config']['evidence_root']).exists() and not clock.CG.exists()
assert Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip()=='1'
template=study.io.document(c['authorization_template']);schema=study.io.document(c['authorization_schema'])
now=dt.datetime.now(dt.timezone.utc)
draft=saved.finalize_template(template,now,schema,dt.datetime.fromisoformat('2026-11-20T05:37:50.487744+00:00'))
assert all(draft[k]==v for k,v in template.items() if k not in ('issued_at_utc','expires_at_utc'))
assert not (E/'d301-study-1').exists() and not (E/'platform-guard-d301-1').exists()
assert not (Path(c['output_root'])/'prepared.json').exists()
r=dict(status='D301_INSTALLED_SOFTWARE_ADMISSION_PASS_NATIVE_TIME_GATE_CLOSED',checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),configuration_sha256=sha,administrative_source_revision=c['administrative_source_revision'],qualified_native_source_revision=c['source_revision'],registered_family_replay_verified=True,request_template_qualification_bindings_verified=True,retained_reports_verified=86,qualification_repeated=False,raw_validation_repeated=False,hardware_prestate_verified=True,uid1000_owner_and_inventory_verified=True,only_authorization_times_changed=True,launch_permitted=False,operational_authority_signed=False,controls_rearmed=False,new_execution_window=False,execution_authority=False)
with (p/'software-preflight.json').open('x') as s:json.dump(r,s,sort_keys=True,indent=2);s.flush();os.fsync(s.fileno())
with (p/'software-authorization-draft.json').open('x') as s:json.dump(draft,s,sort_keys=True,separators=(',',':'));s.flush();os.fsync(s.fileno())
print(json.dumps(r),flush=True)
