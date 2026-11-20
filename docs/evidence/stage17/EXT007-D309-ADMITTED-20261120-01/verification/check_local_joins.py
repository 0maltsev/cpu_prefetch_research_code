from pathlib import Path
import hashlib,json,datetime as dt
root=Path.cwd();d=root/'docs/evidence/stage17/EXT007-D309-ADMITTED-20261120-01';e='/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/'
def read(p):return json.loads(p.read_bytes())
def checked(p,b):
 raw=p.read_bytes();assert len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'];return raw
c=read(d/'post-recovery/d309-ext007-final-replay-1/complete.json')
assert c['status']=='SCOPED_EXT007_OPERATIONALLY_ADMITTED'
for key in ('journal','resolution','manifest','custody_receipt'):
 v=c[key];checked(d/'post-recovery'/v['path'].removeprefix(e),v)
checked(root/'config/stage17/stage17-operational-evidence-admission-policy-v65.json',c['policy'])
checked(root/'docs/evidence/stage17/EXT007-D307-FREEZE-PUBLISHED-20261120-01/descriptive-calibration-freeze-1/calibration-freeze.json',c['freeze'])
j=read(d/'post-recovery/journal/stage17-state-journal-000010.json');old=read(d/'pre-recovery/journal/stage17-state-journal-000009.json')
assert j['resolution_records'][:-1]==old['resolution_records'] and j['transition_records']==old['transition_records']
assert j['resolution_records'][-1]['sha256']==c['resolution']['sha256'] and j['journal_sequence_number']==10
r=read(d/'post-recovery/records/resolution-007-s17-ext-007.json');receipt=read(d/'post-recovery/receipts/d308-ext007-descriptive-freeze-1.json')
assert r['input_id']=='S17-EXT-007' and len(r['evidence'])==1
assert r['evidence'][0]['receipt_sha256']==c['custody_receipt']['sha256']
assert receipt['artifact_sha256']==c['manifest']['sha256'] and receipt['artifact_locator']==c['manifest']['path']
move=read(d/'post-recovery/d309-ext007-final-replay-1/relocation.json')
assert (d/'pre-recovery/journal/d308-scoped-admission-preview.json').read_bytes()==(d/'post-recovery/d309-ext007-final-replay-1/preserved-preview.json').read_bytes()
assert move['sha256']=='3dfcbdfb3efdf7b5d9c26ad5b8cc32dcd672473e1088bb288ae652e63da7d935' and move['canonical_journal_modified'] is False
intent=read(d/'post-recovery/d309-ext007-final-replay-1/relocation-intent.json')
checked(root/'tools/finalize_stage17_descriptive_admission_v1.py',intent['source_code'])
packet=read(d/'post-recovery/d309-final-replay-packet-1/manifest.json')
assert packet==read(d/'recovery-packet-manifest.json') and packet['source_revision']=='50528ea99f6681c618acffcf3f6b2337d1697823'
assert packet['files'][0]['sha256']==intent['source_code']['sha256']
assert len(c['resolved_inputs'])==7 and c['unresolved_inputs']==['S17-EXT-008','S17-EXT-009','S17-EXT-010']
for key in ('pilot_ready','stage17_complete','phase18_authority','raw_decoding_repeated','new_qualification','new_resolution_appended','canonical_journal_modified'):assert c[key] is False
assert c['new_measurements']==0 and c['calibration_scope']=='STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY'
manifest=read(d/'manifest.json');assert len({v['path'] for v in manifest['files']})==len(manifest['files'])
for b in manifest['files']:checked(d/b['path'],b)
print(json.dumps(dict(status='PASS',checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),checked_public_artifacts=len(manifest['files']),actual_policy_matches_local_source=True,original_journal_prefix_preserved=True,canonical_receipt_manifest_joins_verified=True,preview_custody_preserved=True,recovery_source_matches_committed_source=True,pilot_ready=False,stage17_complete=False,phase18_authority=False),sort_keys=True,indent=2))
