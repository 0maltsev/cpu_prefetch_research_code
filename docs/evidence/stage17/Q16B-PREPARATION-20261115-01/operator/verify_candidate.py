"""Independent native declared-input and fixed-design candidate checks."""
import hashlib,json,pathlib,subprocess,tempfile
R=pathlib.Path.cwd();C=R/'build/stage17-step6-q16b-prep/candidate-2';old=R/'build/stage17-step6-q16b-prep/candidate-1'
p=json.loads((C/'plan.json').read_bytes());first=json.loads((old/'plan.json').read_bytes())
assert len(p['captures'])==3540 and p['measurement_ns']==1000000000 and p['repetitions_per_cell']==59
assert p['captures']==first['captures']
assert (C/'identities.json').read_bytes()==(old/'identities.json').read_bytes()
assert p['storage']['archive_staging_bytes']>=first['storage']['archive_staging_bytes']
assert {k:v for k,v in p.items() if k!='storage'}=={k:v for k,v in first.items() if k!='storage'}
hardware=json.loads((C/'preparation.json').read_bytes())['hardware_control']
prestate=[dict(cpu=r['cpu'],value=int(r['complete_value_hex'],16)) for r in hardware['prestate']]
exe=R/'build/stage17-step6-q16b-prep/native-sizing/release/service-layout';seen=set();numeric=set();node=[]
for i,row in enumerate(p['captures']):
 c=row['capture'];assert c['ordinal']==i and c['repetition_ordinal']==i%59
 assert c['warmup_ns']==5000000000 and c['measurement_ns']==1000000000
 for phase in ('warmup','measurement'):
  v=c[phase]
  for key in ('run_id','seed_id'):
   assert v[key] not in seen;seen.add(v[key])
  assert v['seed_hex'] not in numeric;numeric.add(v['seed_hex'])
 if c['linked_order'] is not None:
  v=c['linked_order'];assert v['seed_id'] not in seen and v['seed_hex'] not in numeric
  seen.add(v['seed_id']);numeric.add(v['seed_hex']);node.append(v)
assert len(node)==1416 and len(numeric)==8496
results=[]
with tempfile.TemporaryDirectory() as temp:
 for ordinal in range(0,3540,59):
  row=p['captures'][ordinal];d={k:row[k] for k in ('capture','resources','monitoring')};d['hardware_prestate']=prestate
  path=pathlib.Path(temp)/'input.json';path.write_text(json.dumps(d))
  result=subprocess.run([str(exe),'--verify-declared',str(path)],capture_output=True,timeout=35,check=True)
  answer=json.loads(result.stdout);assert answer['layout']=={k:row['resources'][k] for k in answer['layout']}
  assert answer['source_revision']==p['source_revision'] and answer['declared_layout_rechecked'] is True
  results.append(dict(cell_ordinal=row['capture']['cell_ordinal'],declared_native_layout_verified=True))
summary=dict(status='FIXED_DESIGN_AND_ALL60_DECLARED_NATIVE_LAYOUTS_VERIFIED',plan_sha256=hashlib.sha256((C/'plan.json').read_bytes()).hexdigest(),captures=3540,unique_phase_run_ids=7080,unique_phase_and_linked_numeric_seeds=8496,linked_order_identities=1416,preserved_prior_candidate_identities=True,changes_from_candidate1='archive staging upper bound only',native_cells=results,historical_namespace_audit=False,measurements_performed=False,execution_authority=False)
output=R/'build/stage17-step6-q16b-prep/verification/candidate-2-independent.json';output.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='native_cells'}))
