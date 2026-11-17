"""Prepare D277's first-native Q15 packet from the retained, unexecuted D276 draft.

No stand action occurs here. A real, separately signed D277 execution record is
required to finalize the finite lifetime bindings; native/clock binaries stay fixed.
"""
from pathlib import Path
import argparse,ast,hashlib,json,subprocess,tarfile
ROOT=Path.cwd();BASE=ROOT/'build/stage17-q16c-prep/qualification-packet-919c486-4'
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28');P=E/'operator-preparation-v28-3'
a=argparse.ArgumentParser();a.add_argument('--window-file',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
window_raw=args.window_file.read_bytes();window=json.loads(window_raw);start=window['started_monotonic_ns']
assert window['schema_version']=='cpu-prefetch-stage17-q16c-retained-setup-execution-window/1'
assert window['global_deadline_ns']-start==86400*10**9
OUT=args.output;OUT.mkdir();REV=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
def raw(v):return (json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(name,data):
 if isinstance(data,str):data=data.encode()
 if name.endswith('.py'):ast.parse(data,name)
 (OUT/name).write_bytes(data)
finite=json.loads((BASE/'finite-qualification-plan.json').read_bytes());finite.update(schema_version='cpu-prefetch-v28-d277-q15-preparation/1',qualification_budget_seconds=7200,preparation_latest_qualify_start_monotonic_ns=start+600*10**9)
finite['authorization_basis'].update(current_instruction='D277 accepted owner continue: one separate execution window, retained setup, one initial native Q15 then full180 Q16c; fresh D278 third-edge administrative renewal.',new_explicit_approval_claimed=False,operational_direction='Preserve old timestamps, passed clocks and completed data. No clocks or source regeneration. One first-native Q15. Stop/restore first failure. No retry or further window.')
finite['standing_records']=[r for r in finite['standing_records'] if not r['path'].startswith('docs/decisions/0276-')]
for name in ('docs/decisions/0277-q16c-retained-setup-new-window-proposal.md','docs/STAGE17_EXT007_Q16C_D277_ACCEPTANCE.md','docs/evidence/stage17/Q16C-D277-ACCEPTED-20261117-01/owner-acceptance.json','docs/decisions/0278-q16c-third-transition-authority-renewal.md'):
 finite['standing_records'].append(dict(path=name))
for row in finite['standing_records']:
 b=(ROOT/row['path']).read_bytes();row.update(size_bytes=len(b),sha256=sha(b))
fb=raw(finite);c=json.loads((BASE/'clock-bindings-v28.json').read_bytes())
c['original_source_binding']=c['absolute_window_binding'];c['absolute_window_binding']=dict(path=str(E/'d277-execution-window-1/window.json'),size_bytes=len(window_raw),sha256=sha(window_raw))
c.update(qualification_budget_ns=7200*10**9,preparation_monotonic_ns=start,finite_plan_binding=dict(path=str(P/'finite-qualification-plan.json'),size_bytes=len(fb),sha256=sha(fb)))
c['isolation_config'].update(lifecycle_seconds=63000,protected_work_ns=(7200+47820+120)*10**9)
for p in sorted(BASE.glob('*.py')):
 s=p.read_text()
 if p.name=='run_clock_qualification_v28.py':
  tree=ast.parse(s);n=next(x for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BINDINGS' for t in x.targets));lines=s.splitlines(keepends=True);s=''.join(lines[:n.lineno-1])+'BINDINGS = '+repr(c)+'\n'+''.join(lines[n.end_lineno:])
  s=s.replace("'absolute_window_binding', 'preparation_monotonic_ns'", "'absolute_window_binding', 'original_source_binding', 'preparation_monotonic_ns'")
  s=s.replace('import stage17_q16c_q15_continuation_window_v1 as original_window','import stage17_q16c_execution_window_v1 as original_window')
  s=s.replace('D276 forbids','D277 forbids')
 if p.name=='run_qualification_v28.py':
  s=s.replace('q15-continuation-window-1.json','d277-qualification-window-1.json')
  for old,new in [('intent-2.json','intent-3.json'),('complete-2.json','complete-3.json'),('failure-2.json','failure-3.json'),('pid-2.json','pid-3.json'),('terminal-2.json','terminal-3.json'),('console-2.log','console-3.log'),('.result-2.json','.result-3.json')]:s=s.replace(old,new)
  s=s.replace("    import stage17_q16c_q15_continuation_window_v1 as guard", "    import stage17_q16c_q15_continuation_window_v1 as retained\n    import stage17_q16c_execution_window_v1 as guard")
  s=s.replace("source=json.loads(isolation.bound_bytes(isolation.BINDINGS['absolute_window_binding']))\n    guard.validate(source,now=time.monotonic_ns(),qualification=True)", "source=json.loads(isolation.bound_bytes(isolation.BINDINGS['original_source_binding']))\n    execution=json.loads(isolation.bound_bytes(isolation.BINDINGS['absolute_window_binding']))\n    guard.infrastructure(execution,isolation.BINDINGS['isolation_config'],now=time.monotonic_ns())")
  s=s.replace('guard.verify_retained(', 'retained.verify_retained(')
  s=s.replace('pre[\'prestate\'],(1800+47820)*10**9','pre[\'prestate\'],(7200+47820)*10**9')
  s=s.replace("+2400*10**9<source['global_deadline_ns']", "+2400*10**9<execution['global_deadline_ns']")
  s=s.replace("original_global_deadline_ns=source['global_deadline_ns']))", "original_global_deadline_ns=source['global_deadline_ns'],execution_global_deadline_ns=execution['global_deadline_ns']))")
  old="                self.step('v28-admit-ext005.py')\n                isolation.retain_q15w_handoff(quiescence_timeout_seconds=120)"
  new="                retain('q15-owned-session-success-3.json',dict(pid=self.session.pid,exit_code=self.session.returncode,leader_reaped=True))\n                isolation.retain_q15w_handoff(quiescence_timeout_seconds=120)\n                self.step('v28-admit-ext005.py')"
  assert old in s;s=s.replace(old,new).replace('D276 only corrected Q15','D277 only initial native Q15')
 if p.name=='v28-admit-ext005.py':
  old="cli('append-transition','--actor',actor,'--timestamp-utc',utc())"
  new='''# The ordinary expired edge is retained before its explicit D278 renewal.
cmd=['runuser','-u','omaltsev','--','python3','-B',str(R/'tools/stage17_operational_cli_daycap_v3.py'),'--repository-root',str(R),'--evidence-root',str(E),'--pilot-archive',str(A),'--pilot-sidecar',str(S),'append-transition','--actor',actor,'--timestamp-utc',utc()]
r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
import sys,hashlib
sys.path.insert(0,str(P));import run_clock_qualification_v28 as isolation
isolation.retain(E/'d278-original-transition-rejection-1.json',dict(argv=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,automatic_retry=False))
assert r.returncode!=0 and 'transition authority is future/expired' in r.stderr+r.stdout,(r.returncode,r.stdout,r.stderr)
assert not (E/'journal/stage17-state-journal-000009.json').exists()
inv=hashlib.sha256((P/'preparation-inventory.json').read_bytes()).hexdigest()
op('python3','-B',P/'renew_stage17_e28_transition_v1.py','--inventory-sha256',inv)
assert json.loads((E/'d278-transition-1/complete.json').read_bytes())['status']=='ADMINISTRATIVE_THIRD_EDGE_RENEWED'
'''
  assert old in s;s=s.replace(old,new)
 write(p.name,s)
for name in ('stage17_state_journal_v58.py','stage17_q16c_execution_window_v1.py','renew_stage17_e28_transition_v1.py'):write(name,(ROOT/'tools'/name).read_bytes())
write('d278-decision.md',(ROOT/'docs/decisions/0278-q16c-third-transition-authority-renewal.md').read_bytes())
write('d278-owner-acceptance.json',raw(dict(schema_version='cpu-prefetch-stage17-owner-decision/1',decision_id='D278',owner_message='continue',recorded_decision_sha256=sha((ROOT/'docs/decisions/0278-q16c-third-transition-authority-renewal.md').read_bytes()),exact_decision_text_approved=False,authority_scope='E28_D278_ADMINISTRATIVE_TRANSITION_ONLY',execution_authority=False,phase18_authority=False)))
for name,data in [('finite-qualification-plan.json',fb),('clock-bindings-v28.json',raw(c)),('isolation-config-v28.json',raw(c['isolation_config'])),('release-bindings.json',(BASE/'release-bindings.json').read_bytes()),('v28-codegen-facts.json',(BASE/'v28-codegen-facts.json').read_bytes()),('v28-platform-build-facts.json',(BASE/'v28-platform-build-facts.json').read_bytes())]:write(name,data)
assert sha((OUT/'isolation_core.py').read_bytes())=='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
files=[dict(path=p.name,size_bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(OUT.iterdir())]
inv=dict(schema_version='cpu-prefetch-v28-d277-q15-inventory/1',administrative_source_revision=REV,preparation_only=True,launch_performed=False,clock_repeated=False,files=files)
write('preparation-inventory.json',raw(inv))
with tarfile.open(OUT.with_suffix('.tar'),'w') as t:
 for p in sorted(OUT.iterdir()):t.add(p,arcname=p.name,recursive=False)
print(json.dumps(dict(inventory_sha256=sha(raw(inv)),tar_sha256=sha(OUT.with_suffix('.tar').read_bytes()),files=len(files))))
