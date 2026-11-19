"""D301 saved-request readiness; the original expired runtime gate stays closed.

Software checks can inspect retained state and render an unsigned draft only.
They always return launch_permitted=false and cannot authorize collection.
"""
import ast
import copy
import datetime as dt
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import time
import types

import stage17_q16c_qualified_continuation_v1 as previous

PARENT_SHA='8336c3d20f367d92cd85d36d0166d6868e0944836acf84562120e7e9dedf172f'
PROPOSAL_SHA='c15148c9a7f716c049c52617e784d1641ed26a630e7f3771bbab7edd5192e82d'
TEMPLATE_SHA='7969af609369c6b6e2bd741f2099931d133ce31fc0afec0f2988378531e1af99'
REQUEST_SHA='38fc71fd8e6a5dc79c95284999fa51b6b42a41d7cdb6477b4886272af931851c'
TIP_SHA='18e4177af33e1bc5e19fdf71bc41bf087632e5ec644df2e30f3764116d588da0'
NATIVE_SOURCE,DEADLINE,ENVELOPE,E=previous.NATIVE_SOURCE,previous.DEADLINE,previous.ENVELOPE,previous.E
ORIGINAL_DEADLINE=DEADLINE
SUPPLEMENT_SHA='29f5dfcf84a2736aade41718a105d811c03e883ca7c0334a22ebd27d9d1f9d8e'
SIGNED_DAY_DEADLINE=1636624784571258
require=previous.require


def validate_supplement(proposal,acceptance):
    require(hashlib.sha256(proposal).hexdigest()==SUPPLEMENT_SHA,'exact D302 supplement')
    expected=dict(decision_id='D302',owner_message='continue',exact_decision_text_approved=True,
        recorded_decision_sha256=SUPPLEMENT_SHA,applies_to_decision='D301',new_execution_windows=0,
        additional_manual_continuations=0,automatic_retry=False,repeat_qualification=False,
        repeat_completed_measurements=False,repeat_completed_raw_validations=False,
        reused_capture_count=86,remaining_capture_count=94,maximum_remaining_seconds=31460,
        original_total_deadline_monotonic_ns=ORIGINAL_DEADLINE,
        admitted_day_deadline_monotonic_ns=SIGNED_DAY_DEADLINE,
        latest_start_monotonic_ns=SIGNED_DAY_DEADLINE-ENVELOPE,phase18_authority=False)
    for key,item in expected.items():
        require(type(acceptance.get(key)) is type(item) and acceptance[key]==item,'exact D302 approval '+key)


def supplement_documents(c):
    import stage17_q16c_continuation_operator_v1 as io
    proof=c['deadline_supplement']
    require(type(proof) is dict and set(proof)=={'proposal','acceptance','signature'},'closed D302 proof')
    proposal=io.read(proof['proposal']);raw=io.read(proof['acceptance'])
    validate_supplement(proposal,json.loads(raw));io.read(proof['signature'])
    return raw,proof


def runtime_deadline(c=None):
    if c is None or 'deadline_supplement' not in c:return ORIGINAL_DEADLINE
    supplement_documents(c)
    return SIGNED_DAY_DEADLINE


def check_time(now,c=None):
    require(type(now) is int and 0<now<runtime_deadline(c)-ENVELOPE,
            'complete31460s envelope must fit inside the admitted original signed day')


def verify_supplement(c,trust):
    if 'deadline_supplement' not in c:return
    from stage17_phase_controller_v2 import _verify_signature
    raw,proof=supplement_documents(c)
    _verify_signature(raw,Path(proof['signature']['path']),trust)


