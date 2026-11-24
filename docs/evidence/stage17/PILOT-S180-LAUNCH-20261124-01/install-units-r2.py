from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path('/opt/cpu-prefetch-s180-service-1');digest='548884312b7508d76d697863caf57ba0656ba0c2c114021e692c7c83c54df718'
sys.path.insert(0,str(root));import stage17_s180_service_v1 as service
profile,execution,observer=service.authenticate(digest)
assert not os.path.lexists(execution.ROOT) and not os.path.lexists(service.RUN)
units=service.service_units(digest);parent=Path('/run/systemd/system');paths=[]
for name,text in units.items():
 path=parent/name;assert not os.path.lexists(path)
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
 try:
  raw=text.encode();assert os.write(fd,raw)==len(raw);os.fsync(fd)
 finally:os.close(fd)
 assert path.read_text()==text;paths.append(str(path))
checked=subprocess.run(['/usr/bin/systemd-analyze','verify',*paths],capture_output=True,text=True,timeout=60)
assert checked.returncode==0,(checked.stdout,checked.stderr)
subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True,timeout=30)
rows={}
for name in units:
 result=subprocess.run(['/usr/bin/systemctl','show',name,'--property=LoadState,ActiveState,SubState,MainPID,ExecStart,ExecStopPost,KillMode,SendSIGKILL,Restart,RuntimeMaxUSec,Slice,NeedDaemonReload'],check=True,capture_output=True,text=True,timeout=10)
 props=dict(row.split('=',1) for row in result.stdout.strip().splitlines())
 assert props['LoadState']=='loaded' and props['ActiveState']=='inactive' and props['SubState']=='dead' and props['MainPID']=='0' and props['NeedDaemonReload']=='no'
 assert props['KillMode']=='control-group' and props['SendSIGKILL']=='yes' and props['Restart']=='no' and props['Slice']=='-.slice'
 assert digest in props['ExecStart'];rows[name]=props
assert not os.path.lexists(execution.ROOT)
print(json.dumps(dict(status='FIXED_S180_UNITS_LOADED_NOT_STARTED',source_revision=profile['source_revision'],operator_profile_sha256=digest,units=rows,verify_stderr=checked.stderr,operational_window_started=False,qualification_performed=False),sort_keys=True,indent=2))
