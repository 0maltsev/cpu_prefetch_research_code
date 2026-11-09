"""D243 proposed additional cold-tested isolation reapplication; no clocks/Q15/Q16 invocation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
P=E/'formal-q16a-continuation-authoring-1'
Q=E/'isolation-preparation-v25-resume-2'
CORE=Path('/run/cpu-prefetch-recovery-v25-qualified-1/isolation_core.py')
CORE_SHA='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def hardware(plan,expected,topology):
    observations={}
    for cpu,siblings in topology.items():
        actual=(Path('/sys/devices/system/cpu')/('cpu'+cpu)/'topology/thread_siblings_list').read_text().strip()
        assert actual==siblings,('qualified SMT topology changed',cpu)
        observations[cpu]=dict(thread_siblings_list=actual)
    placements=set()
    for row in plan['captures']:
        g=row['capture']['geometry']
        placements.update((g[role+'_cpu'],g[role+'_node']) for role in ('producer','consumer'))
        s=row['resources']['controller_stack'];placements.add((s['owner_cpu'],s['requested_node']))
    for cpu,node in placements:
        p=Path('/sys/devices/system/cpu')/('cpu'+str(cpu))
        assert sorted(v.name for v in p.glob('node*'))==['node'+str(node)],('NUMA placement changed',cpu)
        observations[str(cpu)]['numa_node']=node
    msrs=[]
    for row in expected:
        cpu=row['cpu'];fd=os.open('/dev/cpu/'+str(cpu)+'/msr',os.O_RDONLY|os.O_CLOEXEC)
        try:raw=os.pread(fd,8,0x1a4)
        finally:os.close(fd)
        assert len(raw)==8
        observed=f'{int.from_bytes(raw,"little"):016x}'
        assert observed==row['complete_value_hex'],('MSR prestate differs',cpu,observed)
        msrs.append(dict(cpu=cpu,observed_hex=observed,matches=True))
    return dict(topology=observations,msr_readback=msrs)


def main():
    assert os.geteuid()==0 and sha(CORE)==CORE_SHA
    approval=json.loads((E/'d243-owner-acceptance-1.json').read_bytes())
    assert approval['decision_id']=='D243' and approval['approved'] is True
    assert approval['additional_isolation_preparations']==1 and approval['repeat_qualification'] is False
    assert approval['owner_check_wall_seconds']==600
    assert approval['plan_sha256']=='91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'
    assert json.loads((E/'d242-commit-1.json').read_bytes())['exit_code']==0
    assert (E/'admission-root/evidence/formal-q16a-1/authorization.json.sig').is_file()
    assert not Q.exists()
    auth=E/'admission-root/evidence/formal-q16a-1'
    assert sha(auth/'request.json')=='aa780db91ceaaedca11fe3b4036c3506e9de80b5a25c6189c69c7a065ed8026a'
    assert sha(auth/'authorization.json')=='c84caa002b522e1228500474ac2f514e6db5e0f5214bfac332acc592d499d4bf'
    assert sha(auth/'authorization.json.sig')=='f2b00a01489e921212cf74f20254dce9c4a3174cb7765f5cb3e428acaaa94b06'
    family=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1/working/91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'
    assert family.is_dir() and not list(family.iterdir())
    assert not (E/'formal-q16a-continuation-launch-1').exists()
    spec=importlib.util.spec_from_file_location('approved_isolation',CORE)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    pre_original=json.loads((E/'isolation-preparation-v25-1/prospective-prestate.json').read_bytes())
    config=dict(pre_original['operator_config'],evidence_root=str(Q))
    assert config['source_revision']=='42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==config['boot_id']
    assert sha(P/'plan.json')=='91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'
    plan=json.loads((P/'plan.json').read_bytes())
    topology=json.loads((E/'clock-qualification-v25-1/prospective-plan.json').read_bytes())['topology']
    request=E/'admission-root/evidence/q15w-fresh/request.json'
    completion=json.loads((E/'stage17-q15_w-completion-v4.json').read_bytes())
    assert sha(request)==completion['request_sha256']
    expected=json.loads(request.read_bytes())['action_inputs']['prestate']
    before=hardware(plan,expected,topology)
    def interrupt(signum,frame):raise RuntimeError('isolation reapplication interrupted '+str(signum))
    for signum in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(signum,interrupt)
    pre=None
    try:
        pre=core.prepare(config)
        after=hardware(plan,expected,topology)
        assert before==after
        observation=core.isolated_state()
        core.verify_remaining_lifetime(pre['prestate'],plan['budget']['watchdog_ns'],plan['budget']['cleanup_ns'])
        assert observation['partition']['cgroup.procs']=='' and 'populated 0' in observation['partition']['cgroup.events'].splitlines()
        core.retain(Q/'d243-reapplication-handoff.json',dict(utc=core.utc(),policy_id='D243',
            isolation_reapplied=True,qualification_repeated=False,source_revision=config['source_revision'],
            boot_id=config['boot_id'],partition_path=str(core.CG),observation=observation,
            hardware_before=before,hardware_after=after,
            q15w_result_sha256=sha(E/'stage17-q15-w-result-v4.json'),
            q15w_completion_sha256=sha(E/'stage17-q15_w-completion-v4.json'),
            isolation_prestate_sha256=sha(Q/'prospective-prestate.json'),
            original_restoration_sha256=sha(E/'clock-qualification-v25-1/restoration.json'),
            operator_sha256=sha(Path(__file__))))
        print(json.dumps(dict(status='ISOLATION_REAPPLIED_VERIFIED',qualification_repeated=False,evidence_root=str(Q))),flush=True)
    except BaseException:
        if pre is not None:core.restore(pre['prestate'])
        raise


if __name__=='__main__':main()
