#!/usr/bin/env python3
"""Bound E29 near/far qualification adapter; no retries, no source defaults.

Generated with actual release bindings. The frozen infrastructure core owns
delegation and maintenance. Qualification retains the same partition for the
following formal continuation; no Q15/Q16 invocation occurs on import.
"""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import types

BINDINGS = {'boot_id': '4c08cd05-b362-49dd-b37f-629e9c7ad79a', 'bundle_root': '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29/local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272', 'clock_binary_sha256': 'cb6422db0be2c3ff3b20897bc58ff4b892ba04e34e9f16f93a8b6d5a04caad69', 'continuation_cleanup_ns': 120000000000, 'continuation_watchdog_ns': 47820000000000, 'evidence_root': '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29', 'finite_plan_binding': {'path': '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29/operator-preparation-v29/finite-qualification-plan.json', 'size_bytes': 6386, 'sha256': 'ca36078439caaf73873cbf422cb3a7d898db9ae1940b2ca0251f8bc51707024d'}, 'id_prefix': 'CPU-PREFETCH-V5-V29', 'isolation_config': {'boot_id': '4c08cd05-b362-49dd-b37f-629e9c7ad79a', 'evidence_root': '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29/isolation-preparation-v29-1', 'lifecycle_seconds': 63000, 'protected_work_ns': 55140000000000, 'source_revision': '7fb894425c82fa7d7f1891f52b3bcdacc2c83585', 'stop_seconds': 120, 'unit_name': 'cpu-prefetch-recovery-v29-qualified-1.service'}, 'isolation_operator_binding': {'path': '/run/cpu-prefetch-recovery-v29-qualified-1/isolation_core.py', 'sha256': '49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a', 'size_bytes': 23863}, 'qualification_budget_ns': 7200000000000, 'source_revision': '7fb894425c82fa7d7f1891f52b3bcdacc2c83585'}
ISO = None
E = Q = B = TOOL = CG = ROOT = None
REVISION = BINARY_SHA = BOOT = None
RESERVED = {0, 1, 2, 8, 16, 17, 18, 24}
HOUSEKEEPING = set(range(32)) - RESERVED
CPU_LIST = '0-2,8,16-18,24'
AS_BYTES = 8 * 1024**3
MEMLOCK_BYTES = 8 * 1024**2
CORE_SHA256 = '49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_bytes(binding):
    require(set(binding) == {'path', 'size_bytes', 'sha256'}, 'exact file binding required')
    path = Path(binding['path'])
    require(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'absolute nonsymlink binding required')
    raw = path.read_bytes()
    require(len(raw) == binding['size_bytes'] and hashlib.sha256(raw).hexdigest() == binding['sha256'], 'bound bytes changed')
    return raw


