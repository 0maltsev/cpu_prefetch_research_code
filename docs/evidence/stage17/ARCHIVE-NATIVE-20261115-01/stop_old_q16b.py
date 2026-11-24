"""Owner-authorized D252 interruption at a fully archived capture boundary."""
import datetime,hashlib,json,os,pathlib,select,signal,time
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');F=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1/working/ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702';OUT=E/'q16b-archive-upgrade-stop-1';PID=197428;PARENT=196367

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,d):
 raw=json.dumps(d,sort_keys=True,separators=(',',':')).encode()
 with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(OUT,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def terminal():return any((F/n).exists() for n in ['stage17-q16b-completion-v6.json','stage17-q16b-failure-v6.json'])
assert os.geteuid()==0 and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
assert not OUT.exists() and not terminal();OUT.mkdir(mode=0o700)
p=pathlib.Path('/proc')/str(PID);fd=os.pidfd_open(PID);poll=select.poll();poll.register(fd,select.POLLIN)
assert hashlib.sha256((p/'exe').read_bytes()).hexdigest()=='7abf4cfac0051103f98b3f63f37efd1bde757d954c973460be6fe4d245f6a275'
assert 'PPid:\t'+str(PARENT) in (p/'status').read_text()
intent=dict(reason='OWNER_REQUESTED_ARCHIVE_UPGRADE',decision='D252',utc=utc(),native_pid=PID,native_pidfd_pinned=True,authorization='owner explicitly permits current Q16b restart from beginning after archive optimization',new_attempt_automatic_retry=False,historical_raw_deletion=False)
save('intent.json',intent)
end=time.monotonic()+2100;sent=False
while time.monotonic()<end:
 if terminal() or poll.poll(0):raise RuntimeError('Original attempt ended before upgrade stop; preserve actual terminal cause, no automatic restart')
 checkpoints=list(F.glob('formal-capture-*-final-checkpoint.json'));receipts=list(F.glob('formal-capture-*-archive-custody.json'))
 cp={int(x.name.split('-')[2]) for x in checkpoints};rs={int(x.name.split('-')[2]) for x in receipts}
 children=set()
 for task in pathlib.Path('/proc',str(PARENT),'task').iterdir():children.update(int(x) for x in (task/'children').read_text().split())
 if cp and cp==rs and children=={PID}:
  last=max(rs);d=json.loads((F/f'formal-capture-{last}-archive-custody.json').read_text());assert d['status']=='ARCHIVED_AND_RELEASED'
  assert not poll.poll(0) and not terminal()
  signal.pidfd_send_signal(fd,signal.SIGTERM,None,0);sent=True
  save('signal.json',dict(utc=utc(),signal='SIGTERM',target_native_pid=PID,checkpoint_count=len(cp),archived_capture_count=len(rs),last_capture_ordinal=last,owner_child_set=sorted(children),one_signal_only=True))
  break
 time.sleep(1)
assert sent,'No safe archive boundary reached within finite wait; nothing signalled'
os.close(fd)
end=time.monotonic()+600
while time.monotonic()<end:
 result=E/'formal-q16b-launch-1/supervisor-result.json'
 if result.exists():
  d=json.loads(result.read_text());save('observed-supervisor-result.json',d)
  failure=F/'stage17-q16b-failure-v6.json'
  if failure.exists():save('original-failure-receipt.json',json.loads(failure.read_text()))
  save('stop-result.json',dict(utc=utc(),status='OWNER_REQUESTED_STOP_TERMINAL_RECEIPT_OBSERVED',signal_sent=True,original_supervisor_receipt=str(result),native_process_absent=not p.exists(),supervisor_success=d.get('success'),child_reaped=d.get('child_reaped'),hardware_restoration_verified=d.get('hardware_restoration_verified'),partition_restoration=d.get('partition_restoration'),original_error_preserved=True,automatic_restart=False))
  print('OWNER_REQUESTED_STOP_RECEIPTS_SAVED',flush=True);break
 time.sleep(1)
else:raise RuntimeError('Stop signal sent; terminal restoration receipt not observed in 600sec; inspect without retry')
