import json,pathlib,sys,os,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');R=E/'admission-root';P=E/'operator-preparation-v29'
A=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272.tar.gz';S=pathlib.Path(str(A)+'.sha256')
sys.path.insert(0,str(P));import run_clock_qualification_v29 as isolation
assert json.loads((E/'clock-qualification-v29-1/complete.json').read_bytes())['both_pairs_passed'] is True
before=isolation.isolated_state();assert before['partition']['cgroup.procs']==''
argv=['runuser','-u','omaltsev','--','python3','-B',str(R/'tools/stage17_operational_cli_daycap_v4.py'),'--repository-root',str(R),'--evidence-root',str(E),'--pilot-archive',str(A),'--pilot-sidecar',str(S),'journal-path']
journal=subprocess.check_output(argv,text=True).strip();assert pathlib.Path(journal).is_file()
QR=R/'evidence/q15r-fresh'
command=['/usr/bin/python3','-B',str(P/'q15-launch-8gib-v2.py'),'--python','/usr/bin/python3','--setpriv','/usr/bin/setpriv','--gid','1000','--controller',str(R/'tools/stage17_q15_session_controller_daycap_v4.py'),'--record',str(E/'q15-launch-readback-1.json'),'--','--start','--repository-root',str(R),'--journal',journal,'--journal-directory',str(E/'journal'),'--operational-evidence-root',str(E),'--authorization',str(QR/'authorization.json'),'--signature',str(QR/'authorization.json.sig'),'--pilot-archive',str(A),'--pilot-sidecar',str(S)]
isolation.retain(E/'q15-launch-intent-1.json',{'utc':isolation.utc(),'argv':command,'isolation':before,'cgroup_entered_before_owner_launch':str(isolation.CG),'supervisor_remains_live_until_q15_w_or_failure':True})
isolation.write_control(isolation.CG/'cgroup.procs',str(os.getpid()));os.sched_setaffinity(0,{2})
print('Q15_SESSION_LAUNCH',isolation.utc(),flush=True)
os.execv(command[0],command)
