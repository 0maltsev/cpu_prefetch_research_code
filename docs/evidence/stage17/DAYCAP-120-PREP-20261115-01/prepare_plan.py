"""Prospective 120-capture declaration from verified layouts; no authority."""
import argparse,copy,hashlib,hmac,json,pathlib,secrets,sys,subprocess
ROOT=pathlib.Path.cwd();sys.path.insert(0,str(ROOT/'tools'))
import stage17_formal_service_daycap_v1 as daycap
import stage17_archive_canonical_fast_v1 as canonical
p=argparse.ArgumentParser();p.add_argument('--source-revision',required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--reuse-seed-json',type=pathlib.Path);a=p.parse_args()
assert len(a.source_revision)==40 and set(a.source_revision)<=set('0123456789abcdef')
subprocess.run(['git','cat-file','-e',a.source_revision+'^{commit}'],check=True)
assert len(a.profile_sha256)==64 and set(a.profile_sha256)<=set('0123456789abcdef')
source=ROOT/'build/stage17-archive-optimization/restart-prep/restart-candidate-3/plan.json';raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()=='6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
old=json.loads(raw);plan=copy.deepcopy({k:v for k,v in old.items() if k!='captures'})
a.output.mkdir(parents=True,exist_ok=False)
master=(bytes.fromhex(json.loads(a.reuse_seed_json.read_bytes())['master_seed_hex']) if a.reuse_seed_json else secrets.token_bytes(32));assert len(master)==32;(a.output/'public-experiment-seed.json').write_text(json.dumps({'purpose':'Public prospective experimental randomization; not an authentication credential','master_seed_hex':master.hex()},indent=2)+'\n')
def seed(label):return hmac.new(master,label.encode(),hashlib.sha256).hexdigest()
plan.update(schema_version=daycap.VERSION,method_id=daycap.METHOD,plan_id='CPU-PREFETCH-V5-D254-Q16B-DAYCAP-1',source_revision=a.source_revision,repetitions_per_cell=2,warmup_namespace='CPU-PREFETCH-V5-D254-Q16B-WARMUP-1',measurement_namespace='CPU-PREFETCH-V5-D254-Q16B-MEASUREMENT-1')
plan['storage']['implementation_profile_sha256']=a.profile_sha256;plan['storage']['per_capture_archive_ns']=240_000_000_000
entries=[];proof=[]
for position in range(60):
 for repetition in range(2):
  old_ordinal=position*59+repetition;ordinal=position*2+repetition
  entry=copy.deepcopy(old['captures'][old_ordinal]);cap=entry['capture']
  for part in ('capture','resources','monitoring'):entry[part]['ordinal']=ordinal
  cap['repetition_ordinal']=repetition
  for phase,tag in (('warmup','W'),('measurement','M')):
   cap[phase]=dict(namespace_id=plan[phase+'_namespace'],run_id=f'B27{tag}{ordinal:08d}',seed_hex=seed(phase+':'+str(ordinal)),seed_id=plan[phase+'_namespace']+f'-SEED-{ordinal:04d}')
  cap['arena_seed']=copy.deepcopy(cap['measurement'])
  if cap['linked_order'] is not None:
   cap['linked_order'].update(namespace_id='CPU-PREFETCH-V5-D254-Q16B-NODE-ORDER-1',seed_hex=seed('node:'+str(ordinal)),seed_id=f'CPU-PREFETCH-V5-D254-Q16B-NODE-SEED-{ordinal:04d}')
  budget=entry['execution_budget'];budget.update(setup_ns=120_000_000_000,publication_ns=90_000_000_000,cleanup_ns=24_000_000_000,watchdog_ns=300_000_000_000)
  assert all(b['drain_ns']==30_000_000_000 for b in cap['budget']['phases'])
  for part in ('resources','monitoring'):
   before={k:v for k,v in old['captures'][old_ordinal][part].items() if k!='ordinal'};after={k:v for k,v in entry[part].items() if k!='ordinal'};assert before==after
  assert cap['geometry']==old['captures'][old_ordinal]['capture']['geometry'] and cap['budget']==old['captures'][old_ordinal]['capture']['budget']
  assert len(cap['warmup']['run_id'])==len(old['captures'][old_ordinal]['capture']['warmup']['run_id'])==12
  entries.append(entry);proof.append(dict(ordinal=ordinal,source_ordinal=old_ordinal,cell_ordinal=cap['cell_ordinal'],repetition=repetition,actual_layout_and_phase_limits_unchanged=True))
plan['captures']=entries
b=plan['budget'];b['watchdog_ns']=b['setup_ns']+b['cleanup_ns']+sum(e['execution_budget']['watchdog_ns'] for e in entries)+len(entries)*plan['storage']['per_capture_archive_ns'];b['max_output_bytes']=b['metadata_output_bytes']+sum(e['execution_budget']['max_output_bytes'] for e in entries)
extent=daycap.validate_plan(plan);data=canonical.canonical(plan);(a.output/'plan.json').write_bytes(data)
assert len(entries)==120 and len({e['capture']['cell_ordinal'] for e in entries})==60
record=dict(schema_version='software-d254-prospective-plan-proof/1',execution_authority=False,status='DRAFT_REQUIRES_ACTUAL_SOURCE_PROFILE_QUALIFICATION_AND_NAMESPACE_ADMISSION',source_template_sha256=hashlib.sha256(raw).hexdigest(),plan_sha256=hashlib.sha256(data).hexdigest(),size_bytes=len(data),source_revision=a.source_revision,profile_sha256=a.profile_sha256,method_id=daycap.METHOD,collector_method_id=daycap.COLLECTOR_METHOD,captures=120,cells=60,repetitions=2,measurement_ns=1_000_000_000,warmup_ns=5_000_000_000,collection_watchdog_ns=b['watchdog_ns'],independent_validation=dict(workers=8,worker_as_bytes=16*1024**3,codec_as_bytes=2*1024**3,per_job_wall_seconds=900,waves=15,maximum_wall_seconds=13500,canonical_workspace_bytes=plan['storage']['analysis_capture_workspace_bytes']*8,scratch_quota_bytes=256*1024**3,aggregate_memory_with_reserves_bytes=164*1024**3),qualification_and_admission_ceiling_seconds=3600,report_and_cleanup_ceiling_seconds=1800,aggregate_ceiling_seconds=b['watchdog_ns']//1_000_000_000+13500+3600+1800,absolute_study_seconds=86400,work_cutoff_seconds=84600,cleanup_reserve_seconds=1800,entries=proof)
assert record['aggregate_ceiling_seconds']<=record['work_cutoff_seconds'] and record['independent_validation']['canonical_workspace_bytes']+17*1024**3<=256*1024**3
(a.output/'preparation-proof.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('entries','independent_validation')},indent=2))
