import datetime as dt,hashlib,json,os,sys,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
assert os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups()
p=E/'d298-continuation-4';config=p/'launch-configuration.json';sha='afef345d8a0183d51a469266ad159dc337d969d76ebb3770341ce44b66543c63'
assert hashlib.sha256(config.read_bytes()).hexdigest()==sha
sys.path.insert(0,str(p));import stage17_q16c_continuation_operator_v1 as io
c=json.loads(config.read_bytes());root=Path(c['repository_root']);req=root/'evidence/formal-q16c-d295-1/request.json'
assert io.binding(req)['sha256']=='38fc71fd8e6a5dc79c95284999fa51b6b42a41d7cdb6477b4886272af931851c'
assert not Path(c['cgroup']).exists() and Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip()=='1'
assert not (req.parent/'authorization.json').exists()
workspace=E/'d300-authorization-software-check-1';workspace.mkdir(mode=0o700)
cli=io.cli_for(c,configured=True);author=io.common(c,author=True)
now=dt.datetime.now(dt.timezone.utc);started=time.monotonic_ns()
issued=now.isoformat(timespec='seconds').replace('+00:00','Z')
expires=(now+dt.timedelta(seconds=24860)).isoformat(timespec='seconds').replace('+00:00','Z')
auth=cli.author_formal_authorization(**author,request_path=req,actor='maltsev.oiu@phystech.edu',reviewer='OWNER',issued_at_utc=issued,expires_at_utc=expires,destination=workspace/'authorization-draft.json')
assert not Path(str(auth)+'.sig').exists() and not Path(c['cgroup']).exists()
built=io.document(c['preconstruction']);family=Path(c['program_root'])/'working'/built['plan']['sha256']
assert not (family/'stage17-q16c-attempt-v6.json').exists()
r=dict(status='ACTUAL_OWNER_UNSIGNED_AUTHORIZATION_SCHEMA_AND_LINEAGE_PASS',checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),elapsed_ns=time.monotonic_ns()-started,configuration_sha256=sha,unsigned_request=io.binding(req),unsigned_draft=io.binding(auth),issued_at_utc=issued,expires_at_utc=expires,authority_interval_seconds=24860,signed=False,executed=False,controls_rearmed=False,new_execution_window=False,qualification_repeated=False,raw_validation_repeated=False,execution_authority=False)
with (workspace/'verification.json').open('x') as f:json.dump(r,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
print(json.dumps(r),flush=True)
