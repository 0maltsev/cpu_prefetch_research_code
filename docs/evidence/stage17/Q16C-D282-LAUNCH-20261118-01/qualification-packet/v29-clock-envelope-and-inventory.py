import datetime,json,pathlib,subprocess,os,hashlib,sys
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');P=E/'operator-preparation-v29';B=E/'local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272';Q=E/'clock-qualification-v29-1/near'
sys.path.insert(0,str(P));import run_clock_qualification_v29 as isolation
assert json.loads((Q.parent/'complete.json').read_bytes())['both_pairs_passed'] is True
for pair in ('near','far'):isolation.verify_raw(json.loads((Q.parent/pair/'clock-raw.json').read_bytes()),pair)
args=['python3','-B',str(P/'emit_qualification_envelope_commands.py'),'clock','--bundle-root',str(B),'--qualification-directory',str(Q),'--source-revision','7fb894425c82fa7d7f1891f52b3bcdacc2c83585','--id-prefix','CPU-PREFETCH-V5-V29']
r=subprocess.run(['runuser','-u','omaltsev','--',*args],check=True,capture_output=True,text=True);planned=json.loads(r.stdout)
isolation.retain(Q/'clock-envelope-authoring-plan.json',planned)
for cmd in planned['argv']:
 output=pathlib.Path(cmd[cmd.index('--output')+1]);assert not output.exists()
 started=isolation.utc();r=subprocess.run(['runuser','-u','omaltsev','--',*cmd],capture_output=True,text=True)
 isolation.retain(Q/'clock-envelope-authoring-result.json',{'started':started,'completed':isolation.utc(),'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 assert r.returncode==0,(r.stdout,r.stderr);assert json.loads(output.read_bytes())['eligible'] is True
 print('CLOCK_ENVELOPE_PASS',flush=True)
subprocess.run(['runuser','-u','omaltsev','--','python3','-B',str(P/'author_platform_facts.py'),'snapshot','--output',str(E/'platform-inventory-1.json')],check=True)
print('FRESH_PLATFORM_INVENTORY_PASS',flush=True)
