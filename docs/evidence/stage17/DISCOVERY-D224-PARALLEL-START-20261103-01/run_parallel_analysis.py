#!/usr/bin/env python3
"""Exclusive, bounded D224 analysis supervisor. No collection or old-run control."""
from __future__ import annotations

import argparse
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import subprocess
import sys
import time

GIB = 1024**3
AS_BYTES = 8 * GIB
MEMORY_ADMISSION_BYTES = 80 * GIB
SCRATCH_BYTES = 256 * GIB
RESERVE_BYTES = 16 * GIB
TIMEOUT_SECONDS = 86400
MAX_CONTROL_BYTES = 3373611301
META_BYTES = 32 * 1024**2
BOOT_ID = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
ROOT_NAME = 'discovery-analysis-r3-d224-2'
FILES = frozenset(('stage17_discovery_validation_v3.py',
    'stage17_discovery_validation_parallel_v1.py',
    'validate_d207_retained_study_parallel_v1.py',
    '0213-discovery-whole-plot-readback-validation.md',
    '0224-parallel-retained-discovery-validation.md', 'run_parallel_analysis.py'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def safe(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'symlink path: ' + str(part))
    return path


def bounded_read(path, digest=None, owned=False):
    path = safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= META_BYTES,
                'not bounded regular metadata: ' + str(path))
        if owned:
            require(before.st_uid == 1000 and not before.st_mode & 0o022, 'metadata ownership/mode')
        raw = stream.read(META_BYTES + 1)
        after = os.fstat(stream.fileno())
    fields = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    require(fields(before) == fields(after) and len(raw) == before.st_size, 'metadata changed')
    if digest is not None:
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'invalid SHA256')
        require(hashlib.sha256(raw).hexdigest() == digest, 'SHA256 differs: ' + path.name)
    return raw


def document(path, digest=None, owned=False):
    return json.loads(bounded_read(path, digest, owned), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def retain(root, name, value):
    require('/' not in name, 'flat output name required')
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def flags(argv):
    require(type(argv) is list and len(argv) >= 5 and argv[:2] == ['/usr/bin/python3', '-B'],
            'fixed Python invocation required')
    require(all(type(item) is str for item in argv) and len(argv[3:]) % 2 == 0, 'argv structure')
    result = {}
    for key, value in zip(argv[3::2], argv[4::2], strict=True):
        require(key.startswith('--') and key not in result, 'duplicate/invalid argv flag')
        result[key] = value
    return result


def installation(root, manifest_digest):
    require(os.getuid() == os.geteuid() == 1000, 'UID 1000 required')
    root = safe(root)
    info = root.stat()
    require(root.name == ROOT_NAME and info.st_uid == 1000 and stat.S_ISDIR(info.st_mode)
            and not info.st_mode & 0o077, 'exclusive owned analysis root required')
    manifest = document(root / 'installed-bindings.json', manifest_digest, True)
    require(manifest['schema_version'] == 'd224-analysis-installation/1', 'manifest version')
    require(manifest['analysis_root'] == str(root) and manifest['expected_boot_id'] == BOOT_ID,
            'manifest root/boot differs')
    rows = manifest['files']
    require(len(rows) == len(FILES) and {row['name'] for row in rows} == FILES, 'exact six bound files')
    for row in rows:
        raw = bounded_read(root / row['name'], row['sha256'], True)
        require(type(row['size_bytes']) is int and len(raw) == row['size_bytes'], 'installed size differs')
    argv = manifest['argv']; options = flags(argv)
    require(argv[2] == str(root / 'validate_d207_retained_study_parallel_v1.py'), 'wrapper path differs')
    require(options['--scratch-directory'] == str(root / 'scratch')
            and options['--output'] == str(root / 'scratch/full-study-validation-parallel-v1.json'),
            'fresh analysis output paths required')
    raw_root = safe(options['--output-root'])
    require(not root.is_relative_to(raw_root) and not raw_root.is_relative_to(root), 'raw/analysis overlap')
    scratch = safe(root / 'scratch'); info = scratch.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 1000 and not info.st_mode & 0o077,
            'private scratch directory required')
    require(not any(scratch.iterdir()), 'scratch must be empty before first launch')
    return manifest, options


