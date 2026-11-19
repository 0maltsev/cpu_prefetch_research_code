"""D287 finite software-only cross-UID/root-death recovery check."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29')
sys.path.insert(0, str(ROOT/'admission-root/tools'))
sys.path.insert(0, str(HERE))
import stage17_locked_compaction_guard_v1 as guard
import stage17_q16c_compaction_integration_v1 as integration

if sys.argv[1] == 'owner':
    assert os.getuid() == os.geteuid() == 1000
    witness = integration.ReadOnlyWitness(json.loads(sys.argv[3]), int(sys.argv[2]))
    observations = integration.Observations(witness, HERE/'owner-observations-parent/observations',
        request_sha256='a'*64, plan_sha256='b'*64, capture_count=1)
    observations.before_capture(0)
    observations.after_capture(0, dict(software_test=True))
    observations.complete()
    print('OWNER_WITNESS_AND_SYNTHETIC_CAPTURE_PASS', flush=True)
    time.sleep(20)  # Remains inside the owned systemd group when supervisor dies.
else:
    assert os.geteuid() == 0
    status = subprocess.check_output(['systemctl','show',
        'cpu-prefetch-q16c-d285-continuation-v29-1.service',
        'cpu-prefetch-recovery-v29-qualified-1.service','-p','MainPID','--value'], text=True)
    assert set(status.split()) == {'0'}
    os.sched_setaffinity(0, {3})
    held = guard.Guard(HERE/'check', deadline_ns=time.monotonic_ns()+15*10**9).__enter__()
    description, fd = integration.export_witness(held)
    child = None
    try:
        child = subprocess.Popen(['/usr/bin/setpriv','--reuid=1000','--regid=1000','--clear-groups',
            '--bounding-set=-all','--inh-caps=-all','--ambient-caps=-all',
            '/usr/bin/python3','-B',str(Path(__file__).resolve()),'owner',str(fd),json.dumps(description)],
            pass_fds=(fd,),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ready,_,_ = select.select([child.stdout],[],[],5)
        assert ready, 'bounded owner readback timed out'
        line=child.stdout.readline(4096)
        assert line==b'OWNER_WITNESS_AND_SYNTHETIC_CAPTURE_PASS\n', repr(line)
        report=dict(schema_version='cpu-prefetch-d287-software-owner-death/1',
            software_only=True, root_pid=os.getpid(), root_start_ticks=integration.process_identity(os.getpid()),
            child_pid=child.pid, child_start_ticks=integration.process_identity(child.pid),
            actual_child_uid=1000, child_capabilities='none', witness=description,
            expected_failure='SIGKILL_ROOT_SUPERVISOR', experiments_started=0)
        guard.publish(HERE/'fault-intent.json',report)
        print(json.dumps(report,sort_keys=True),flush=True)
        os.kill(os.getpid(),signal.SIGKILL)
    except BaseException:
        if child is not None:
            child.kill()
            child.communicate(timeout=3)
        held.__exit__(None,None,None)
        raise
    finally:
        os.close(fd)
