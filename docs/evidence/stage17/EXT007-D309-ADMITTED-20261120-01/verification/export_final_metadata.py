import base64,datetime as dt,hashlib,json,os,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
e=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
def doc(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
names=['d309-ext007-final-replay-1/complete.json','d308-ext007-admission-1/preview-verified.json','d308-admission-install-1.json','records/resolution-007-s17-ext-007.json','journal/stage17-state-journal-000010.json','receipts/d308-ext007-descriptive-freeze-1.json','descriptive-calibration-freeze-1/ext007-manifest-v5.json','records/d308-preview-resolution-007.json','d309-ext007-final-replay-1/preserved-preview.json','d309-final-replay-console-1.log','d309-ext007-final-replay-1/relocation-intent.json','d309-ext007-final-replay-1/relocation.json','d309-final-replay-packet-1/manifest.json']
status=dict(x.split('=',1) for x in subprocess.check_output(['systemctl','show','cpu-prefetch-d309-final-replay-1.service','-p','ActiveState','-p','SubState','-p','MainPID','-p','ExecMainStatus','-p','Result','-p','ControlGroup','-p','InvocationID'],text=True).splitlines())
assert status['MainPID']=='0' and status['ExecMainStatus']=='0' and status['ActiveState']=='inactive'
complete=doc(e/names[0]);assert complete['status']=='SCOPED_EXT007_OPERATIONALLY_ADMITTED'
old=e/'journal/stage17-state-journal-000009.json';assert sha(old)=='2fab0d69e3350dea0106a1fd5a0aa0ddd04dab8bae1956815e66ad47a378f5aa'
a=doc(old);b=doc(e/names[4]);assert b['journal_sequence_number']==10
assert b['resolution_records'][:-1]==a['resolution_records']
assert b['transition_records']==a['transition_records']
assert b['previous_journal']==dict(path=str(old.relative_to(e)),sha256=sha(old))
for binding in b['resolution_records']+b['transition_records']:assert sha(e/binding['path'])==binding['sha256']
for key in ('journal','resolution','policy','manifest','custody_receipt','freeze'):
 v=complete[key];p=Path(v['path']);assert len(p.read_bytes())==v['size_bytes'] and sha(p)==v['sha256']
assert not (e/'journal/d308-scoped-admission-preview.json').exists()
assert complete['new_resolution_appended'] is False and complete['canonical_journal_modified'] is False
assert sha(e/'d309-ext007-final-replay-1/preserved-preview.json')=='3dfcbdfb3efdf7b5d9c26ad5b8cc32dcd672473e1088bb288ae652e63da7d935'
assert complete['new_measurements']==0 and complete['raw_decoding_repeated'] is False
assert complete['pilot_ready'] is False and complete['stage17_complete'] is False and complete['phase18_authority'] is False
cfg=doc(e/'d306-continuation-1/launch-configuration.json');assert not Path(cfg['cgroup']).exists()
assert Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip()=='1'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
result={}
for name in names:
 p=e/name;assert p.is_file() and not p.is_symlink() and p.stat().st_size<1024**2
 raw=p.read_bytes();result[name]=dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),data=base64.b64encode(raw).decode())
audit=dict(status='SCOPED_EXT007_FINAL_METADATA_VERIFIED',checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),unit=status,preserved_predecessor_count=6,transition_count=3,journal_sequence_number=10,original_journal_sha256=sha(old),all_record_hashes_verified=True,complete_bindings_verified=True,native_cgroup_absent=True,guard_value='1',boot_unchanged=True,raw_data_transferred=False,new_measurements=0,pilot_ready=False,stage17_complete=False,phase18_authority=False)
print(json.dumps(dict(files=result,audit=audit)),flush=True)