def configure(c):
    global BINDINGS, ISO, E, Q, B, TOOL, CG, ROOT, REVISION, BINARY_SHA, BOOT
    BINDINGS = c
    require(set(c) == {'evidence_root', 'bundle_root', 'source_revision', 'clock_binary_sha256', 'boot_id',
                       'finite_plan_binding', 'isolation_operator_binding', 'isolation_config', 'id_prefix',
                       'qualification_budget_ns', 'continuation_watchdog_ns', 'continuation_cleanup_ns'}, 'clock configuration fields')
    E = Path(c['evidence_root'])
    require(E.name == 'local-authoring-cpuprefetchv5-29' and E.parent == Path('/home/omaltsev/stage17-owner-evidence'), 'fresh E29 root required')
    require(c['id_prefix'] == 'CPU-PREFETCH-V5-V29', 'fresh E29 identity prefix required')
    B = Path(c['bundle_root'])
    require(B.is_relative_to(E / 'local-bundle-extract'), 'actual E29 bundle root required')
    Q = E / 'clock-qualification-v29-1'
    TOOL = B / 'release/bin/cpu_prefetch_q15_clock_qualification_tool'
    REVISION, BINARY_SHA, BOOT = c['source_revision'], c['clock_binary_sha256'], c['boot_id']
    require(c['isolation_operator_binding']['sha256'] == CORE_SHA256, 'cold-proven infrastructure source differs')
    operator = bound_bytes(c['isolation_operator_binding'])
    ISO = types.ModuleType('bound_e24_infrastructure')
    ISO.__file__ = c['isolation_operator_binding']['path']
    exec(compile(operator, ISO.__file__, 'exec'), ISO.__dict__)
    cfg = c['isolation_config']
    require(cfg['unit_name'] == 'cpu-prefetch-recovery-v29-qualified-1.service', 'fresh qualified unit required')
    require(cfg['source_revision'] == REVISION and cfg['boot_id'] == BOOT, 'isolation source/boot differs')
    require(Path(cfg['evidence_root']).is_relative_to(E), 'isolation evidence outside E29')
    for key in ('qualification_budget_ns', 'continuation_watchdog_ns', 'continuation_cleanup_ns'):
        require(type(c[key]) is int and c[key] > 0, 'explicit finite qualification/formal ceilings required')
    require(cfg['lifecycle_seconds'] == 63000, 'explicit D282 keeper lifetime required')
    require(cfg['protected_work_ns'] >= sum(c[k] for k in ('qualification_budget_ns','continuation_watchdog_ns','continuation_cleanup_ns')), 'lifecycle omits qualification/formal ceilings')
    ISO.configure({'operator_config': cfg})
    ROOT, CG = ISO.ROOT, ISO.CG


def read(path): return ISO.read(path)
def cpus(value): return ISO.cpus(value)
def retain(path, value): return ISO.retain(path, value)
def write_control(path, value): return ISO.write_control(path, value)
def root_state(): return ISO.root_state()
def isolated_state(): return ISO.isolated_state()


def preparation():
    path = Path(BINDINGS['isolation_config']['evidence_root']) / 'prospective-prestate.json'
    raw = path.read_bytes()
    pre = json.loads(raw)
    require(pre['operator_config'] == BINDINGS['isolation_config']
            and pre['operator_script_sha256'] == CORE_SHA256
            and pre['source_revision'] == REVISION and pre['boot_id'] == BOOT
            and pre['partition_path'] == str(CG), 'actual isolation preparation differs')
    record = Q / 'prospective-plan.json'
    if record.exists():
        binding = json.loads(record.read_bytes())['isolation_prestate_binding']
        require(bound_bytes(binding) == raw, 'clock-bound preparation changed')
    return pre


def restore(prestate):
    ISO.Q = Q
    return ISO.restore(prestate)


def cleanup_after_external_failure(error, *, quiescence_timeout_seconds):
    """Covers envelope/authoring/signature/admission failures, not just clocks.

    Do not kill a qualified persistent Q15 supervisor: let its existing finite
    recovery path finish. After the explicit wait, infra cleanup itself rejects
    any live partition, yet still attempts owned maintenance restoration.
    """
    require(type(quiescence_timeout_seconds) is int and quiescence_timeout_seconds > 0, 'finite quiescence timeout required')
    pre = preparation()
    result = {'utc': utc(), 'error': repr(error), 'retry_allowed': False,
              'quiescence_timeout_seconds': quiescence_timeout_seconds}
    try:
        wait_partition_empty(quiescence_timeout_seconds)
    except BaseException as wait_error:
        result['quiescence_error'] = repr(wait_error)
    try:
        existing = Q / 'restoration.json'
        if existing.exists():
            old = json.loads(existing.read_bytes())
            require(old['verified'] is True and not CG.exists() and root_state() == pre['prestate']['root'], 'prior cleanup incomplete; no automatic retry')
            result['already_restored'] = True
        else:
            restore(pre['prestate'])
            result['restored'] = True
    except BaseException as cleanup_error:
        result['cleanup_error'] = repr(cleanup_error)
        raise
    finally:
        retain(Q / 'qualification-external-failure.json', result)


