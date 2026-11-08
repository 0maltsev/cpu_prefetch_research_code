"""One finite reviewed E24 qualification packet; never launches formal Q16.

--prerequisites admits EXT001/2/3/6. --qualify requires those actual admissions,
then runs near/far and one persistent Q15-R/W, retaining isolation on success.
Stop prefix/package analysis before --qualify. There is no retry entry point.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

# Preserve the installed packet. This bounded driver is separately byte-bound.
INSTALLED_PACKET = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-24/operator-preparation-v24')
INSTALLER_SHA256 = 'd5c121ca95b2afa7e714ad3858093b4de51d9d235cb419c2275a557113468e77'

def verify_packet(packet, inventory_sha, **arguments):
    import importlib.util
    path = packet / 'install_v24.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != INSTALLER_SHA256:
        raise RuntimeError('frozen packet verifier changed')
    spec = importlib.util.spec_from_file_location('frozen_e24_packet_verifier', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_packet(packet, inventory_sha, **arguments)

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-24')
P=E/'operator-preparation-v24'


def require(ok,msg):
    if not ok:raise RuntimeError(msg)


def retain(name,value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    fd=os.open(E/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o400)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.chown(E/name,1000,1000)
    fd=os.open(E,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def wait_result(path,process,deadline):
    # Producers publish small JSON directly. Allow incomplete publication only
    # while its owning process is alive, under the unchanged finite deadline.
    while True:
        require(time.monotonic()<deadline,'qualification result deadline expired: '+str(path))
        try:
            return json.loads(path.read_bytes())
        except (FileNotFoundError,json.JSONDecodeError):
            code=process.poll()
            if code is not None:
                # Re-read after exit: a completed file may have appeared between
                # our first read and poll. Missing/malformed final bytes fail.
                try:
                    return json.loads(path.read_bytes())
                except (FileNotFoundError,json.JSONDecodeError) as error:
                    raise RuntimeError('persistent Q15 session exited without a complete result: '+str(code)) from error
            time.sleep(min(0.1,max(0.0,deadline-time.monotonic())))


class Packet:
    def __init__(self,inventory,finite):
        self.files={row['path']:row for row in inventory['files']}
        self.deadline=time.monotonic()+finite['qualification_budget_seconds']
        self.cleanup_seconds=finite['q15_quiescence_seconds']
        self.session=None

    def argv(self,name):
        require(name in self.files,'unbound operator')
        raw=(P/name).read_bytes();row=self.files[name]
        require(len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'operator changed')
        return ['/usr/bin/python3','-B',str(P/name)]

    def remaining(self):
        result=self.deadline-time.monotonic()
        require(result>0,'finite whole qualification deadline expired')
        return result

    def step(self,name):
        argv=self.argv(name)
        result={'operator':name,'argv':argv,'started_monotonic_ns':time.monotonic_ns(),'retry_allowed':False}
        process=None
        try:
            with (E/(name+'.log')).open('xb') as log:
                self.remaining()  # Deadline must hold before starting any child.
                process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                         start_new_session=True,close_fds=True)
                try:
                    code=process.wait(timeout=self.remaining())
                except BaseException:
                    # Foreground operators handle their own clock child cleanup.
                    # The separately owned persistent Q15 supervisor is never killed here.
                    if process.poll() is None:
                        os.killpg(process.pid,signal.SIGTERM)
                        process.wait(timeout=self.cleanup_seconds)
                    raise
                require(code==0,name+' failed with exit '+str(code))
        finally:
            result.update(completed_monotonic_ns=time.monotonic_ns(),
                          exit_code=process.returncode if process is not None else None,
                          leader_reaped=process is not None and process.returncode is not None)
            retain(name+'.result.json',result)

    def qualify(self,isolation):
        session_log=None
        with isolation.qualification_guard(quiescence_timeout_seconds=self.cleanup_seconds):
            try:
                self.step('run_clock_qualification_v24.py')
                self.step('v24-clock-envelope-and-inventory.py')
                self.step('v24-prepare-q15r.py')
                # Exactly one persistent controller, retained until W or its
                # own qualified failure/recovery path completes.
                argv=self.argv('v24-start-q15-session.py')
                session_log=(E/'q15-session-console-1.log').open('xb')
                self.remaining()  # No Q15 invocation after the finite deadline.
                self.session=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=session_log,
                    stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
                retain('q15-owned-session-pid-1.json',dict(pid=self.session.pid,argv=argv,retry_allowed=False))
                result=wait_result(E/'stage17-q15-r-result-v4.json',self.session,self.deadline)
                require(result['terminal_state']=='Q15_R_READ_ONLY_COMPLETE' and result['quarantined'] is False,
                        'Q15-R actual terminal result failed')
                wait_result(E/'stage17-q15-session-waiting-v1.json',self.session,self.deadline)
                self.step('v24-author-admit-ext004.py')
                self.step('v24-prepare-continue-q15w.py')
                result=wait_result(E/'stage17-q15-w-result-v4.json',self.session,self.deadline)
                require(result['terminal_state']=='Q15_W_RESTORED_COMPLETE'
                        and result['restoration_verified'] is True and result['quarantined'] is False,
                        'Q15-W actual restoration failed')
                wait_result(E/'stage17-q15_w-completion-v4.json',self.session,self.deadline)
                require(self.session.wait(timeout=self.remaining())==0,'persistent Q15 supervisor failed')
                self.step('v24-admit-ext005.py')
                isolation.retain_q15w_handoff(quiescence_timeout_seconds=120)
            finally:
                if self.session is not None:
                    # Even an external signing/admission failure must allow the
                    # original finite Q15 supervisor to restore before infra cleanup.
                    cleanup_error=None
                    if self.session.poll() is None:
                        try:self.session.wait(timeout=self.cleanup_seconds)
                        except BaseException as error:cleanup_error=repr(error)
                    retain('q15-owned-session-terminal-1.json',dict(pid=self.session.pid,
                        exit_code=self.session.returncode,leader_reaped=self.session.returncode is not None,
                        cleanup_error=cleanup_error))
                if session_log is not None:session_log.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prerequisites',action='store_true');mode.add_argument('--qualify',action='store_true')
    p.add_argument('--packet-inventory-sha256',required=True)
    p.add_argument('--driver-sha256',required=True)
    args=p.parse_args()
    require(os.geteuid()==0,'reviewed root qualification driver required')
    require(Path(__file__).resolve().parent==E/'continuation-operators-1','separate E24 bounded driver directory required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.driver_sha256,'checked driver bytes differ')
    inventory=verify_packet(P,args.packet_inventory_sha256,installed=True)
    finite=json.loads((P/'finite-qualification-plan.json').read_bytes())
    os.sched_setaffinity(0,{3})
    def interrupted(number,frame):raise RuntimeError('qualification signal '+str(number))
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,interrupted)
    phase='qualification-prerequisites' if args.prerequisites else 'qualification-family'
    retain(phase+'-intent-1.json',dict(pid=os.getpid(),packet_inventory_sha256=args.packet_inventory_sha256,
           qualification_budget_seconds=finite['qualification_budget_seconds'],driver_sha256=args.driver_sha256,automatic_retries=0,
           formal_capture_started=False,shared_archive_program_modified=False))
    packet=Packet(inventory,finite)
    try:
        if args.prerequisites:
            packet.step('v24-ext001-execute.py')
            packet.step('v24-admit-002-003-006.py')
        else:
            sys.path.insert(0,str(P))
            import run_clock_qualification_v24 as isolation
            packet.qualify(isolation)
        retain(phase+'-complete-1.json',dict(success=True,formal_capture_started=False,
               isolation_retained_for_formal=bool(args.qualify)))
    except BaseException as error:
        retain(phase+'-failure-1.json',dict(error=repr(error),automatic_retry=False,formal_capture_started=False))
        raise


if __name__=='__main__':main()