def retention_control_bound(options):
    root = safe(options['--output-root'])
    result = document(root / 'stage17-action-result-v5.json', options['--admitted-result-sha256'])
    artifacts = result['artifacts']
    indexed = {row['file_name']: row for row in artifacts}
    require(len(indexed) == len(artifacts), 'duplicate admitted artifact')
    binding = indexed['retention-report.json']
    raw = bounded_read(root / binding['file_name'], binding['sha256'])
    require(len(raw) == binding['size_bytes'], 'retention size differs')
    report = json.loads(raw, object_pairs_hook=unique)
    require(len(report['captures']) == 36, 'full36 retention required')
    sizes = []
    for ordinal, capture in enumerate(report['captures']):
        require(type(capture['ordinal']) is int and capture['ordinal'] == ordinal, 'retention order')
        name = f'discovery-c{ordinal:02d}-control.json'
        matches = [row for row in capture['artifacts'] if row['file_name'] == name]
        require(len(matches) == 1, 'one bound control per capture')
        row = matches[0]
        require(all(row[key] == indexed[name][key] for key in ('file_name', 'size_bytes', 'sha256')),
                'control differs from admitted artifact')
        require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= MAX_CONTROL_BYTES,
                'control size exceeds prospective admission ceiling')
        path = safe(root / name); info = path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_size == row['size_bytes'], 'actual control size differs')
        sizes.append(info.st_size)
    return dict(control_files=36, actual_max_control_bytes=max(sizes), admitted_control_ceiling=MAX_CONTROL_BYTES,
                retention_sha256=binding['sha256'], control_content_hashes_checked_here=False,
                control_hash_gate='UNCHANGED_WRAPPER_AND_CAPTURE_VALIDATOR_BEFORE_ACCEPTANCE',
                scratch_planning_estimate_bytes=MAX_CONTROL_BYTES * 8 * 6,
                scratch_expansion_factor=6, expansion_factor_is_proved_bound=False)


def mem_available(raw):
    matches = re.findall(r'^MemAvailable:\s+([0-9]+) kB$', raw, re.MULTILINE)
    require(len(matches) == 1, 'missing/duplicate MemAvailable')
    return int(matches[0]) * 1024


def available_disk(path):
    value = os.statvfs(path)
    return value.f_bavail * value.f_frsize


def resource_admission(root):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    memory = mem_available(Path('/proc/meminfo').read_text())
    cpus = sorted(os.sched_getaffinity(0)); disk = available_disk(root)
    require(boot == BOOT_ID, 'boot differs')
    require(len(cpus) >= 8, 'fewer than eight available CPUs')
    require(memory >= MEMORY_ADMISSION_BYTES, 'MemAvailable below 80 GiB')
    require(disk >= SCRATCH_BYTES + RESERVE_BYTES, 'free disk below scratch plus reserve')
    return dict(observed_at_utc=utc(), boot_id=boot, available_cpus=cpus,
                mem_available_bytes=memory, disk_available_bytes=disk,
                required_mem_available_bytes=MEMORY_ADMISSION_BYTES,
                supervisor_address_space_bytes=AS_BYTES, parent_address_space_bytes=AS_BYTES,
                worker_count=8, worker_address_space_bytes=AS_BYTES,
                scratch_bytes=SCRATCH_BYTES, disk_reserve_bytes=RESERVE_BYTES,
                per_file_write_ceiling_bytes=SCRATCH_BYTES,
                scratch_is_hard_quota=False, scratch_poll_seconds=1,
                scratch_may_overshoot_between_polls=True, maximum_analysis_seconds=TIMEOUT_SECONDS)