@contextlib.contextmanager
def qualification_guard(*, quiescence_timeout_seconds):
    """Outer packet must enclose ALL steps through Q15-W + EXT005 handoff."""
    try:
        yield
    except BaseException as error:
        try:
            cleanup_after_external_failure(error, quiescence_timeout_seconds=quiescence_timeout_seconds)
        except BaseException as cleanup_error:
            raise RuntimeError('qualification failed: '+repr(error)+'; cleanup: '+repr(cleanup_error)) from error
        raise


def wait_partition_empty(seconds):
    require(type(seconds) is int and seconds > 0, 'finite quiescence wait required')
    deadline = time.monotonic() + seconds
    while CG.exists() and read(CG / 'cgroup.procs') and time.monotonic() < deadline:
        time.sleep(0.25)
    require(not CG.exists() or read(CG / 'cgroup.procs') == '', 'partition did not quiesce before timeout')


def retain_q15w_handoff(*, quiescence_timeout_seconds):
    pre = preparation()
    result_path = E / 'stage17-q15-w-result-v4.json'
    completion = E / 'stage17-q15_w-completion-v4.json'
    result = json.loads(result_path.read_bytes())
    require(result['terminal_state'] == 'Q15_W_RESTORED_COMPLETE'
            and result['restoration_verified'] is True and result['quarantined'] is False
            and completion.is_file(), 'actual Q15-W restored completion required')
    wait_partition_empty(quiescence_timeout_seconds)
    state = isolated_state()
    require(state['partition']['cgroup.procs'] == '' and 'populated 0' in state['partition']['cgroup.events'].splitlines(), 'Q15 supervisor not quiescent')
    ISO.verify_remaining_lifetime(pre['prestate'], BINDINGS['continuation_watchdog_ns'], BINDINGS['continuation_cleanup_ns'])
    retain(Q / 'q15w-isolation-handoff.json', {'utc': utc(), 'isolation_retained': True,
           'source_revision': REVISION, 'partition_path': str(CG), 'observation': state,
           'q15w_result_sha256': digest(result_path), 'q15w_completion_sha256': digest(completion),
           'isolation_prestate_sha256': digest(Path(BINDINGS['isolation_config']['evidence_root'])/'prospective-prestate.json')})

def verify_raw(raw, pair):
    require(raw['schema_version'] == 'cpu-prefetch-stage17-q15-clock-pair-raw/1', 'raw schema differs')
    require(raw['pair'] == pair, 'pair differs')
    require((raw['producer_cpu'], raw['consumer_cpu']) == (0, 1 if pair == 'near' else 8), 'CPU identity differs')
    for role in ('producer', 'consumer'):
        require(raw[role + '_prime_read_count'] == 100000, 'prime count differs')
        require(raw[role + '_delta_count'] == 10000000, 'delta count differs')
        require(raw[role + '_pinned'] is True and raw[role + '_per_core_passed'] is True, 'per-core qualification failed')
    for field in ('producer_to_consumer_window_count', 'consumer_to_producer_window_count'):
        require(raw[field] == 3, 'window count differs')
    require(raw['exchanges_per_window'] == 100000 and raw['cross_core_passed'] is True, 'cross-core qualification failed')

def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