def deadline_utc(c):
    import stage17_q16c_continuation_operator_v1 as io
    record=io.document(c['window_proof']['manifest']);end=runtime_deadline(c)
    if 'deadline_supplement' in c:
        require(record['global_deadline_ns']==end,'supplement is bounded by the original signed day')
    start=dt.datetime.fromisoformat(record['started_at_utc'].replace('Z','+00:00'))
    return start+dt.timedelta(microseconds=(end-record['started_monotonic_ns'])//1000)


def parent_verified():
    require(hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest()==PARENT_SHA,'exact D300 administrative parent')


def finalize_template(template, now, schema, deadline_utc):
    """Refresh only time fields; preserve every non-temporal authority binding."""
    import jsonschema
    require(now.tzinfo is not None and now.utcoffset()==dt.timedelta(0),'actual UTC timestamp required')
    require(template['deadline_policy']['session_max_wall_seconds']==24860
            and template['deadline_policy']['implicit_extension'] is False,'unchanged finite authority policy')
    for field,value in [('one_attempt',True),('retry_allowed',False),('stop_first',True),
                        ('retain_partial',True),('stage18_authority',False)]:
        require(template[field] is value,'unchanged authority '+field)
    result=copy.deepcopy(template)
    issued=now.replace(microsecond=0);expires=issued+dt.timedelta(seconds=24860)
    require(expires<=deadline_utc,'fresh authorization exceeds admitted total deadline')
    result['issued_at_utc']=issued.isoformat().replace('+00:00','Z')
    result['expires_at_utc']=expires.isoformat().replace('+00:00','Z')
    jsonschema.Draft202012Validator(schema).validate(result)
    require({k:v for k,v in result.items() if k not in ('issued_at_utc','expires_at_utc')}
            =={k:v for k,v in template.items() if k not in ('issued_at_utc','expires_at_utc')},
            'non-temporal authorization binding changed')
    return result


def validate_acceptance(value):
    expected=dict(decision_id='D301',owner_message='approve',exact_decision_text_approved=True,
        recorded_decision_sha256=PROPOSAL_SHA,new_execution_windows=0,manual_continuations=1,
        automatic_retry=False,repeat_qualification=False,repeat_completed_measurements=False,
        repeat_completed_raw_validations=False,reused_capture_count=86,remaining_capture_count=94,
        maximum_remaining_seconds=31460,original_deadline_monotonic_ns=ORIGINAL_DEADLINE,
        latest_start_monotonic_ns=ORIGINAL_DEADLINE-ENVELOPE,phase18_authority=False)
    for key,item in expected.items():
        require(type(value.get(key)) is type(item) and value[key]==item,'exact D301 approval '+key)


def validate_saved_state(c,validation):
    """Actual quiescent ledger replay and physical identity; no writes/registration."""
    import dataclasses
    import stage17_q16c_continuation_operator_v1 as io
    cli=io.cli_for(c,configured=True);built=io.document(c['preconstruction'])
    plan=io.document(built['plan']);inputs=io.document(built['action_inputs'])
    req=io.document(c['saved_request']);template=io.document(c['authorization_template'])
    require(c['saved_request']['sha256']==REQUEST_SHA and c['authorization_template']['sha256']==TEMPLATE_SHA,
            'exact saved request/template')
    require(req['action_inputs']==inputs and req['action_inputs']['plan']==plan,'unchanged request and prepared science')
    expected=[cli.base._resolution_binding(validation.resolutions[f'S17-EXT-{i:03d}']) for i in range(1,7)]
    runtime,release,_=cli.controller.runtime_from_context(validation)
    require(req['predecessor_resolutions']==template['predecessor_resolutions']==expected
            and req['runtime_binding']==runtime and req['release_binding']==release,'actual current qualification lineage')
    trust=validation.resolutions['S17-EXT-003'].semantic_context['trust']
    require(template['actor']==trust['measurements']['principal'] and template['reviewer']==trust['measurements']['reviewer_role'],
            'actual admitted template owner')
    require(template['request_binding']==c['saved_request'],'actual template/request bytes')
    pinned=cli.registry.pin_registry(Path(c['repository_root']))
    require(template['fixed_action_definition_sha256']==pinned.plan_sha256
            and template['permission_matrix']==pinned.action('Q16c')['permission_matrix'],'unchanged actual fixed action')
    cli.registry.validate_document(pinned,template,cli.registry.schema_path('phase-action-authorization'),'retained unsigned template')
    latest=io.document(c['latest_result']);recovery=io.document(c['latest_recovery'])
    require(latest['success'] is False and len(latest['phases'])==1
            and latest['phases'][0]['role']=='sign-collect' and latest['phases'][0]['leader_reaped'] is True
            and latest['partition_restoration']['verified'] is True
            and recovery['verified'] is True and recovery['errors']==[],'actual D298 stopped and restored')
    registration=io.document(c['family_registration'])
    require(registration['new_family_id']==built['plan']['sha256']
            and registration['after']['sha256']==TIP_SHA,'exact existing registration')
    executor=cli.controller.make_executor()
    limits=executor.custody_limits(plan['storage'],time.monotonic_ns()+120*10**9)
    with executor.custody.ProgramStore(Path(c['program_root']),scope_sha256=plan['storage']['program_scope_sha256'],
            family_id=built['plan']['sha256'],limits=limits) as store:
        require(not store._capture_pending and all(s['kind']=='RELEASED' for s in store._states.values()),'quiescent retained custody')
        require(dataclasses.asdict(store.ledger_binding())==registration['after'],'unchanged last ledger tip')
        facts=store._families[built['plan']['sha256']];family=store.working;st=family.stat(follow_symlinks=False)
        require(not family.is_symlink() and (st.st_dev,st.st_ino)==(facts['device'],facts['inode'])
                and not list(family.iterdir()),'exact empty registered family')
        require(template['evidence_root_binding']==cli.base._root_binding(family),'actual physical formal output root')
    require(not (Path(c['output_root'])/'prepared.json').exists()
            and not (Path(c['saved_request']['path']).parent/'authorization.json').exists()
            and not (Path(c['saved_request']['path']).parent/'authorization.json.sig').exists(),
            'no consumed operational authority')


def _metadata_function():
    parent_verified();text=inspect.getsource(previous.owner_metadata)
    text=text.replace('def owner_metadata(args, c):','def _metadata_impl(args, c):')
    text=text.replace('check_time(time.monotonic_ns())','if not args.software_check: check_time(time.monotonic_ns(),c)')
    text=text.replace("c['continuation_decision'] == 'D298'","c['continuation_decision'] == 'D301'")
    text=text.replace("c['original_total_deadline_ns'] == DEADLINE","c['original_total_deadline_ns'] == ORIGINAL_DEADLINE")
    text=text.replace("record['started_monotonic_ns']+39380*10**9 == DEADLINE","record['started_monotonic_ns']+39380*10**9 == ORIGINAL_DEADLINE")
    needle="    _verify_signature(acceptance_raw, Path(c['continuation_authority']['signature']['path']), trust)"
    text=previous.replace_once(text,needle,needle+'\n    verify_supplement(c,trust)')
    needle="    window.verify_bindings(record)"
    text=previous.replace_once(text,needle,needle+"\n    if 'deadline_supplement' in c: require(record['global_deadline_ns']==runtime_deadline(c),'original signed-day endpoint')")
    a=text.index("    require(not (Path(c['program_root'])/'working'/constructed['plan']['sha256']).exists()")
    b=text.index("    rows = inputs['hardware_control']['prestate']",a)
    text=text[:a]+'    validate_saved_state(c,validation)\n'+text[b:]
    text=text.replace('record=record,prestate=rows)','record=record,prestate=rows,launch_permitted=not args.software_check)')
    exec(compile(text,__file__+':retained-metadata','exec'),globals())
    return globals()['_metadata_impl']


def owner_journal(configuration,digest,*,software_check=False):
    import stage17_q16c_continuation_operator_v1 as io
    require(os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups(),'actual evidence owner')
    c=io.document(dict(path=str(configuration),size_bytes=Path(configuration).stat().st_size,sha256=digest))
    return _metadata_function()(types.SimpleNamespace(configuration_sha256=digest,software_check=software_check),c)


def admit(args,c,*,software_check=False):
    parent_verified();text=inspect.getsource(previous.admit)
    text=text.replace('def admit(args, c, *, software_check=False):','def _root_impl(args, c, *, software_check=False):')
    text=text.replace('    check_time(time.monotonic_ns())','    if not software_check: check_time(time.monotonic_ns(),c)')
    text=text.replace("'--owner-journal',str(args.configuration)","('--owner-journal-check' if software_check else '--owner-journal'),str(args.configuration)")
    text=text.replace("rows = accepted['prestate']","require(accepted['launch_permitted'] is (not software_check),'software admission grants no launch')\n    rows = accepted['prestate']")
    text=text.replace('d298-execution-owner-','d301-execution-owner-')
    text=previous.replace_once(text,'str(E/(','str(Path(args.configuration).parent/(')
    exec(compile(text,__file__+':retained-root-admission','exec'),globals())
    return globals()['_root_impl'](args,c,software_check=software_check)


def prepare_authorization(c,deadline):
    import subprocess
    import stage17_q16c_continuation_operator_v1 as io
    check_time(time.monotonic_ns(),c)
    require(time.monotonic_ns()<deadline,'readiness600s ceiling')
    template=io.document(c['authorization_template'])
    schema=io.document(c['authorization_schema'])
    # Native admission still revalidates the current signed authority before arm.
    value=finalize_template(template,dt.datetime.now(dt.timezone.utc),schema,deadline_utc(c))
    path=Path(c['saved_request']['path']).parent/'authorization.json'
    authorization=io.save(path,value)
    signed=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519',
        '-n','stage17-owner-acceptance',str(path)],capture_output=True,timeout=30)
    require(signed.returncode==0,'actual owner signing failed')
    built=io.document(c['preconstruction'])
    result=io.save(Path(c['output_root'])/'prepared.json',dict(plan=built['plan'],request=c['saved_request'],
        authorization=authorization,signature=io.binding(Path(str(path)+'.sig')),worker=c['worker'],
        execution_authority=False,phase18_authority=False))
    require(time.monotonic_ns()<deadline,'readiness publication600s ceiling')
    return result