def hard_limits():
    for kind, requested in ((resource.RLIMIT_AS, AS_BYTES), (resource.RLIMIT_FSIZE, SCRATCH_BYTES)):
        soft, hard = resource.getrlimit(kind)
        require(hard == resource.RLIM_INFINITY or hard >= requested, 'inherited hard resource limit too small')
        resource.setrlimit(kind, (requested, requested))


def subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER')
    current = ctypes.c_int()
    require(libc.prctl(37, ctypes.byref(current), 0, 0, 0) == 0 and current.value == 1,
            'subreaper readback failed')


def children(pid):
    try:
        return [int(value) for value in Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
    except FileNotFoundError:
        return []


def process_identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
    except FileNotFoundError:
        return None
    fields = raw[raw.rfind(')') + 2:].split()
    return int(fields[1]), int(fields[19])  # PPID, starttime; comm may contain ')'.


class OwnTree:
    def __init__(self):
        self.handles = {}

    def discover(self):
        pending = [os.getpid()]; seen = set()
        while pending:
            parent = pending.pop()
            for pid in children(parent):
                if pid in seen:
                    continue
                seen.add(pid)
                require(len(seen) <= 128, 'unexpected descendant count')
                before = process_identity(pid)
                if before is None or before[0] != parent:
                    continue
                if pid not in self.handles:
                    try:
                        fd = os.pidfd_open(pid, 0)
                    except ProcessLookupError:
                        continue
                    if process_identity(pid) != before:
                        os.close(fd); continue
                    self.handles[pid] = fd
                pending.append(pid)
        return seen

    def signal(self, number):
        for fd in self.handles.values():
            try:
                signal.pidfd_send_signal(fd, number)
            except ProcessLookupError:
                pass

    def close(self):
        for fd in self.handles.values():
            os.close(fd)


def scratch_usage(root, pids):
    """Logical/allocated bytes, deduplicated, including open unlinked spools."""
    root = str(root); found = {}

    def add(info):
        if stat.S_ISREG(info.st_mode):
            key = info.st_dev, info.st_ino
            found[key] = max(found.get(key, 0), info.st_size, info.st_blocks * 512)

    count = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in (*dirs, *files):
            count += 1; require(count <= 4096, 'unexpected analysis file count')
            path = Path(directory) / name
            try:
                info = path.lstat()
                require(not stat.S_ISLNK(info.st_mode), 'analysis symlink appeared')
                add(info)
            except FileNotFoundError:
                pass
    for pid in {*pids, os.getpid()}:
        try:
            entries = list(Path(f'/proc/{pid}/fd').iterdir())
        except FileNotFoundError:
            continue
        require(len(entries) <= 4096, 'unexpected analysis descriptor count')
        for entry in entries:
            try:
                target = os.readlink(entry)
                if target.startswith(root + '/'):
                    add(entry.stat())
            except (FileNotFoundError, ProcessLookupError):
                pass
    return sum(found.values())


def reap_available(process, receipts):
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return
        code = os.waitstatus_to_exitcode(status)
        receipts.append(dict(pid=pid, exit_code=code))
        if pid == process.pid:
            process.returncode = code


def cleanup(process, tree, grace_seconds=5):
    """Only this dedicated subreaper's children; never enumerate other jobs."""
    receipts = []
    # The direct leader has deliberately not been reaped, anchoring its PGID.
    for number, grace in ((signal.SIGTERM, grace_seconds), (signal.SIGKILL, 10)):
        tree.discover()
        if process.returncode is None:
            try:
                os.killpg(process.pid, number)
            except ProcessLookupError:
                pass
        tree.signal(number)
        deadline = time.monotonic() + grace
        while True:
            tree.discover(); tree.signal(number)
            reap_available(process, receipts)
            if not children(os.getpid()):
                require(process.returncode is not None, 'analysis leader not reaped')
                return receipts
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
    raise RuntimeError('own analysis descendants could not all be reaped')


def supervise(argv, root, timeout_seconds=TIMEOUT_SECONDS, poll_seconds=1,
              scratch_limit=SCRATCH_BYTES, disk_reserve=RESERVE_BYTES, grace_seconds=5):
    require(not children(os.getpid()), 'supervisor must start without unrelated children')
    require(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'Linux pidfd support required')
    subreaper(); tree = OwnTree(); process = None; handlers = {}
    report = dict(started_at_utc=utc(), status='ANALYSIS_ABORTED', execution_authority=False,
                  raw_mutation=False, maximum_sampled_scratch_bytes=0, reaped_children=[])
    start = time.monotonic()

    def interrupted(number, frame):
        raise InterruptedError(f'supervisor received signal {number}')

    try:
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            handlers[number] = signal.signal(number, interrupted)
        stdout = os.open(root / 'analysis-stdout.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            stderr = os.open(root / 'analysis-stderr.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    cwd=root, start_new_session=True, close_fds=True,
                    env={**os.environ, 'TMPDIR':str(root / 'scratch'), 'PYTHONDONTWRITEBYTECODE':'1'})
            finally:
                os.close(stderr)
        finally:
            os.close(stdout)
        report['analysis_pid'] = process.pid; report['analysis_pgid'] = process.pid
        while True:
            pids = tree.discover()
            used = scratch_usage(root, pids)
            report['maximum_sampled_scratch_bytes'] = max(used, report['maximum_sampled_scratch_bytes'])
            require(used <= scratch_limit, 'monitored scratch allowance exceeded')
            require(available_disk(root) >= disk_reserve, 'disk reserve crossed')
            require(time.monotonic() - start < timeout_seconds, 'whole-analysis deadline exceeded')
            # WNOWAIT leaves the group leader's PID reserved until cleanup.
            status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if status is not None:
                # A worker in the earlier snapshot may have been joined before
                # the leader exited. WNOWAIT now anchors the exited leader.
                remaining = tree.discover()
                require(not (remaining - {process.pid}), 'analysis leader exited with descendants')
                report['status'] = 'ANALYSIS_EXITED'
                break
            time.sleep(min(poll_seconds, max(0.001, timeout_seconds - (time.monotonic() - start))))
    except BaseException as error:
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        for number in handlers:
            signal.signal(number, signal.SIG_IGN)
        try:
            if process is not None:
                report['reaped_children'] = cleanup(process, tree, grace_seconds)
                report['exit_code'] = process.returncode
                report['all_own_children_reaped'] = not children(os.getpid())
            else:
                report['all_own_children_reaped'] = True
        except BaseException as error:
            report['status'] = 'ANALYSIS_ABORTED'
            report['cleanup_error'] = f'{type(error).__name__}: {error}'
            report['all_own_children_reaped'] = False
        finally:
            tree.close()
            for number, handler in handlers.items():
                signal.signal(number, handler)
        report['finished_at_utc'] = utc()
        report['elapsed_seconds'] = time.monotonic() - start
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    root = safe(Path(__file__).parent)
    manifest, options = installation(root, args.manifest_sha256)
    hard_limits()
    controls = retention_control_bound(options)
    admission = resource_admission(root)
    retain(root, 'analysis-intent.json', dict(schema_version='d224-analysis-intent/1', argv=manifest['argv'],
        installation_sha256=args.manifest_sha256, files=manifest['files'], resource_admission=admission,
        control_admission=controls, started_at_utc=utc(), execution_authority=False, raw_mutation=False))
    result = supervise(manifest['argv'], root)
    retain(root, 'analysis-process-result.json', result)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result['status'] == 'ANALYSIS_EXITED' and result.get('exit_code') == 0 \
        and result['all_own_children_reaped'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('D224_LAUNCH_REJECTED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
