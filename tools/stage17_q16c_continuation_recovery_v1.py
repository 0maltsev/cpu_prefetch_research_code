"""Independent D288 StopPost; native-before-owner cleanup and actual restoration.

No experiment, retry, qualification or window entry exists. All process signals
use retained PID start ticks and actual candidate executable identities.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time

import stage17_q16c_continuation_operator_v1 as io
import stage17_q16c_continuation_study_v1 as study


def live(h,pid,ticks):
    try:
        raw=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
        return raw[0] not in ('Z','X','x') and h.start_ticks(pid)==ticks
    except (FileNotFoundError,ProcessLookupError):return False


def recover(args,c,h):
    io.require(os.geteuid()==0,'independent root recovery')
    root=study.E/'d288-study-1';output=study.E/'d288-independent-recovery-1.json'
    io.require(not output.exists(),'one independent recovery receipt')
    result=dict(verified=False,errors=[],signalled_native=[],signalled_owner=[],execution_authority=False,phase18_authority=False)
    try:
        if not root.exists():
            result.update(verified=True,reason='NO_STUDY_STARTED');return result
        intent_path=root/'intent.json'
        if intent_path.exists():
            intent=io.document(io.binding(intent_path))
            io.require(intent['configuration_sha256']==args.configuration_sha256,'actual root study identity')
            io.require(not live(h,intent['supervisor_pid'],intent['supervisor_start_ticks']),'original supervisor still live')
        snapshot=root/'owned-process-snapshot.json';owned={}
        if snapshot.exists():
            d=io.document(io.binding(snapshot));io.require(d['configuration_sha256']==args.configuration_sha256,'owned process snapshot identity')
            owned={row['pid']:row['start_ticks'] for row in d['processes']}
            owned[d['owner_pid']]=d['owner_start_ticks']
        for pid,ticks in tuple(owned.items()):
            if live(h,pid,ticks):owned.update(h.descendants(pid))
        # Qualification helpers and a forked restoration can outlive their root
        # parent without appearing in the collection owner's last snapshot.
        # Inspect only the original dedicated service inode and known script
        # arguments; never use a host-wide Python/process-name search.
        if intent_path.exists() and 'root_service_cgroup' in intent:
            service=Path(intent['root_service_cgroup']['path'])
            io.require(service.name==c['supervisor_unit'] and service.is_relative_to('/sys/fs/cgroup'),
                'original dedicated root service namespace')
            st=service.stat(follow_symlinks=False)
            io.require([st.st_dev,st.st_ino]==intent['root_service_cgroup']['identity'],'original root service inode')
            own={os.getpid(),*h.descendants(os.getpid())}
            scripts={b['path']:b for b in c['operator_sources'].values() if b['path'].endswith('.py')}
            qroot=Path(c['qualification_packet']);q=io.document(c['qualification_inventory'])
            scripts.update({str(qroot/r['path']):dict(r,path=str(qroot/r['path'])) for r in q['files'] if r['path'].endswith('.py')})
            for text in (service/'cgroup.procs').read_text().split():
                pid=int(text)
                if pid in own:continue
                ticks=h.start_ticks(pid)
                argv=Path('/proc/'+text+'/cmdline').read_bytes().split(b'\0')
                args=[a.decode() for a in argv if a]
                matches=[name for name in scripts if name in args]
                io.require(bool(matches),'unrecognised root-service survivor')
                for name in matches:io.read(scripts[name])
                owned[pid]=ticks;owned.update(h.descendants(pid))
        prep=study.E/'isolation-preparation-v30-1/prospective-prestate.json'
        cg=Path(c['cgroup']);actual_pre=None
        if prep.exists():
            actual_pre=io.document(io.binding(prep))
            io.require(actual_pre['operator_config']==io.document(c['qualification_isolation_configuration']),
                'actual bound isolation configuration')
            if cg.exists():
                st=cg.stat(follow_symlinks=False)
                io.require([st.st_dev,st.st_ino]==actual_pre['prestate']['partition_identity'],'original managed partition identity')
                for text in (cg/'cgroup.procs').read_text().split():
                    pid=int(text);ticks=h.start_ticks(pid)
                    # A native child can be born just before its root owner dies.
                    # Only the exact dedicated partition + UID + executable can
                    # add it beyond the already persisted descendant snapshot.
                    if pid not in owned:
                        status=Path('/proc/'+text+'/status').read_text()
                        uid=next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1:]
                        images={(b['size_bytes'],b['sha256']) for b in c['native_images']}
                        argv=Path('/proc/'+text+'/cmdline').read_bytes().split(b'\0')
                        args=[a.decode() for a in argv if a]
                        controller=str(Path(c['repository_root'])/'tools/stage17_q15_session_controller_daycap_v5.py')
                        qualified_owner=(controller in args and '--operational-evidence-root' in args
                            and args[args.index('--operational-evidence-root')+1]==str(study.E))
                        if qualified_owner:
                            rows=[r for r in io.document(c['candidate_inventory'])['files'] if r['path']=='tools/stage17_q15_session_controller_daycap_v5.py']
                            io.require(len(rows)==1,'one qualified Q15 owner source')
                            io.read(dict(rows[0],path=controller))
                        io.require(uid==['1000']*4 and (h.executable_identity(pid) in images or qualified_owner),
                            'unrecognised live partition member')
                        owned[pid]=ticks
        native={(b['size_bytes'],b['sha256']) for b in c['native_images']}
        native_pids={}
        for pid,ticks in owned.items():
            if live(h,pid,ticks) and h.executable_identity(pid) in native:
                h.send_pidfd(pid,ticks,signal.SIGTERM,native=native);native_pids[pid]=ticks
                result['signalled_native'].append(dict(pid=pid,start_ticks=ticks,signal='SIGTERM'))
        end=time.monotonic_ns()+2400*10**9
        grace=min(end,time.monotonic_ns()+2100*10**9)
        while time.monotonic_ns()<grace and any(live(h,p,t) for p,t in owned.items()):
            # The persistent Q15 supervisor/native executor gets its original
            # finite recovery opportunity before the Python owner is touched.
            if all(not live(h,p,t) for p,t in native_pids.items()):
                if not any(live(h,p,t) for p,t in owned.items()):break
            time.sleep(.1)
        for pid,ticks in native_pids.items():
            if live(h,pid,ticks):
                h.send_pidfd(pid,ticks,signal.SIGKILL,native=native)
                result['errors'].append('forced native cleanup '+str(pid))
        for sig,seconds in ((signal.SIGTERM,10),(signal.SIGKILL,10)):
            for pid,ticks in owned.items():
                if live(h,pid,ticks):
                    h.send_pidfd(pid,ticks,sig);result['signalled_owner'].append(dict(pid=pid,start_ticks=ticks,signal=sig.name))
            until=min(end,time.monotonic_ns()+seconds*10**9)
            while time.monotonic_ns()<until and any(live(h,p,t) for p,t in owned.items()):time.sleep(.05)
        io.require(not any(live(h,p,t) for p,t in owned.items()),'owned processes remain live')
        io.require(not cg.exists() or (cg/'cgroup.procs').read_text().strip()=='','managed native partition remains populated')
        sys.path.insert(0,str(Path(c['repository_root'])/'tools'))
        import stage17_hardware_recovery_v1 as hardware
        state_path=root/'msr-prestate.json'
        if state_path.exists():
            state=io.document(io.binding(state_path))
            io.require(state['mapping_id']==hardware.MAPPING_ID and [r['cpu'] for r in state['prestate']]==[0,1,8],
                'actual three-CPU original prestate')
            values=tuple((r['cpu'],int(r['complete_value_hex'],16)) for r in state['prestate'])
            io.require(all(r['complete_value_hex']==f'{v:016x}' for r,(_,v) in zip(state['prestate'],values,strict=True)),'canonical complete MSR prestate')
            if (study.E/'platform-guard-1/intent.json').exists():hardware.restore(values)
            result['msr_readback']=hardware.verify(values)
        if actual_pre is not None:
            adapter=study.module('d288_independent_isolation',c['clock_adapter'])
            receipt=adapter.Q/'restoration.json'
            if not receipt.exists():adapter.restore(actual_pre['prestate'])
            io.require(io.document(io.binding(receipt))['verified'] is True and not adapter.CG.exists()
                and adapter.root_state()==actual_pre['prestate']['root'],'actual independent isolation restoration')
            for name,before in actual_pre['prestate']['maintenance_before'].items():
                observed=adapter.ISO.systemd_state(name)
                io.require(observed['UnitFileState']==before['UnitFileState'] and (name not in adapter.ISO.TIMER_SERVICES
                    or observed['ActiveState']==before['ActiveState']),'actual independent maintenance restoration')
            result['isolation_restoration']=io.binding(receipt)
        guard=study.E/'platform-guard-1'
        if (guard/'intent.json').exists():
            import stage17_locked_compaction_guard_v1 as controls
            result['compaction']=controls.recover(guard)
        result['verified']=not result['errors']
    except BaseException as error:result['errors'].append(repr(error))
    finally:io.save(output,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    args=p.parse_args();c,h=study.configure(args);result=recover(args,c,h)
    print(json.dumps(result),flush=True);io.require(result['verified'],'independent recovery incomplete; retain evidence')


if __name__=='__main__':main()
