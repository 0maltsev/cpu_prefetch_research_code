"""One detached setup-to-launch handoff; no retry and no repeated experiment."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import types

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
OPERATORS=E/'q16b-launch-admission-1'
CONTROL=E/'q16b-setup-and-launch-1'
LAUNCH=E/'formal-q16b-launch-1'
ISOLATION=E/'isolation-preparation-v25-q16b-1'
CORE=Path('/run/cpu-prefetch-recovery-v25-qualified-1/isolation_core.py')
CORE_SHA='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
OPS_SHA='8326b5a2a6e0ec97ccf7cd9671756ba78b15cd9d35e3dc047b7bdb9c1a62915a'
PACKET_SHA='6c38b37e2b6b326d4f3f53fc06f7a478d452f32445f5481cf201c693f1125842'
PRE_SHA='2db4452a66f5182b0e13459d29b8856c340268362774c7df7a43cd2bb6f3a2cf'
AS=240518168576
LOCK=30709854208

def wrapper_owns_restore(setup_completed, launch_root_exists):
    # Once launch() creates its exclusive root, its finally/supervisor owns
    # restoration even if publishing the detached supervisor PID fails.
    return setup_completed and not launch_root_exists

def save(name,doc):
    raw=json.dumps(doc,sort_keys=True,separators=(',',':')).encode()
    with (CONTROL/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(CONTROL,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def restore_owned_setup():
    existing=ISOLATION/'restoration.json'
    if existing.exists():
        result=json.loads(existing.read_bytes())
        if result.get('verified') is not True:raise ValueError('existing setup restoration is incomplete; no automatic retry')
        return dict(already_restored=True,verified=True)
    path=ISOLATION/'prospective-prestate.json'
    doc=json.loads(path.read_bytes())
    raw=CORE.read_bytes();assert hashlib.sha256(raw).hexdigest()==CORE_SHA
    module=types.ModuleType('q16b_pipeline_owned_restore');module.__file__=str(CORE)
    exec(compile(raw,str(CORE),'exec'),module.__dict__)
    module.configure(doc);module.restore(doc['prestate'])
    result=json.loads(existing.read_bytes());assert result['verified'] is True
    return dict(verified=True,restoration=result)

def main():
    assert os.geteuid()==0 and Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
    assert not CONTROL.exists() and not LAUNCH.exists() and not ISOLATION.exists()
    raw=(OPERATORS/'manifest.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==OPS_SHA
    for row in json.loads(raw)['files']:
        path=OPERATORS/row['name'];data=path.read_bytes();assert not path.is_symlink() and len(data)==row['size_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    assert hashlib.sha256(CORE.read_bytes()).hexdigest()==CORE_SHA
    os.sched_setaffinity(0,{3});CONTROL.mkdir(mode=0o700)
    save('intent.json',dict(started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),prelaunch_configuration_sha256=PRE_SHA,administrative_packet_sha256=PACKET_SHA,operator_packet_sha256=OPS_SHA,automatic_retry=False,measurements_repeated=False))
    sys.path.insert(0,str(OPERATORS))
    import formal_launch_q16b as launch
    import reapply_isolation_q16b as setup
    import render_q16b_config as render
    setup_completed=False;error=None;restore=None;handoff=False
    try:
        pre_args=argparse.Namespace(config=OPERATORS/'prelaunch-config.json',config_sha256=PRE_SHA,address_space_bytes=AS,memlock_bytes=LOCK)
        c=launch.read_config(pre_args)
        result=setup.prepare(c,pre_args)
        setup_completed=True;save('setup-result.json',result)
        print('Q16B_SETUP_VERIFIED',flush=True)
        current=render.render('launch',PACKET_SHA);encoded=launch.canonical(current)
        path=OPERATORS/'launch-config.json';render.exclusive(path,encoded);os.chown(path,1000,1000)
        digest=hashlib.sha256(encoded).hexdigest();save('launch-config-binding.json',dict(path=str(path),size_bytes=len(encoded),sha256=digest))
        args=argparse.Namespace(config=path,config_sha256=digest,address_space_bytes=AS,memlock_bytes=LOCK)
        launch.launch(launch.read_config(args),args)
        handoff=True;save('handoff.json',dict(supervisor=json.loads((LAUNCH/'supervisor-pid.json').read_bytes()),launch_config_sha256=digest,experiment_started='NOT_ASSESSED_BY_TRANSACTION',supervisor_owns_restoration=True))
    except BaseException as e:
        error=dict(type=type(e).__name__,message=str(e))
    finally:
        for number in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(number,signal.SIG_IGN)
        if wrapper_owns_restore(setup_completed or (ISOLATION/'prospective-prestate.json').is_file(),LAUNCH.exists()):
            try:restore=restore_owned_setup()
            except BaseException as e:restore=dict(verified=False,type=type(e).__name__,message=str(e))
        elif (ISOLATION/'restoration.json').exists():
            restore=json.loads((ISOLATION/'restoration.json').read_bytes())
        save('transaction-result.json',dict(completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),setup_completed=setup_completed,supervisor_handoff=handoff,launch_root_exists=LAUNCH.exists(),error=error,restoration=restore,automatic_retry=False,experiment_success='NOT_ASSESSED'))
    if error:raise RuntimeError(error)
    print('Q16B_SUPERVISOR_HANDOFF_COMPLETE',flush=True)

if __name__=='__main__':main()
