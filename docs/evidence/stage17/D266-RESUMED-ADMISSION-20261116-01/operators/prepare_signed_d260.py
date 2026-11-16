"""One-shot D260 namespace, registration and signed authority; never executes Q16."""
import argparse,copy,dataclasses,datetime,hashlib,json,os,pathlib,subprocess,sys,time,types
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27');O=E/'d265-admission-preparation-2';P=E/'d260-configuration-2';OP=pathlib.Path(__file__).resolve().parent
PROGRAM=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1'
def require(ok,message):
 if not ok:raise ValueError(message)
def read(b):
 p=pathlib.Path(b['path']);require(p.is_absolute() and all(not q.is_symlink() for q in (p,*p.parents)),'nonsymlink binding');raw=p.read_bytes();require(len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'],'changed binding');return raw
def binding(p):
 raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def save(p,v):
 raw=v if type(v) is bytes else json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);return binding(p)
def main(a):
 require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
 c=json.loads(read(dict(path=str(a.config),size_bytes=a.config.stat().st_size,sha256=a.config_sha256)))
 for b in c['files'].values():read(b)
 w=json.loads(read(c['files']['window']));require(time.monotonic_ns()<w['last_safe_collection_start_ns'],'original safe start expired')
 built=json.loads(read(c['files']['constructed']));approved=json.loads(read(c['files']['input_admission']));require(approved['status']=='ALL_SOURCE_PREFIX_COMPATIBILITY_GATES_PASS' and approved['plan']==built['plan'],'prior actual admission required')
 wrapper=types.ModuleType('d260_cli');wrapper.__file__=c['files']['cli_wrapper']['path'];exec(compile(read(c['files']['cli_wrapper']),wrapper.__file__,'exec'),wrapper.__dict__)
 cli,cfg=wrapper.configure(pathlib.Path(built['cli_configuration']['path']),built['cli_configuration']['sha256']);loader=sys.modules['stage17_service_continuation_packet_v2']
 plan=loader.strict_json(loader.read(built['plan']));planid=built['plan']['sha256'];extent=cli.controller.contract.validate_plan('Q16b',plan);require(len(extent.captures)==103 and extent.required_watchdog_ns==55860*10**9,'exact103')
 local=json.loads(read(c['files']['local_audit']));require(local['status']=='PASS_SCOPED_HISTORY_AUDIT' and local['plan_sha256']==planid and not local['errors'] and not local['matches'],'local namespace audit')
 import stage17_service_continuation_namespace_v1 as namespaces
 audit=namespaces.audit('stand',E.parent,namespaces.Matcher(plan,loader.read(plan['continuation']['parent_plan'])))
 save(O/'stand-namespace-audit.json',audit);require(audit['status']=='PASS_SCOPED_HISTORY_AUDIT' and not audit['errors'] and not audit['matches'],'stand namespace audit')
 executor=cli.controller.make_executor();storage=plan['storage'];limits=executor.custody_limits(storage,min(w['last_safe_collection_start_ns'],time.monotonic_ns()+120*10**9))
 expected=set(namespaces.base.FAMILIES)|{namespaces.contract.PARENT_SHA256}
 with executor.custody.ProgramStore(PROGRAM,scope_sha256=storage['program_scope_sha256'],family_id=planid,limits=limits) as store:
  require(set(store._families)==expected and not store._capture_pending and all(s['kind']=='RELEASED' for s in store._states.values()),'exact quiescent five-family history')
  before=copy.deepcopy(store._families);tip=dataclasses.asdict(store.ledger_binding());require(tip['file_name']=='0000000000060699.json' and tip['sha256']=='9c830228849b2ed62683319eebda44b58e31c70fc46f664a3d2f427c5cf426d6','original completed custody ledger changed')
  require(not (PROGRAM/'working'/planid).exists(),'already registered; no retry');store.prepare_family(planid)
  require(set(store._families)==expected|{planid} and all(store._families[k]==v for k,v in before.items()),'old families modified')
  after=dataclasses.asdict(store.ledger_binding());require(after['file_name']=='0000000000060700.json','exactly one append')
 save(O/'family-registration.json',dict(before=tip,after=after,new_family_id=planid,old_family_count=5,execution_authority=False))
 root=E/'admission-root';authroot=root/'evidence/formal-q16b-d260-1';authroot.mkdir(mode=0o700);phase=PROGRAM/'working'/planid
 common=dict(repository_root=root,evidence_root=E,pilot_archive=pathlib.Path(cfg['archive']['path']),pilot_sidecar=pathlib.Path(cfg['sidecar']['path']))
 req=cli.author_formal_request(**common,action_id='Q16b',action_inputs_path=pathlib.Path(built['action_inputs']['path']),request_id='CPU-PREFETCH-V5-D260-Q16B-REQUEST-1',authorization_id='CPU-PREFETCH-V5-D260-Q16B-AUTH-1',attempt_id='CPU-PREFETCH-V5-D260-Q16B-ATTEMPT-1',session_id='CPU-PREFETCH-V5-D260-Q16B-SESSION-1',output_root=phase,destination=authroot/'request.json')
 now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0);issued=now.isoformat().replace('+00:00','Z');expires=(now+datetime.timedelta(seconds=55860)).isoformat().replace('+00:00','Z')
 auth=cli.author_formal_authorization(**common,request_path=req,actor='maltsev.oiu@phystech.edu',reviewer='OWNER',issued_at_utc=issued,expires_at_utc=expires,destination=authroot/'authorization.json')
 sign=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(auth)],stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
 save(O/'signing-result.json',dict(exit_code=sign.returncode,stdout=sign.stdout.decode(errors='replace'),stderr=sign.stderr.decode(errors='replace')));require(sign.returncode==0,'signing failed')
 sig=pathlib.Path(str(auth)+'.sig');journal=cli.base.latest_journal(E)
 cli.verify_formal_signature(repository_root=root,journal=journal,journal_directory=E/'journal',operational_evidence_root=E,authorization_path=auth,signature_path=sig,pilot_archive=common['pilot_archive'],pilot_sidecar=common['pilot_sidecar'])
 limits=save(O/'owner-limits.json',dict(address_space_bytes=max(x['execution_budget']['memory_bytes'] for x in plan['captures']),memlock_bytes=max(x['resources']['total_mapping_bytes'] for x in plan['captures'])))
 inputs=json.loads(read(built['action_inputs']));hardware=save(O/'hardware-control.json',inputs['hardware_control'])
 wrappers=dict(cli=c['files']['cli_wrapper'],owner_check=c['files']['owner_check'],analysis=c['files']['analysis'])
 analysis=dict(schema_version='software-d260-offline-analysis/1',repository_root=str(root),evidence_root=str(E),analysis_root=str(E/'d260-analysis-1'),boot_id=c['boot_id'],canonical_capture_bytes=storage['analysis_capture_workspace_bytes'],archive=cfg['archive']['path'],sidecar=cfg['sidecar']['path'],operator_sha256=c['files']['analysis']['sha256'],files=dict(request=binding(req),authorization=binding(auth),signature=binding(sig),journal=binding(journal),cli_wrapper=c['files']['cli_wrapper'],cli_configuration=built['cli_configuration'],composition=c['files']['composition'],reader=c['files']['reader']),execution_authority=False)
 ab=save(O/'analysis-configuration.json',analysis)
 v=cli._validation(root,E,common['pilot_archive'],common['pilot_sidecar']);release=v.resolutions['S17-EXT-006'].semantic_context
 prepared=dict(schema_version='software-d254-prepared-phase/1',source_revision=release['source_revision'],boot_id=c['boot_id'],repository_root=str(root),evidence_root=str(E),output_root=str(phase),worker=dict(path=release['release_artifact_path'],size_bytes=release['release_artifact_size_bytes'],sha256=release['release_artifact_sha256']),files=dict(request=binding(req),authorization=binding(auth),signature=binding(sig),plan=built['plan'],cli_configuration=built['cli_configuration'],analysis_config=ab,limits=limits,hardware_control=hardware),wrappers=wrappers,execution_authority=False,phase18_authority=False)
 save(O/'prepared-phase.json',prepared);loader.check_loaded();require(time.monotonic_ns()<w['last_safe_collection_start_ns'],'safe start expired after preparation')
 print(json.dumps(dict(status='103_PREPARED_SIGNED_NOT_EXECUTED',prepared=binding(O/'prepared-phase.json'),source_revision=release['source_revision'],execution_authority=False)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--config-sha256',required=True);main(p.parse_args())
