"""Read-only existing program accounting; no registration or ledger writes."""
import dataclasses,datetime,hashlib,json,os,pathlib,resource,sys,time
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
R=E/'admission-root';B=E/'local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a'
assert os.getuid()==os.geteuid()==1000
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
assert hashlib.sha256((B/'BUNDLE_INVENTORY.json').read_bytes()).hexdigest()=='8e657978d848ae8c633036536357741fff02388788b0f6a18f2e13e5dc6d5397'
rows={r['path']:r for r in json.loads((B/'BUNDLE_INVENTORY.json').read_bytes())['files']}
for name in ['stage17_formal_archive_custody_v1.py','stage17_formal_archive_v1.py','check_canonical.py']:
 p=R/'tools'/name;d=p.read_bytes();expected=rows['tools/'+name]
 assert len(d)==expected['size_bytes'] and hashlib.sha256(d).hexdigest()==expected['sha256']
sys.path.insert(0,str(R/'tools'));import stage17_formal_archive_custody_v1 as custody
P=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1'
out=E/'q16b-program-capacity-1.json';assert not out.exists()
limits=custody.CustodyLimits(1048576,1000000,1000000,1048576,time.monotonic_ns()+1800*10**9)
with custody.ProgramStore(P,scope_sha256='4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2',family_id='91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2',limits=limits) as store:
 used=store.physical_accounting();remaining=custody.PROGRAM_QUOTA-used.quota_bytes
 ledger=dataclasses.asdict(store.ledger_binding());v=os.statvfs(P)
 free=v.f_bavail*v.f_frsize;required=remaining+custody.WORKSPACE+custody.SCRATCH+custody.RESERVE
 result=dict(status='READ_ONLY_PROGRAM_CAPACITY_OBSERVED',observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),program_root=str(P),program_id=store.scope['program_id'],scope_sha256=store.scope_sha256,families=len(store._families),ledger=ledger,physical_usage=dataclasses.asdict(used),reserved_bytes=store.reserved_bytes(),remaining_program_quota_bytes=remaining,filesystem_available_bytes=free,filesystem_available_inodes=v.f_favail,remaining_quota_plus_workspace_scratch_reserve_bytes=required,disk_requirement_satisfied=free>=required,boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),mem_available_line=[s for s in pathlib.Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')][0],registration_performed=False,ledger_mutation=False,raw_mutation=False,execution_authority=False)
 with out.open('x') as f:
  json.dump(result,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 print(json.dumps(result,sort_keys=True))
