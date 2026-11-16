import datetime,hashlib,json,os,pathlib,subprocess,time
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27');B=E.parent/'v27-bootstrap-1';O=E/'d267-admission-preparation-3';S=E/'d260-study-1';P=E/'d260-configuration-3';F=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1/working/1ccafebafafea4b8491b4daf5b70f1065d1ea2c0b854d662bae388bfb031b2ba'
files={}
paths=[B/'collection-launch-intent-1.json',B/'collection-launch-result-1.json',B/'d268-operator-publication.json',B/'signed-preparation-2.log',E/'continuation-window-1.json',P/'manifest.json',P/'cli-configuration.json',O/'constructed-phase.json',O/'prepared-phase.json',O/'supersession-intent.json',O/'signing-result.json',O/'authority-supersession-complete.json',S/'study-intent.json',S/'isolation-rearm.json',S/'check-result.json',S/'check.log',S/'collection-intent.json',S/'collection-result.json',S/'study-result.json',S/'partition-restoration.json',E/'isolation-preparation-v27-resume-1/prospective-prestate.json',E/'isolation-preparation-v27-resume-1/isolation-ready.json',F/'stage17-q16b-attempt-v6.json',F/'stage17-q16b-completion-v6.json',F/'stage17-q16b-failure-v6.json']
for p in paths:
 if not p.exists():continue
 assert not p.is_symlink() and p.stat().st_size<=131072,str(p)
 raw=p.read_bytes();row=dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 row['document' if p.suffix=='.json' else 'text']=json.loads(raw) if p.suffix=='.json' else raw.decode()
 files[str(p)]=row
units={}
for name in ['cpu-prefetch-q16b-v27-study-1.service','cpu-prefetch-recovery-v27-qualified-1.service','cpu-prefetch-d268-v27-signing-preparation-2.service']:
 result=subprocess.run(['systemctl','show',name,'-p','ActiveState','-p','SubState','-p','MainPID','-p','Result','-p','ExecMainStatus','-p','ControlGroup','-p','InvocationID'],check=True,capture_output=True,text=True)
 units[name]=dict(line.split('=',1) for line in result.stdout.splitlines())
workers=[]
prepared=json.loads((O/'prepared-phase.json').read_bytes());expected=prepared['worker']
cg=pathlib.Path('/sys/fs/cgroup/cpu-prefetch-recovery-v27-qualified-1.service/reserved')
for token in (cg/'cgroup.procs').read_text().split() if cg.exists() else []:
 p=pathlib.Path('/proc')/token
 try:
  exe=p/'exe'
  if exe.stat().st_size!=expected['size_bytes']:continue
  with exe.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
  if digest!=expected['sha256']:continue
  status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
  workers.append(dict(pid=int(token),executable=os.readlink(exe),size_bytes=exe.stat().st_size,sha256=digest,uid=status['Uid'].strip(),cgroup=(p/'cgroup').read_text().strip(),allowed_cpus=status['Cpus_allowed_list'].strip(),capabilities={k:status[k].strip() for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')}))
 except (FileNotFoundError,ProcessLookupError,PermissionError):continue
print(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observed_monotonic_ns=time.monotonic_ns(),files=files,units=units,native_workers=workers,new_archived_captures=len(list(F.glob('formal-capture-*-archive-custody.json'))),retained_validated_prefix=17,completed_q16a_preserved=708,raw_transferred=False,automatic_retry=False),sort_keys=True,indent=2))
