"""Bounded parallel synthetic page timing; no research observations."""
import datetime,hashlib,json,os,signal,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
cores={}
for cpu in sorted(os.sched_getaffinity(0)):
 p=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology');pair=tuple(int((p/name).read_text()) for name in ('physical_package_id','core_id'))
 cores.setdefault(pair,cpu)
cpus=list(cores.values())[:12];assert len(cpus)==12
children=[];results=[];started=time.monotonic_ns()
try:
 for cpu in cpus:
  p=subprocess.Popen(['/usr/bin/taskset','-c',str(cpu),'/usr/bin/python3.14','-B',str(ROOT/'page-concurrent-worker.py')],
   stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
  children.append((cpu,p))
 for cpu,p in children:
  remaining=170-(time.monotonic_ns()-started)/1e9;assert remaining>0
  out,err=p.communicate(timeout=remaining);assert p.returncode==0 and len(out)<=16384 and len(err)<=16384,(cpu,p.returncode,err[-2048:])
  row=json.loads(out);assert row['cpu_affinity']==[cpu] and row['synthetic_files_removed'] is True
  results.append(dict(cpu=cpu,leader_reaped=True,result=row))
finally:
 for cpu,p in children:
  if p.poll() is None:os.killpg(p.pid,signal.SIGKILL)
  p.wait(timeout=5)
print(json.dumps(dict(schema_version='cpu-prefetch-stage17-s180-software-packed-pages-concurrency/1',
 utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),results=results,physical_cpus=cpus,
 including_source_verification_preparation_ns=time.monotonic_ns()-started,
 maximum_actual_parse_and_exact_check_ns=max(r['result']['packed_parse_ns']+r['result']['exact_residency_values_ns'] for r in results),
 all_children_reaped=True,software_only=True,whole_control_validation_timed=False,whole_family_timing=False,
 research_raw_read=False,scientific_source_generated=False,qualification_performed=False,operational_window_started=False,
 execution_authority=False,phase18_authority=False),sort_keys=True))
