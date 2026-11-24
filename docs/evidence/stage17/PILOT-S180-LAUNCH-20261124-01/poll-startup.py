from pathlib import Path
import subprocess,json,datetime,time,os
root=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/s180-d310-1');unit='cpu-prefetch-s180-operator-1.service'
raw=subprocess.run(['systemctl','show',unit,'--property=ActiveState,SubState,MainPID,ControlPID,Result,InvocationID,NRestarts,ExecMainStartTimestamp,ExecMainStatus,ExecStopPost'],check=True,capture_output=True,text=True,timeout=10).stdout
props=dict(line.split('=',1) for line in raw.strip().splitlines())
result=dict(utc=datetime.datetime.now(datetime.UTC).isoformat(),unit=props,operational_root_exists=os.path.lexists(root),compaction_control=Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip())
for name in ('controller-intent.json','controller-failure.json','controller-handoff.json','source-author/intent.json','source-author/failure.json','source-author/completion.json','namespaces/ready.json'):
 path=root/name
 if path.is_file():
  s=path.stat();result.setdefault('present_metadata',[]).append(dict(name=name,size_bytes=s.st_size))
  if name in ('controller-intent.json','controller-failure.json'):
   data=path.read_bytes();assert len(data)<=16384;result[name]=json.loads(data)
if result.get('controller-intent.json'):
 window=result['controller-intent.json']['window_binding'];remaining=(window['end_monotonic_ns']-time.monotonic_ns())/1e9
 result['original_window_remaining_seconds']=round(remaining,1);result['approx_window_end_utc']=(datetime.datetime.now(datetime.UTC)+datetime.timedelta(seconds=remaining)).isoformat()
print(json.dumps(result,sort_keys=True,indent=2))
