#!/usr/bin/env python3
"""One approved near/far qualification family; no retry or policy changes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-18')
Q = E / 'clock-requalification-1'
B = E / 'local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-817c652-clean-2cafad333953'
TOOL = B / 'release/bin/cpu_prefetch_q15_clock_qualification_tool'
ROOT = Path('/sys/fs/cgroup')
CG = ROOT / 'cpu-prefetch-v5-clock-qualified-1'
RESERVED = {0, 1, 2, 8, 16, 17, 18, 24}
HOUSEKEEPING = set(range(32)) - RESERVED
CPU_LIST = '0-2,8,16-18,24'
REVISION = '817c6522e3954efce53797e2bcc202a3bfc5d9af'
BINARY_SHA = '0ccefc493c48de378f4611570e6839dabbb0a7589d2c09caad3e63e734961f8d'
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
AS_BYTES = 8 * 1024**3
MEMLOCK_BYTES = 8 * 1024**2

def require(value, message):
    if not value:
        raise RuntimeError(message)

def utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def read(path):
    return Path(path).read_text().strip()

def cpus(value):
    result = set()
    for part in value.split(','):
        if not part:
            continue
        span = part.split('-')
        require(len(span) in (1, 2), 'bad CPU list')
        first, last = int(span[0]), int(span[-1])
        require(first <= last, 'reversed CPU range')
        result.update(range(first, last + 1))
    return result

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def retain(path, value):
    payload = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(path, 1000, 1000)
    os.chmod(path, 0o400)
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def write_control(path, value):
    with Path(path).open('w') as stream:
        stream.write(value + '\n')

def root_state():
    return {name: read(ROOT / name) for name in (
        'cgroup.controllers', 'cgroup.subtree_control', 'cpuset.cpus.effective',
        'cpuset.mems.effective', 'cpuset.cpus.isolated')}

def isolated_state():
    state = {name: read(CG / name) for name in (
        'cgroup.type', 'cgroup.subtree_control', 'cgroup.procs', 'cgroup.events',
        'cpuset.cpus', 'cpuset.cpus.effective', 'cpuset.cpus.exclusive',
        'cpuset.cpus.exclusive.effective', 'cpuset.cpus.partition',
        'cpuset.mems', 'cpuset.mems.effective')}
    root = root_state()
    require(state['cgroup.type'] == 'domain', 'unexpected cgroup type')
    require(state['cgroup.subtree_control'] == '', 'unexpected child delegation')
    require(state['cpuset.cpus.partition'] == 'isolated', 'partition is not valid isolated')
    for field in ('cpuset.cpus', 'cpuset.cpus.effective', 'cpuset.cpus.exclusive', 'cpuset.cpus.exclusive.effective'):
        require(cpus(state[field]) == RESERVED, 'reserved CPU readback differs: ' + field)
    require(cpus(state['cpuset.mems.effective']) == {0, 1}, 'NUMA nodes differ')
    require(cpus(root['cpuset.cpus.effective']) == HOUSEKEEPING, 'outside CPU exclusion differs')
    require(cpus(root['cpuset.cpus.isolated']) == RESERVED, 'root isolated set differs')
    require(os.sched_getaffinity(0) <= HOUSEKEEPING, 'supervisor escaped housekeeping')
    for name in ('system.slice', 'user.slice', 'init.scope'):
        require(cpus(read(ROOT / name / 'cpuset.cpus.effective')) <= HOUSEKEEPING,
                'outside slice can use reserved CPUs: ' + name)
    require(read('/proc/sys/kernel/random/boot_id') == BOOT, 'boot changed')
    return {'captured_at_utc': utc(), 'root': root, 'partition': state,
            'supervisor_affinity': sorted(os.sched_getaffinity(0))}

def restore(prestate):
    if CG.exists():
        require(read(CG / 'cgroup.procs') == '', 'unreaped or unrelated task; do not move/kill it')
        require('populated 0' in read(CG / 'cgroup.events').splitlines(), 'partition still populated')
        write_control(CG / 'cpuset.cpus.partition', 'member')
        require(read(CG / 'cpuset.cpus.partition') == 'member', 'partition restoration failed')
        CG.rmdir()
    if 'cpuset' not in prestate['cgroup.subtree_control'].split() and 'cpuset' in read(ROOT / 'cgroup.subtree_control').split():
        for child in ROOT.iterdir():
            if child.is_dir():
                require('cpuset' not in read(child / 'cgroup.subtree_control').split(),
                        'new unrelated cpuset dependency; do not disable it')
        write_control(ROOT / 'cgroup.subtree_control', '-cpuset')
    observed = root_state()
    require(observed == prestate, 'root settings differ after restoration')
    retain(Q / 'restoration.json', {'utc': utc(), 'verified': True, 'root': observed,
                                    'partition_absent': not CG.exists()})

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
    record = {'capture_id': 'CPU-PREFETCH-V5-V18-ISOLATED-CLOCK-' + pair.upper() + '-1',
              'command': argv, 'binary_sha256': digest(TOOL), 'source_revision': REVISION,
              'started_at_utc': utc(), 'timeout_seconds': 600,
              'clock_api': 'CLOCK_MONOTONIC_RAW', 'timestamp_units': 'relative picoseconds',
              'scope': 'OWNER_APPROVED_FINITE_ISOLATED_REQUALIFICATION',
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
        require(read('/proc/self/cgroup') == '0::/' + CG.name, 'launcher membership differs')
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
    require(os.geteuid() == 0, 'operator root required')
    require(not Q.exists() and not CG.exists(), 'exclusive study/partition already exists')
    require(read('/proc/sys/kernel/random/boot_id') == BOOT, 'boot changed')
    require(digest(TOOL) == BINARY_SHA, 'qualified binary differs')
    require(resource.getrlimit(resource.RLIMIT_MEMLOCK) == (MEMLOCK_BYTES, MEMLOCK_BYTES), 'memlock differs')
    before = root_state()
    require(before['cgroup.subtree_control'] == 'cpu memory pids', 'delegation differs from reviewed prestate')
    require(cpus(before['cpuset.cpus.effective']) == set(range(32)) and before['cpuset.cpus.isolated'] == '', 'pre-existing CPU isolation differs')
    require(cpus(before['cpuset.mems.effective']) == {0, 1}, 'NUMA prestate differs')
    require('cpuset' in before['cgroup.controllers'].split(), 'cpuset unavailable')
    require(not list(ROOT.rglob('cpuset.cpus.partition')), 'pre-existing delegated partitions')
    topology = {}
    for cpu in RESERVED:
        observed = read(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list')
        require(cpus(observed) == {cpu % 16, cpu % 16 + 16}, 'SMT topology changed')
        topology[str(cpu)] = observed
    os.sched_setaffinity(0, {3})
    Q.mkdir(mode=0o700)
    os.chown(Q, 1000, 1000)
    proposal = E / 'operator-preparation-v18/approved-clock-requalification-plan.md'
    require('OWNER_APPROVED_FINITE_PLAN' in proposal.read_text(), 'approved plan absent')
    commands = [[str(TOOL), '--qualify-pair', pair, '--output', str(Q / pair / 'clock-raw.json')] for pair in ('near', 'far')]
    retain(Q / 'prospective-plan.json', {
        'utc': utc(), 'owner_approval': 'yes, I approve the requalification plan',
        'approval_plan_sha256': digest(proposal), 'operator_script_sha256': digest(__file__),
        'source_revision': REVISION, 'binary_sha256': BINARY_SHA, 'boot_id': BOOT,
        'prestate': before, 'topology': topology, 'partition_path': str(CG),
        'requested_cpus': CPU_LIST, 'requested_mems': '0-1', 'partition_mode': 'isolated',
        'ordered_pairs': ['near', 'far'], 'maximum_invocations': 2,
        'stop_on_first_failure': True, 'per_invocation_timeout_seconds': 600,
        'rlimit_as_bytes': AS_BYTES, 'preserved_memlock_bytes': MEMLOCK_BYTES,
        'commands': commands,
        'commands_sha256': hashlib.sha256(json.dumps(commands, separators=(',', ':')).encode()).hexdigest(),
        'rollback': ['reap own capture group', 'require empty partition', 'partition member', 'remove own cgroup', 'remove only added cpuset delegation', 'verify exact root prestate'],
        'unchanged_controls': ['governor', 'turbo', 'IRQ routing', 'boot options', 'clocksource', 'production binaries']})
    success = False
    def interrupted(number, frame):
        raise RuntimeError('operator signal ' + str(number))
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, interrupted)
    try:
        write_control(ROOT / 'cgroup.subtree_control', '+cpuset')
        CG.mkdir()
        write_control(CG / 'cpuset.mems', '0-1')
        write_control(CG / 'cpuset.cpus', CPU_LIST)
        write_control(CG / 'cpuset.cpus.exclusive', CPU_LIST)
        write_control(CG / 'cpuset.cpus.partition', 'isolated')
        retain(Q / 'isolation-verified.json', isolated_state())
        print('ISOLATION_VERIFIED', utc(), flush=True)
        capture('near')
        capture('far')
        retain(Q / 'complete.json', {'utc': utc(), 'both_pairs_passed': True,
                                    'isolation_retained_for_following_qualification': isolated_state()})
        success = True
        print('REQUALIFICATION_COMPLETE_BOTH_PAIRS_PASS', flush=True)
    except BaseException as error:
        retain(Q / 'failure.json', {'utc': utc(), 'error': repr(error), 'retry_allowed': False})
        raise
    finally:
        if not success:
            restore(before)
            print('RESTORATION_VERIFIED', utc(), flush=True)

if __name__ == '__main__':
    main()