def capture(pair):
    directory = Q / pair
    directory.mkdir(mode=0o700)
    os.chown(directory, 1000, 1000)
    before = isolated_state()
    require(before['partition']['cgroup.procs'] == '', 'unexpected partition member before capture')
    retain(directory / 'control-before.json', before)
    raw = directory / 'clock-raw.json'
    argv = [str(TOOL), '--qualify-pair', pair, '--output', str(raw)]
    record = {'capture_id': BINDINGS['id_prefix'] + '-ISOLATED-CLOCK-' + pair.upper() + '-1',
              'command': argv, 'binary_sha256': digest(TOOL), 'source_revision': REVISION,
              'started_at_utc': utc(), 'timeout_seconds': 600,
              'clock_api': 'CLOCK_MONOTONIC_RAW', 'timestamp_units': 'relative picoseconds',
              'scope': 'CURRENT_OWNER_FINITE_RELEASE_QUALIFICATION',
              'control_before_sha256': digest(directory / 'control-before.json')}
    require(record['binary_sha256'] == BINARY_SHA, 'clock binary changed')
    retain(directory / 'clock-capture-intent.json', record)
    def prepare_child():
        write_control(CG / 'cgroup.procs', str(os.getpid()))
        os.sched_setaffinity(0, {2})
        resource.setrlimit(resource.RLIMIT_AS, (AS_BYTES, AS_BYTES))
        require(resource.getrlimit(resource.RLIMIT_MEMLOCK) == (MEMLOCK_BYTES, MEMLOCK_BYTES), 'memlock drift')
        os.setgroups([])
        os.setgid(1000)
        os.setuid(1000)
        require(read('/proc/self/cgroup') == '0::/' + str(CG.relative_to(ROOT)), 'launcher membership differs')
        require(os.sched_getaffinity(0) == {2}, 'launcher CPU differs')
        retain(directory / 'launcher-readback.json', {
            'utc': utc(), 'pid': os.getpid(), 'uid': os.getuid(), 'gid': os.getgid(),
            'cgroup': read('/proc/self/cgroup'), 'affinity': sorted(os.sched_getaffinity(0)),
            'rlimit_as': resource.getrlimit(resource.RLIMIT_AS),
            'rlimit_memlock': resource.getrlimit(resource.RLIMIT_MEMLOCK), 'argv': argv})
    print('CAPTURE_START', pair, utc(), flush=True)
    process = None
    try:
        with (directory / 'clock-stdout.txt').open('xb') as stdout, (directory / 'clock-stderr.txt').open('xb') as stderr:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       preexec_fn=prepare_child, start_new_session=True)
            try:
                record['exit_code'] = process.wait(timeout=600)
                record['timed_out'] = False
            except subprocess.TimeoutExpired:
                stop_process(process)
                record['exit_code'] = process.returncode
                record['timed_out'] = True
    except BaseException as error:
        if process is not None:
            stop_process(process)
        record['launch_or_wait_error'] = repr(error)
        raise
    finally:
        record['completed_at_utc'] = utc()
        for name in ('clock-raw.json', 'clock-stdout.txt', 'clock-stderr.txt'):
            path = directory / name
            if path.exists():
                os.chown(path, 1000, 1000)
                record[name] = {'size_bytes': path.stat().st_size, 'sha256': digest(path)}
        retain(directory / 'clock-capture-result.json', record)
    after = isolated_state()
    require(after['partition']['cgroup.procs'] == '', 'capture process not reaped')
    retain(directory / 'control-after.json', after)
    print('CAPTURE_EXIT', pair, record['exit_code'], flush=True)
    require(record['exit_code'] == 0 and not record['timed_out'], 'clock qualification failed: ' + pair)
    verify_raw(json.loads(raw.read_bytes()), pair)
    print('CAPTURE_VERIFIED_PASS', pair, flush=True)


