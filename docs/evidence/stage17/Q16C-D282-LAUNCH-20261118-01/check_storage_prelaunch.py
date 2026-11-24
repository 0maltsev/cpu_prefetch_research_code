import dataclasses,hashlib,json,os,sys,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');P=E/'q16c-configuration-1';R=E/'admission-root';sys.path.insert(0,str(R/'tools'))
import stage17_formal_archive_custody_v1 as custody
import stage17_fixed_action_executor_v12 as executor
c=json.loads((E/'d282-launch-preparation-1.json').read_bytes());plan=json.loads((P/'plan.json').read_bytes());family=hashlib.sha256((P/'plan.json').read_bytes()).hexdigest();root=Path(c['program_root'])
with custody.ProgramStore(root,scope_sha256=plan['storage']['program_scope_sha256'],family_id=family,limits=executor.custody_limits(plan['storage'],time.monotonic_ns()+120*10**9)) as store:
 assert not store._capture_pending and all(s['kind']=='RELEASED' for s in store._states.values()) and family not in store._families
 tip=dataclasses.asdict(store.ledger_binding());retained=store.physical_usage();reserved=store.reserved_bytes();assert reserved==0
 fs=os.statvfs(root);free=fs.f_bavail*fs.f_frsize;required=custody.PROGRAM_QUOTA-retained+custody.WORKSPACE+custody.SCRATCH+custody.RESERVE
 assert free>=required and fs.f_favail>=100000
 report=dict(status='PASS',old_program_quiescent=True,original_program_reinitialized=False,new_family_registered=False,retained_bytes=retained,reserved_bytes=reserved,free_bytes=free,required_free_bytes=required,free_inodes=fs.f_favail,ledger=tip,source_revision=c['source_revision'],successful_q16c_captures=0,execution_window_started=False)
with (E/'d282-storage-prelaunch-1.json').open('x') as f:json.dump(report,f,sort_keys=True,separators=(',',':'));f.flush();os.fsync(f.fileno())
print(json.dumps(report),flush=True)
