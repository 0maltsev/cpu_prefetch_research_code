import datetime,json,pathlib,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');R=E/'admission-root';P=E/'operator-preparation-v29';NAME='cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272';B=E/'local-bundle-extract'/NAME;A=E.parent/(NAME+'.tar.gz');S=pathlib.Path(str(A)+'.sha256');actor='maltsev.oiu@phystech.edu'
def utc():return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def op(*args):
 print('OPERATOR',utc(),json.dumps(list(map(str,args))),flush=True);subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True)
def cli(*args):op('python3','-B',R/'tools/stage17_operational_cli_daycap_v4.py','--repository-root',R,'--evidence-root',E,'--pilot-archive',A,'--pilot-sidecar',S,*args)
def author(kind,*args):op('python3','-B',P/'author_fresh_qualification_records_v2.py',kind,'--repository-root',R,'--evidence-root',E,'--bundle-root',B,'--pilot-archive',A,'--pilot-sidecar',S,'--id-prefix','CPU-PREFETCH-V5-V29','--archive-runtime-root','/',*args)


import sys
sys.path.insert(0,str(P));import run_clock_qualification_v29 as isolation
Q=E/'clock-qualification-v29-1/near'
args=['python3','-B',P/'emit_qualification_envelope_commands.py','q15r','--bundle-root',B,'--qualification-directory',Q,'--source-revision','7fb894425c82fa7d7f1891f52b3bcdacc2c83585','--id-prefix','CPU-PREFETCH-V5-V29','--request',R/'evidence/q15r-fresh/request.json','--codegen-facts',P/'v29-codegen-facts.json']
result=subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True,capture_output=True,text=True);plan=json.loads(result.stdout)
isolation.retain(Q/'q15r-envelope-authoring-plan.json',plan)
for index,cmd in enumerate(plan['argv']):
 output=pathlib.Path(cmd[cmd.index('--output')+1]);assert not output.exists()
 started=utc();r=subprocess.run(['runuser','-u','omaltsev','--',*cmd],capture_output=True,text=True)
 isolation.retain(Q/('q15r-envelope-authoring-result-'+str(index)+'.json'),{'started':started,'completed':utc(),'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 assert r.returncode==0,(r.stdout,r.stderr);assert json.loads(output.read_bytes())['eligible'] is True
 print('ENVELOPE_PASS',output.name,flush=True)
op('python3','-B',P/'author_platform_facts.py','compose','--repository-root',R,'--evidence-root',E,'--bundle-root',B,'--pilot-archive',A,'--pilot-sidecar',S,'--id-prefix','CPU-PREFETCH-V5-V29','--request',R/'evidence/q15r-fresh/request.json','--result',E/'stage17-q15-r-result-v4.json','--snapshot',E/'platform-inventory-1.json','--build-facts',P/'v29-platform-build-facts.json','--clock-envelope',Q/'SELECTED_PAIR_CLOCK.json','--near-cpus','0','1','--far-cpus','0','8','--output',E/'platform-facts-1.json','--provenance-output',E/'platform-facts-provenance-1.json')
author('ext004','--platform-facts',E/'platform-facts-1.json','--qualification-directory',Q)
cli('admit-resolution','--input-id','S17-EXT-004','--actor',actor,'--recorded-at-utc',utc(),'--receipt-evidence',E/'receipts/ext004-custody-receipt-1.json')
cli('status')