def main():
    import stage17_q16c_execution_window_v2 as window
    window.infrastructure(json.loads((Path(BINDINGS['evidence_root'])/'d282-execution-window-1/window.json').read_bytes()),BINDINGS['isolation_config'],now=time.monotonic_ns())
    require(BINDINGS is not None, 'render actual qualified release bindings first')
    require(os.geteuid() == 0, 'operator root required')
    require(not Q.exists(), 'clock namespace already used; no retry')
    require(read('/proc/sys/kernel/random/boot_id') == BOOT, 'boot changed')
    require(digest(TOOL) == BINARY_SHA, 'qualified clock binary differs')
    require(resource.getrlimit(resource.RLIMIT_MEMLOCK) == (MEMLOCK_BYTES, MEMLOCK_BYTES), 'preserved memlock differs')
    finite_raw = bound_bytes(BINDINGS['finite_plan_binding'])
    finite = json.loads(finite_raw)
    require(finite['release']['source_revision'] == REVISION, 'finite qualification plan/source differs')
    status_argv = ['runuser','-u','omaltsev','--','python3','-B',str(E/'admission-root/tools/stage17_operational_cli_daycap_v4.py'),
                   '--repository-root',str(E/'admission-root'),'--evidence-root',str(E),
                   '--pilot-archive',str(E.parent/(B.name+'.tar.gz')),
                   '--pilot-sidecar',str(E.parent/(B.name+'.tar.gz.sha256')),'status']
    status_value = json.loads(subprocess.run(status_argv,capture_output=True,text=True,check=True,
                                            timeout=BINDINGS['isolation_config']['stop_seconds']).stdout)
    require(status_value['current_state']=='PREFLIGHT_ACCEPTED' and status_value['resolutions']==4
            and status_value['transitions']==2
            and status_value['missing_inputs']==['S17-EXT-004','S17-EXT-005','S17-EXT-007','S17-EXT-008','S17-EXT-009','S17-EXT-010'],
            'fresh qualified prerequisite state differs')
    os.sched_setaffinity(0,{3})
    topology = {}
    for cpu in RESERVED:
        value = read(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list')
        require(cpus(value)=={cpu%16,cpu%16+16}, 'SMT topology differs')
        topology[str(cpu)] = value
    Q.mkdir(mode=0o700)
    os.chown(Q,1000,1000)
    def interrupted(number,frame):
        raise RuntimeError('qualification signal '+str(number))
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
        signal.signal(sig,interrupted)
    success = False
    pre = None
    try:
        # Frozen cold-proven operation: no direct root cpuset mutation here.
        pre = ISO.prepare(BINDINGS['isolation_config'])
        prepath = Path(BINDINGS['isolation_config']['evidence_root'])/'prospective-prestate.json'
        require(pre['prestate']['keeper_deadline_monotonic_ns']-time.monotonic_ns()
                > BINDINGS['isolation_config']['protected_work_ns']+BINDINGS['isolation_config']['stop_seconds']*10**9,
                'keeper lifetime no longer covers qualification and formal ceilings')
        commands = [[str(TOOL),'--qualify-pair',pair,'--output',str(Q/pair/'clock-raw.json')] for pair in ('near','far')]
        retain(Q/'prospective-plan.json', {'utc':utc(), 'source_revision':REVISION,'binary_sha256':BINARY_SHA,'boot_id':BOOT,
               'operator_script_sha256':digest(__file__),'finite_plan_sha256':hashlib.sha256(finite_raw).hexdigest(),
               'prestate':pre['prestate'],'partition_path':str(CG),'prerequisite_status':status_value,'topology':topology,
               'isolation_operator_binding':BINDINGS['isolation_operator_binding'],
               'isolation_prestate_binding':{'path':str(prepath),'size_bytes':prepath.stat().st_size,'sha256':digest(prepath)},
               'ordered_pairs':['near','far'],'maximum_invocations':2,'stop_on_first_failure':True,
               'per_invocation_timeout_seconds':600,'rlimit_as_bytes':AS_BYTES,'preserved_memlock_bytes':MEMLOCK_BYTES,
               'commands':commands,'commands_sha256':hashlib.sha256(json.dumps(commands,separators=(',',':')).encode()).hexdigest()})
        retain(Q/'isolation-verified.json',isolated_state())
        capture('near')
        capture('far')
        retain(Q/'complete.json', {'utc':utc(),'both_pairs_passed':True,
               'isolation_retained_for_following_qualification':isolated_state()})
        success = True
    except BaseException as error:
        retain(Q/'failure.json',{'utc':utc(),'error':repr(error),'retry_allowed':False})
        raise
    finally:
        if not success and pre is not None:
            restore(pre['prestate'])


if BINDINGS is not None:
    configure(BINDINGS)

if __name__ == '__main__':
    main()
