"""D279 one owner-requested first-Q16c continuation, reusing passed qualification.

Only the original frozen isolation core changes controls. No Q15 or clock capture
is invoked; exact current hardware prestate, ownership, boot, time and source
checks precede rearm. New study/receipt names preserve the stopped attempt.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
import types


def require(ok,message):
    if not ok:raise RuntimeError('Q16c rearm: '+message)


def verify_hardware(request):
    rows=request['action_inputs']['prestate'];out=[]
    require(type(rows) is list and {r['cpu'] for r in rows}=={0,1,8} and len(rows)==3,'actual three-CPU qualified prestate')
    for row in rows:
        cpu=row['cpu'];path='/dev/cpu/'+str(cpu)+'/msr'
        fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
        try:raw=os.pread(fd,8,0x1a4)
        finally:os.close(fd)
        require(len(raw)==8,'complete hardware read')
        actual=format(int.from_bytes(raw,'little'),'016x')
        require(actual==row['complete_value_hex'],'actual hardware differs from passed Q15-W prestate')
        out.append(dict(cpu=cpu,requested_value_hex=row['complete_value_hex'],observed_value_hex=actual,verified=True))
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--configuration',type=Path,required=True)
    p.add_argument('--configuration-sha256',required=True);p.add_argument('--operator-sha256',required=True);a=p.parse_args()
    import hashlib
    require(os.geteuid()==0 and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.operator_sha256,'bound root rearm operator')
    raw=a.configuration.read_bytes();require(hashlib.sha256(raw).hexdigest()==a.configuration_sha256,'configuration changed')
    c=json.loads(raw);b=c['files']['study_driver'];source=Path(b['path']).read_bytes()
    require(len(source)==b['size_bytes'] and hashlib.sha256(source).hexdigest()==b['sha256'],'driver bytes changed')
    d=types.ModuleType('q16c_continuation_driver');d.__file__=b['path'];exec(compile(source,b['path'],'exec'),d.__dict__)
    c,h,window,_=d.configure(a);d.verify_preconstruction(c)
    E=Path(c['evidence_root']);require(E.name=='local-authoring-cpuprefetchv5-28','bound original stand root')
    clock=d.module('q16c_rearm_isolation',c['files']['clock_adapter'])
    require(clock.Q==E/'q16c-continuation-recovery-1'
        and clock.BINDINGS['isolation_config']['evidence_root']==str(E/'isolation-preparation-v28-resume-2'),'fresh isolation evidence namespaces')
    record=d.load(c['files']['execution_window']);window.infrastructure(record,clock.BINDINGS['isolation_config'],now=time.monotonic_ns())
    require(not clock.CG.exists() and not clock.Q.exists() and not (E/'q16c-study-2').exists(),'no live partition/continuation; no automatic retry')
    plan=d.load(c['files']['frozen_plan']);family=Path(c['program_root'])/'working'/c['files']['frozen_plan']['sha256']
    require(not family.exists() and not (Path(c['repository_root'])/'evidence/formal-q16c-d270-1').exists(),'first native family must remain unused')
    require(d.load(c['files']['qualification_complete'])['success'] is True,'passed qualification required')
    restored=d.load(c['files']['prior_partition_restoration']);require(restored['verified'] is True and not restored['errors'],'prior recovery incomplete')
    native=d.load(c['files']['q15w_completion']);require(all(native[k] is True for k in ('restoration_verified','leader_reaped','process_group_gone')) and native['quarantined'] is False,'passed and reaped native Q15-W required')
    hardware=verify_hardware(d.load(c['files']['q15w_request']))
    require(clock.digest(clock.TOOL)==clock.BINDINGS['clock_binary_sha256'],'unchanged qualified clock executable')
    for pair in ('near','far'):clock.verify_raw(d.load(d.binding(E/'clock-qualification-v28-1'/pair/'clock-raw.json')),pair)
    # Inventory/UID/hash admission runs as the actual evidence owner, without
    # invoking worker bytes or changing their permissions.
    import subprocess
    owner=E/'d279-execution-owner-admission-1.json';src=d.load(c['files']['source_manifest'])
    subprocess.run(['runuser','-u','omaltsev','--','python3','-B',c['files']['execution_owner_guard']['path'],
        '--bundle-root',str(Path(c['worker']['path']).parents[2]),'--uid','1000','--inventory-sha256',src['bundle_inventory_sha256'],
        '--source-revision',src['software_source_revision'],'--worker-sha256',c['worker']['sha256'],'--output',str(owner)],check=True,timeout=120)
    def interrupted(number,frame):raise RuntimeError('rearm signal '+str(number))
    for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(s,interrupted)
    clock.Q.mkdir(mode=0o700);os.chown(clock.Q,1000,1000)
    try:
        os.sched_setaffinity(0,{3})
        pre=clock.ISO.prepare(clock.BINDINGS['isolation_config'])
        pp=Path(clock.BINDINGS['isolation_config']['evidence_root'])/'prospective-prestate.json'
        clock.retain(clock.Q/'prospective-plan.json',dict(isolation_prestate_binding=d.binding(pp),
            original_qualification=c['files']['qualification_complete'],execution_window=c['files']['execution_window'],
            clocks_repeated=False,q15_repeated=False,global_deadline_ns=record['global_deadline_ns']))
        clock.ISO.verify_remaining_lifetime(pre['prestate'],window.FAMILY*10**9,120*10**9)
        observed=clock.isolated_state();require(observed['partition']['cgroup.procs']=='','fresh empty owned partition')
        verify_hardware(d.load(c['files']['q15w_request']))
        clock.retain(clock.Q/'rearm-complete.json',dict(status='SAME_SOURCE_BOOT_HARDWARE_NEW_ISOLATION',
            hardware=hardware,isolation=observed,original_qualification=c['files']['qualification_complete'],
            preconstruction=c['files']['constructed'],clocks_repeated=False,q15_repeated=False,automatic_retries=0))
        argv=['/usr/bin/python3','-B',c['files']['study_driver']['path'],'--run','--configuration',str(a.configuration),
            '--configuration-sha256',a.configuration_sha256]
        os.execv(argv[0],argv)
    except BaseException as error:
        try:clock.cleanup_after_external_failure(error,quiescence_timeout_seconds=120)
        finally:
            d.save(clock.Q/'rearm-failure.json',dict(error=repr(error),automatic_retries=0))
        raise


if __name__=='__main__':main()
