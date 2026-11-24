"""Reapply approved, previously qualified isolation once; no clock capture."""
import datetime, hashlib, json, os, pathlib, signal, struct, subprocess, sys
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19')
R=E/'admission-root'; P=E/'operator-preparation-v19'; Q=E/'discovery-isolation-r2-1'
assert hashlib.sha256((P/'run_clock_requalification_v2.py').read_bytes()).hexdigest()=='22873c5c62ed4db7b6758bf7cec8a304afe428104d4ca8498c90414fe2dc5031'
sys.path.insert(0,str(P));import run_clock_requalification_v2 as isolation
isolation.Q=Q
old=json.loads((E/'clock-requalification-2/prospective-plan.json').read_bytes())
assert os.geteuid()==0 and not Q.exists() and not isolation.CG.exists()
assert isolation.read('/proc/sys/kernel/random/boot_id')==old['boot_id']
before=isolation.root_state();assert before==old['prestate']
assert not list(isolation.ROOT.rglob('cpuset.cpus.partition'))
for cpu,expected in old['topology'].items():
    assert isolation.read(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list')==expected
prior=json.loads((E/'discovery-launch-readback-1.json').read_bytes())
for item in prior['executable_bindings'].values():
    assert isolation.digest(item['path'])==item['sha256']
assert isolation.digest(isolation.B/'release/bin/cpu_prefetch_runner')=='cffe204c0af3bffaa46912a52dfa3d79c2114ba1b87e74f71573dd2a14071268'
baseline=json.loads((E/'discovery-resource-inventory-1.json').read_bytes())
stable_suffixes=('scaling_driver','scaling_governor','scaling_min_freq','scaling_max_freq')
stable_paths=('/proc/sys/kernel/numa_balancing','/proc/sys/kernel/random/boot_id','/sys/devices/system/cpu/online','/sys/devices/system/clocksource/clocksource0/current_clocksource','/sys/kernel/mm/transparent_hugepage/enabled','/sys/kernel/mm/transparent_hugepage/defrag')
stable=[]
for item in baseline['files']:
    name=item['path']
    if name in stable_paths or name.endswith(stable_suffixes):
        raw=pathlib.Path(name).read_bytes();assert hashlib.sha256(raw).hexdigest()==item['sha256'],name
        stable.append(dict(path=name,sha256=item['sha256']))
msrs=[]
for cpu in (0,1,8):
    fd=os.open(f'/dev/cpu/{cpu}/msr',os.O_RDONLY)
    try:raw=os.pread(fd,8,0x1a4)
    finally:os.close(fd)
    assert len(raw)==8 and struct.unpack('<Q',raw)[0]==0
    msrs.append(dict(cpu=cpu,complete_value_hex=raw[::-1].hex()))
A=E.parent/(isolation.B.name+'.tar.gz'); S=pathlib.Path(str(A)+'.sha256')
argv=['runuser','-u','omaltsev','--','python3','-B',str(R/'tools/stage17_operational_cli_v16.py'),'--repository-root',str(R),'--evidence-root',str(E),'--pilot-archive',str(A),'--pilot-sidecar',str(S),'status']
status=json.loads(subprocess.check_output(argv))
assert status['current_state']=='READY_FOR_STAGE17_PHASE_AUTHORIZATION' and status['resolutions']==6 and status['transitions']==3,status
assert status['missing_inputs']==['S17-EXT-007','S17-EXT-008','S17-EXT-009','S17-EXT-010'],status
os.sched_setaffinity(0,{3});Q.mkdir(mode=0o700);os.chown(Q,1000,1000)
isolation.retain(Q/'prestate.json',dict(recorded_at_utc=isolation.utc(),prestate=before,original_clock_plan_sha256=isolation.digest(E/'clock-requalification-2/prospective-plan.json'),stable_controls=stable,msr_readback=msrs,status=status,new_clock_capture_authority=False))
success=False
def interrupted(number,frame):raise RuntimeError('operator signal '+str(number))
for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,interrupted)
try:
    isolation.write_control(isolation.ROOT/'cgroup.subtree_control','+cpuset')
    isolation.CG.mkdir()
    for name,value in [('cpuset.mems','0-1'),('cpuset.cpus',isolation.CPU_LIST),('cpuset.cpus.exclusive',isolation.CPU_LIST),('cpuset.cpus.partition','isolated')]:
        isolation.write_control(isolation.CG/name,value)
    observed=isolation.isolated_state();assert observed['partition']['cgroup.procs']==''
    isolation.retain(Q/'isolation-verified.json',observed)
    print(json.dumps(dict(status='PASS_SAME_ISOLATION_REAPPLIED_NO_CLOCK_CAPTURE',observed=observed)))
    success=True
finally:
    if not success:isolation.restore(before)
