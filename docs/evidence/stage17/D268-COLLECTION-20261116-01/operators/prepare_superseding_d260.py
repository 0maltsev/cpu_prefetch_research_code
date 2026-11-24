"""Replace only a verified unused D260 authority/declaration; no measurements."""
import argparse,copy,dataclasses,datetime,json,os,pathlib,subprocess,sys,time,types
import prepare_signed_d260 as util
require,read,binding,save=util.require,util.read,util.binding,util.save
E=util.E;O=E/'d267-admission-preparation-3';OLD=E/'d265-admission-preparation-2';PROGRAM=util.PROGRAM

def main(a):
 require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
 c=json.loads(read(dict(path=str(a.config),size_bytes=a.config.stat().st_size,sha256=a.config_sha256)))
 for b in c['files'].values():read(b)
 window=json.loads(read(c['files']['window']));require(time.monotonic_ns()<window['deadline_monotonic_ns']-(56460+13500+1800)*10**9,'tightened safe start expired')
 old=json.loads(read(c['files']['old_prepared']));new=json.loads(read(c['files']['constructed']));oldplan=json.loads(read(old['files']['plan']));plan=json.loads(read(new['plan']))
 require(old['files']['plan']['sha256']=='d980ed9417ddf76e88931d849a62573971522b10604975c51f5fa709335698f4' and new['plan']['sha256']=='1ccafebafafea4b8491b4daf5b70f1065d1ea2c0b854d662bae388bfb031b2ba','exact unused declarations')
 compare=copy.deepcopy(plan);compare['budget']['watchdog_ns']=oldplan['budget']['watchdog_ns'];require(compare==oldplan and plan['budget']['watchdog_ns']==57600*10**9,'only permitted family watchdog changes')
 for b in (*old['files'].values(),*old['wrappers'].values()):read(b)
 oldreq=json.loads(read(old['files']['request']));require(oldreq['action_inputs']['plan']==oldplan,'original signed source')
 state=dict(line.split('=',1) for line in subprocess.run(['systemctl','show','cpu-prefetch-d266-v27-signing-preparation-1.service','-p','MainPID','-p','Result','-p','ExecMainStatus'],check=True,capture_output=True,text=True).stdout.splitlines())
 require(state==dict(MainPID='0',Result='success',ExecMainStatus='0'),'original signed preparation must have completed successfully')
 oldphase=pathlib.Path(old['output_root']);require(oldphase.is_dir() and not list(oldphase.iterdir()),'original family not empty/unused')
 require(json.loads(read(c['files']['old_signing']))['exit_code']==0,'original signature success')
 local=json.loads(read(c['files']['local_audit']));stand=json.loads(read(c['files']['stand_audit']))
 for audit in (local,stand):require(audit['status']=='PASS_SCOPED_HISTORY_AUDIT' and not audit['errors'] and not audit['matches'] and audit['plan_sha256']==old['files']['plan']['sha256'],'original actual zero-collision audit')
 # Equality of the complete capture trees proves identical run/seed identities,
 # sample geometry and all native/per-capture controls, not just matching counts.
 require(plan['captures']==oldplan['captures'] and len(plan['captures'])==103,'identical audited capture identity trees')
 wrapper=types.ModuleType('d260_cli');wrapper.__file__=c['files']['cli_wrapper']['path'];exec(compile(read(c['files']['cli_wrapper']),wrapper.__file__,'exec'),wrapper.__dict__)
 cli,cfg=wrapper.configure(pathlib.Path(new['cli_configuration']['path']),new['cli_configuration']['sha256']);loader=sys.modules['stage17_service_continuation_packet_v3']
 extent=cli.controller.contract.validate_plan('Q16b',plan);require(extent.required_watchdog_ns==55860*10**9 and cli.controller.deadline_policy(extent)['session_max_wall_seconds']==57600,'unchanged original policy matches native declaration')
 import stage17_service_continuation_namespace_v1 as namespaces
 oldids=namespaces.planned_identities(oldplan);newids=namespaces.planned_identities(plan)
 for k in ('phase_identities','linked_order_identities','schedule_namespaces'):require(oldids[k]==newids[k],'exact audited identities '+k)
 require(binding(cli.base.latest_journal(E))==json.loads(read(c['files']['old_constructed']))['original_journal'],'qualification journal changed since original audit')
 executor=cli.controller.make_executor();storage=plan['storage'];limits=executor.custody_limits(storage,min(window['deadline_monotonic_ns'],time.monotonic_ns()+120*10**9));newid=new['plan']['sha256'];oldid=old['files']['plan']['sha256']
 original_registration=json.loads(read(c['files']['old_registration']));expected=set(namespaces.base.FAMILIES)|{namespaces.contract.PARENT_SHA256,oldid}
 with executor.custody.ProgramStore(PROGRAM,scope_sha256=storage['program_scope_sha256'],family_id=newid,limits=limits) as store:
  require(set(store._families)==expected and not store._capture_pending and all(s['kind']=='RELEASED' for s in store._states.values()),'exact quiescent six-family history')
  tip=dataclasses.asdict(store.ledger_binding());require(tip==original_registration['after'] and tip['file_name']=='0000000000060700.json','no intervening ledger execution since audited preparation')
  require(not list(oldphase.iterdir()),'old family acquired an attempt');require(not (PROGRAM/'working'/newid).exists(),'new family already registered')
  before=copy.deepcopy(store._families);store.prepare_family(newid);after=dataclasses.asdict(store.ledger_binding());require(after['file_name']=='0000000000060701.json' and set(store._families)==expected|{newid} and all(store._families[k]==v for k,v in before.items()),'exactly one new family append; all history unchanged')
 bridge=dict(schema_version='software-d268-unused-authority-supersession/1',original_prepared=c['files']['old_prepared'],old_request=old['files']['request'],old_authorization=old['files']['authorization'],old_signature=old['files']['signature'],old_plan=old['files']['plan'],new_plan=new['plan'],local_namespace_audit=c['files']['local_audit'],stand_namespace_audit=c['files']['stand_audit'],identical_all103_capture_trees=True,identical_phase_and_linked_identities=True,old_family_observed_empty=True,no_intervening_ledger_records=True,ledger_before=tip,ledger_after=after,qualification_journal=binding(cli.base.latest_journal(E)),superseded_before_native_attempt=True,execution_authority=False)
 save(O/'supersession-intent.json',bridge)
 root=E/'admission-root';authroot=root/'evidence/formal-q16b-d268-2';authroot.mkdir(mode=0o700);phase=PROGRAM/'working'/newid
 common=dict(repository_root=root,evidence_root=E,pilot_archive=pathlib.Path(cfg['archive']['path']),pilot_sidecar=pathlib.Path(cfg['sidecar']['path']))
 req=cli.author_formal_request(**common,action_id='Q16b',action_inputs_path=pathlib.Path(new['action_inputs']['path']),request_id='CPU-PREFETCH-V5-D268-Q16B-REQUEST-2',authorization_id='CPU-PREFETCH-V5-D268-Q16B-AUTH-2',attempt_id='CPU-PREFETCH-V5-D268-Q16B-ATTEMPT-2',session_id='CPU-PREFETCH-V5-D268-Q16B-SESSION-2',output_root=phase,destination=authroot/'request.json')
 now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0);issued=now.isoformat().replace('+00:00','Z');expires=(now+datetime.timedelta(seconds=57600)).isoformat().replace('+00:00','Z')
 auth=cli.author_formal_authorization(**common,request_path=req,actor='maltsev.oiu@phystech.edu',reviewer='OWNER',issued_at_utc=issued,expires_at_utc=expires,destination=authroot/'authorization.json')
 sign=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(auth)],stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
 save(O/'signing-result.json',dict(exit_code=sign.returncode,stdout=sign.stdout.decode(errors='replace'),stderr=sign.stderr.decode(errors='replace')));require(sign.returncode==0,'signing failed')
 sig=pathlib.Path(str(auth)+'.sig');journal=cli.base.latest_journal(E)
 cli.verify_formal_signature(repository_root=root,journal=journal,journal_directory=E/'journal',operational_evidence_root=E,authorization_path=auth,signature_path=sig,pilot_archive=common['pilot_archive'],pilot_sidecar=common['pilot_sidecar'])
 analysis=json.loads(read(old['files']['analysis_config']));analysis['operator_sha256']=c['files']['analysis']['sha256'];analysis['files'].update(request=binding(req),authorization=binding(auth),signature=binding(sig),journal=binding(journal),cli_wrapper=c['files']['cli_wrapper'],cli_configuration=new['cli_configuration'],composition=c['files']['composition'],reader=c['files']['reader']);ab=save(O/'analysis-configuration.json',analysis)
 prepared=copy.deepcopy(old);prepared['output_root']=str(phase);prepared['files'].update(request=binding(req),authorization=binding(auth),signature=binding(sig),plan=new['plan'],cli_configuration=new['cli_configuration'],analysis_config=ab);prepared['wrappers']=dict(cli=c['files']['cli_wrapper'],owner_check=c['files']['owner_check'],analysis=c['files']['analysis'])
 save(O/'prepared-phase.json',prepared);bridge.update(new_request=binding(req),new_authorization=binding(auth),new_signature=binding(sig),new_prepared=binding(O/'prepared-phase.json'));save(O/'authority-supersession-complete.json',bridge)
 loader.check_loaded();require(time.monotonic_ns()<window['deadline_monotonic_ns']-(56460+13500+1800)*10**9,'tightened latest start expired')
 print(json.dumps(dict(status='D268_PREPARED_SIGNED_NOT_EXECUTED',plan=new['plan'],prepared=binding(O/'prepared-phase.json'),execution_authority=False)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--config-sha256',required=True);main(p.parse_args())