def render(name,raw):
    parent_verified();text=previous.render(name,raw).decode()
    text=text.replace('d298-','d301-').replace('D298','D301')
    text=text.replace('d298_rearm_isolation','d301_rearm_isolation')
    text=text.replace('stage17_q16c_qualified_continuation_v1 as resume','stage17_q16c_saved_request_v1 as resume')
    if name.endswith('operator_v1.py'):
        a=text.index('    cli = cli_for(c, configured=True)',text.index('def sign_collect('))
        b=text.index('    import stage17_q16c_compaction_integration_v2 as guarded',a)
        text=text[:a]+'''    cli,d,args=common(c)
    root,evidence=Path(c['repository_root']),Path(c['evidence_root'])
    out=Path(c['output_root']);built=document(c['preconstruction']);plan=document(built['plan'])
    program=Path(c['program_root'])
'''+text[b:]
        text=previous.replace_once(text,"choices=('construct','sign-collect','suffix')","choices=('construct','authorize','sign-collect','suffix')")
        text=previous.replace_once(text,"    if args.mode=='construct':result=construct(c,args.deadline_ns)",
            "    if args.mode=='authorize':\n        import stage17_q16c_saved_request_v1 as saved\n        result=saved.prepare_authorization(c,args.deadline_ns)\n    elif args.mode=='construct':result=construct(c,args.deadline_ns)")
    elif name.endswith('study_v1.py'):
        text=previous.replace_once(text,'resume.check_time(time.monotonic_ns())','resume.check_time(time.monotonic_ns(),c)')
        text=previous.replace_once(text,'complete=min(resume.DEADLINE,start+resume.ENVELOPE)',
                                  'complete=min(resume.runtime_deadline(c),start+resume.ENVELOPE)')
        text=previous.replace_once(text,"native=args.role in ('construct','sign-collect')","native=args.role in ('construct','authorize','sign-collect')")
        text=previous.replace_once(text,"choices=('sign-collect','suffix')","choices=('authorize','sign-collect','suffix')")
        text=previous.replace_once(text,"        guard.verify();command('sign-collect'",
            "        command('authorize',min(start+600*NS,complete-(24860+2400+3600)*NS))\n        guard.verify();command('sign-collect'")
    ast.parse(text,filename=name)
    return text.encode()


def render_isolation():
    parent_verified();return previous.render_isolation().replace(b'D298',b'D301').replace(b'd298',b'd301')


if __name__=='__main__':
    require(len(sys.argv)==4 and sys.argv[1] in ('--owner-journal','--owner-journal-check'),'metadata-only owner entry')
    print(json.dumps(owner_journal(Path(sys.argv[2]),sys.argv[3],software_check=sys.argv[1].endswith('-check'))),flush=True)
