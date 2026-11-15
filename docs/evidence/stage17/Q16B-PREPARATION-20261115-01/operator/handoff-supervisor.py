"""Bounded one-shot D247 administrative supervisor; no experimental action."""
import datetime, json, os, pathlib, signal, subprocess, time
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
packet=E/'q16b-handoff-operators-1';control=E/'q16b-handoff-launch-1'
assert os.getuid()==os.geteuid()==1000
assert not control.exists()
control.mkdir(mode=0o700)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,value):
 with (control/name).open('x') as f:
  json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(control,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
start=now();child=None;error=None;status=None
try:
 with (control/'operator.log').open('xb') as log:
  argv=['/usr/bin/python3.14','-B',str(packet/'prepare_stage17_q16a_handoff_v1.py'),'--output-root',str(E/'q16b-handoff-preparation-1')]
  child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  save('started.json',dict(started_at_utc=start,pid=child.pid,supervisor_pid=os.getpid(),argv=argv,wall_limit_seconds=1800,execution_authority=False))
  try:status=child.wait(timeout=1800)
  except subprocess.TimeoutExpired:
   error='administrative wall timeout';os.killpg(child.pid,signal.SIGTERM)
   try:status=child.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);status=child.wait()
except BaseException as e:
 error=type(e).__name__+': '+str(e)
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGKILL);status=child.wait()
save('process-result.json',dict(started_at_utc=start,completed_at_utc=now(),exit_code=status,error=error,child_reaped=child is not None and child.returncode is not None,raw_redecode_performed=False,new_collection_performed=False,execution_authority=False))
