"""D275 signed Q16c check/collection/analysis through the authenticated packet."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import types


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('check','collect','analyze'))
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    p.add_argument('--deadline-ns',type=int,required=True);a=p.parse_args()
    # The bootstrap is independently bound by the root operator configuration.
    import hashlib
    raw=a.configuration.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.configuration_sha256:raise ValueError('operator configuration changed')
    c=json.loads(raw);b=c['files']['preparation_operator'];source=Path(b['path']).read_bytes()
    if len(source)!=b['size_bytes'] or hashlib.sha256(source).hexdigest()!=b['sha256']:raise ValueError('preparation bootstrap changed')
    helper=types.ModuleType('q16c_bound_preparation');helper.__file__=b['path'];exec(compile(source,b['path'],'exec'),helper.__dict__)
    helper.require(os.getuid()==os.geteuid()==1000 and time.monotonic_ns()<a.deadline_ns,'owner/deadline')
    loader=helper.loader_for(c);d=helper.document(helper.binding(Path(c['output_root'])/'prepared.json'))
    cfgb=d['cli_configuration'];cli,cfg=loader.activate(Path(cfgb['path']),cfgb['sha256'])
    evidence=Path(c['evidence_root']);root=Path(c['repository_root'])
    common=dict(repository_root=root,operational_evidence_root=evidence,journal=cli.base.latest_journal(evidence),
        journal_directory=evidence/'journal',authorization_path=Path(d['authorization']['path']),
        signature_path=Path(d['signature']['path']),pilot_archive=Path(cfg['archive']['path']),pilot_sidecar=Path(cfg['sidecar']['path']))
    if a.mode=='analyze':
        restoration=helper.document(helper.binding(evidence/'q16c-study-1/partition-restoration.json'))
        helper.require(restoration['verified'] is True,'actual infrastructure restoration before analysis')
        prepared=cli.prepare_formal_retention(**common)
        analysis=sys.modules['stage17_q16c_analysis_v1']
        print(json.dumps(analysis.analyze(cli,prepared,evidence/'q16c-analysis-1',global_deadline_ns=a.deadline_ns,
            retained_failed_scratch_bytes=c['retained_failed_scratch_bytes'],
            started_monotonic_ns=a.deadline_ns-analysis.TOTAL_NS)),flush=True)
    elif a.mode=='check':
        prepared=cli.controller.prepare_action(**common)
        helper.require(prepared.request_bytes==helper.read(d['request'])
            and prepared.request['action_inputs']['plan']==helper.document(d['plan']),'actual signed request/plan')
        extent=cli.controller.contract.validate_plan('Q16c',prepared.request['action_inputs']['plan'])
        phase=Path(prepared.request['evidence_root_binding']['absolute_path'])
        helper.require(not list(phase.iterdir()),'fresh registered family')
        fd=os.open(phase,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:observed=cli.controller.make_executor().live_resources(fd,extent,request=prepared.request,
            deadline_ns=min(a.deadline_ns,time.monotonic_ns()+120*10**9))
        finally:os.close(fd)
        helper.require(observed['memory_available_bytes']>=extent.declared.memory_bytes+8*1024**3,'complete actual memory reserve')
        helper.save(evidence/'q16c-study-1/owner-check.json',dict(status='SIGNATURE_SOURCE_HISTORY_RESOURCE_ADMISSION_PASS',
            plan=d['plan'],observed=observed,execution_authority=False))
    else:
        check=helper.document(helper.binding(evidence/'q16c-study-1/owner-check.json'))
        helper.require(check['status']=='SIGNATURE_SOURCE_HISTORY_RESOURCE_ADMISSION_PASS' and check['plan']==d['plan'],
            'actual signed owner check required')
        result=cli.execute_formal(**common)
        # execute_once publishes the original authenticated completion/failure.
        print(json.dumps(dict(result=str(result))),flush=True)
    loader.check_loaded()


if __name__=='__main__':main()
