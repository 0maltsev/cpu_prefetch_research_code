"""One create-exclusive D254 collection admission; no experimental execution."""
import argparse,copy,dataclasses,datetime,hashlib,importlib.util,json,os,pathlib,subprocess,sys,time,types
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26')
PROGRAM=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1'
SOURCE='aa3285f15acbd3314cae64a628c113488a8438b8'
PLAN='53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486'
FAMILIES={'a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7','91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2','ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702','6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'}
def require(v,m):
 if not v:raise ValueError(m)
def read(b):
 p=pathlib.Path(b['path']);require(p.is_absolute() and all(not x.is_symlink() for x in (p,*p.parents)),'nonsymlink binding')
 with p.open('rb') as f:
  before=os.fstat(f.fileno());require(0<before.st_size==b['size_bytes']<=128*1024**2,'bounded input');raw=f.read(before.st_size+1);after=os.fstat(f.fileno())
 stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 require(stamp(before)==stamp(after)==stamp(p.stat()) and len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==b['sha256'],'bound bytes changed');return raw
def load_module(name,b):
 require(name not in sys.modules,'unverified cached module');m=types.ModuleType(name);m.__file__=b['path'];sys.modules[name]=m;exec(compile(read(b),m.__file__,'exec'),m.__dict__);return m
def utc():return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def main(a):
 if os.geteuid()==0:
  argv=['/usr/bin/setpriv','--reuid=1000','--regid=1000','--clear-groups','--inh-caps=+sys_ptrace','--ambient-caps=+sys_ptrace','--',sys.executable,'-B',str(pathlib.Path(__file__).resolve()),*sys.argv[1:]];os.execv(argv[0],argv)
 require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
 cfg=json.loads(read(dict(path=str(a.config),size_bytes=a.config.stat().st_size,sha256=a.config_sha256)))
 require(cfg['schema_version']=='software-d254-collection-preparation/1' and cfg['native_source_revision']==SOURCE and cfg['execution_authority'] is False,'preparation config')
 require(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==cfg['boot_id'],'same actual boot')
 deadline=a.global_deadline_ns
 def remaining():
  value=(deadline-time.monotonic_ns())/1e9;require(value>0,'qualification/preparation deadline');return value
 for b in cfg['files'].values():read(b)
 root=E/'admission-root';sys.path.insert(0,str(root/'tools'));sys.path.insert(1,str(pathlib.Path(cfg['packet_root'])))
 # Authenticate all immutable qualified source bytes before project imports.
 policy=json.loads(read(cfg['files']['policy']))
 for group in ('bindings','runtime_closure'):
  for b in policy[group].values():read(dict(b,path=str(root/b['path'])))
 loader=load_module('bound_d257_administration_loader',cfg['files']['administration_loader']);cli=loader.load(dict(administration=cfg['files']['administration'],administration_manifest=cfg['files']['administration_manifest']),read);cli.activate()
 validation=cli._validation(root,E,pathlib.Path(cfg['archive']['path']),pathlib.Path(cfg['sidecar']['path']))
 require({'S17-EXT-004','S17-EXT-005','S17-EXT-006'}<=set(validation.resolutions),'actual fresh Q15 qualification required')
 new=validation.resolutions['S17-EXT-006'].semantic_context
 require(new['source_revision']==SOURCE and new['release_artifact_sha256']==cfg['native_worker_sha256'],'actual new qualified native')
 helper=load_module('daycap_inputs',cfg['files']['inputs_helper']);write,binding=helper.write,helper.bound
 out=E/'daycap-collection-preparation-1';prefix=load_module('bound_d257_unsigned_preparation_prefix',cfg['files']['prefix_helper']);write=prefix.adopt(cfg['files']['preparation_prefix'],read,write,helper.canonical,out,pathlib.Path(cfg['packet_root']))
 plan_raw=read(cfg['files']['plan']);require(hashlib.sha256(plan_raw).hexdigest()==PLAN,'exact approved120 plan');plan=json.loads(plan_raw);plan_binding=write(out/'plan.json',plan_raw)
 extent=cli.controller.contract.validate_plan('Q16b',plan);require(len(plan['captures'])==120 and extent.declared.watchdog_ns==65040*10**9,'approved family budget')
 context=json.loads(read(cfg['files']['original_context']))
 proof=helper.compatibility(cfg,context,new,out/'plan.json',E/'ext004-authoring-records-1/platform-manifest.json')
 packet=pathlib.Path(cfg['packet_root']);compat=write(packet/'q16a-compatibility.json',proof)
 historical=write(packet/'historical-inputs.json',dict(schema_version='cpu-prefetch-stage17-daycap-historical-inputs/1',historical_context=cfg['files']['original_context'],original_plan=cfg['original_plan'],compatibility=compat,boot_id=cfg['boot_id'],execution_authority=False,phase18_authority=False))
 import stage17_archive_daycap_overlay_v1 as overlay
 overlay.configure_verified_descriptor(read(cfg['files']['overlay']),packet)
 cli.controller.configure_historical_inputs(json.loads(read(historical)),packet)
 q4=validation.resolutions['S17-EXT-004'].semantic_context;q5=validation.resolutions['S17-EXT-005'].semantic_context['q15_w']
 hardware=dict(mapping_id=q4['hardware_mapping']['mapping_id'],q15_w_result_sha256=q5['result_sha256'],prestate=q5['request']['action_inputs']['prestate'])
 namespace=dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1',plan_sha256=PLAN,stand_id=plan['stand_id'],phase_identities=[x['capture'][phase] for x in plan['captures'] for phase in ('warmup','measurement')],schedule_namespaces=[],execution_authority=False)
 ns=write(out/'namespace_registry.json',namespace);prerequisites={**cfg['prerequisites'],'namespace_registry':ns}
 inputs=dict(plan=plan,hardware_control=hardware,prerequisite_bindings=prerequisites)
 # Every qualification/scientific/profile/namespace gate precedes registration.
 cli.controller.validate_action_inputs(dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',action_id='Q16b',stand_id=plan['stand_id'],action_inputs=inputs),validation)
 inputs_binding=write(out/'action-inputs.json',inputs)
 # Global finite public history audit, all existing experiments retained.
 local=json.loads(read(cfg['files']['local_audit']));require(local['status']=='PASS_SCOPED_HISTORY_AUDIT' and not local['errors'] and not local['matches'],'local namespace audit')
 command=[sys.executable,'-B',cfg['files']['audit_helper']['path'],'--repository-root',str(root),'--plan',str(out/'plan.json'),'--identities',cfg['files']['planned_identities']['path'],'--identities-sha256',cfg['files']['planned_identities']['sha256'],'--mode','stand','--base',str(E.parent),'--wall-seconds','300']
 result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=min(300,remaining()),check=False)
 write(out/'stand-namespace-audit-2.stderr',result.stderr if result.stderr else b'\n');audit=json.loads(result.stdout);write(out/'stand-namespace-audit-2.json',audit)
 require(result.returncode==0 and audit['status']=='PASS_SCOPED_HISTORY_AUDIT' and not audit['matches'] and not audit['errors'],'stand namespace audit failed')
 # Register once against the exact retained shared ledger; never initialize it.
 executor=cli.controller.make_executor();storage=plan['storage'];limits=executor.custody_limits(storage,min(deadline,time.monotonic_ns()+120*10**9))
 with executor.custody.ProgramStore(PROGRAM,scope_sha256=storage['program_scope_sha256'],family_id=PLAN,limits=limits) as store:
  require(set(store._families)==FAMILIES and not store._capture_pending and all(s['kind']=='RELEASED' for s in store._states.values()),'exact quiescent four-family history')
  before=copy.deepcopy(store._families);tip=dataclasses.asdict(store.ledger_binding());require(tip['file_name']=='0000000000059746.json' and tip['sha256']=='3b3198273f0b2d2ad49aa46980b0de42ea269d8722dec2593c7bd98781ac852c','original ledger changed')
  require(not (PROGRAM/'working'/PLAN).exists(),'family already registered; no retry');store.prepare_family(PLAN)
  require(set(store._families)==FAMILIES|{PLAN} and {k:store._families[k] for k in FAMILIES}==before,'registration modified old history')
  after=dataclasses.asdict(store.ledger_binding());require(after['file_name']=='0000000000059747.json','exactly one FAMILY append required')
  record=json.loads((PROGRAM/'ledger'/after['file_name']).read_bytes());require(record['kind']=='FAMILY' and record['previous_sha256']==tip['sha256'] and record['sequence']==59747 and record['payload']==store._families[PLAN],'single append lineage')
 write(out/'family-registration.json',dict(before=tip,after=after,old_families=before,new_family_id=PLAN,execution_authority=False))
 cli_cfg=dict(schema_version='software-d254-qualified-cli-configuration/1',repository_root=str(root),packet_root=str(packet),policy=cfg['files']['policy'],overlay=cfg['files']['overlay'],administration=cfg['files']['administration'],administration_manifest=cfg['files']['administration_manifest'],administration_loader=cfg['files']['administration_loader'],historical_inputs=historical,archive=cfg['archive'],sidecar=cfg['sidecar'],boot_id=cfg['boot_id'],execution_authority=False)
 cli_binding=write(packet/'cli-configuration.json',cli_cfg)
 authroot=root/'evidence/formal-q16b-daycap-1';authroot.mkdir(mode=0o700);phase=PROGRAM/'working'/PLAN
 common=dict(repository_root=root,evidence_root=E,pilot_archive=pathlib.Path(cfg['archive']['path']),pilot_sidecar=pathlib.Path(cfg['sidecar']['path']))
 request=cli.author_formal_request(**common,action_id='Q16b',action_inputs_path=pathlib.Path(inputs_binding['path']),request_id='CPU-PREFETCH-V5-D254-Q16B-REQUEST-1',authorization_id='CPU-PREFETCH-V5-D254-Q16B-AUTH-1',attempt_id='CPU-PREFETCH-V5-D254-Q16B-ATTEMPT-1',session_id='CPU-PREFETCH-V5-D254-Q16B-SESSION-1',output_root=phase,destination=authroot/'request.json')
 issued=utc();expires=(datetime.datetime.fromisoformat(issued.replace('Z','+00:00'))+datetime.timedelta(seconds=65040)).isoformat().replace('+00:00','Z')
 authorization=cli.author_formal_authorization(**common,request_path=request,actor='maltsev.oiu@phystech.edu',reviewer='OWNER',issued_at_utc=issued,expires_at_utc=expires,destination=authroot/'authorization.json')
 sign=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(authorization)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=min(30,remaining()),check=False)
 write(out/'signing-result.json',dict(exit_code=sign.returncode,stdout=sign.stdout.decode(errors='replace'),stderr=sign.stderr.decode(errors='replace')));require(sign.returncode==0,'owner signing failed')
 signature=pathlib.Path(str(authorization)+'.sig');latest=cli.base.latest_journal(E)
 cli.verify_formal_signature(repository_root=root,journal=latest,journal_directory=E/'journal',operational_evidence_root=E,authorization_path=authorization,signature_path=signature,pilot_archive=common['pilot_archive'],pilot_sidecar=common['pilot_sidecar'])
 ownerlimits=write(out/'owner-limits.json',dict(address_space_bytes=max(x['execution_budget']['memory_bytes'] for x in plan['captures']),memlock_bytes=max(x['resources']['total_mapping_bytes'] for x in plan['captures'])))
 hardware_binding=write(out/'hardware-control.json',hardware)
 analysis=dict(schema_version='software-d254-offline-analysis/1',repository_root=str(root),evidence_root=str(E),analysis_root=str(E/'daycap-analysis-1'),boot_id=cfg['boot_id'],canonical_capture_bytes=storage['analysis_capture_workspace_bytes'],archive=cfg['archive']['path'],sidecar=cfg['sidecar']['path'],operator_sha256=cfg['wrappers']['analysis']['sha256'],files=dict(request=binding(request),authorization=binding(authorization),signature=binding(signature),journal=binding(latest),cli_wrapper=cfg['wrappers']['cli'],cli_configuration=cli_binding,overlay=cfg['files']['overlay'],historical_inputs=historical),execution_authority=False)
 analysis_binding=write(out/'analysis-configuration.json',analysis)
 prepared=dict(schema_version='software-d254-prepared-phase/1',source_revision=SOURCE,boot_id=cfg['boot_id'],repository_root=str(root),evidence_root=str(E),output_root=str(phase),worker=dict(path=new['release_artifact_path'],size_bytes=new['release_artifact_size_bytes'],sha256=new['release_artifact_sha256']),files=dict(request=binding(request),authorization=binding(authorization),signature=binding(signature),plan=plan_binding,cli_configuration=cli_binding,analysis_config=analysis_binding,limits=ownerlimits,hardware_control=hardware_binding),wrappers=cfg['wrappers'],execution_authority=False,phase18_authority=False)
 write(out/'prepared-phase.json',prepared);print(json.dumps(dict(status='PREPARED_SIGNED_NOT_EXECUTED',captures=120,plan_sha256=PLAN,execution_authority=False)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--global-deadline-ns',type=int,required=True);main(p.parse_args())
