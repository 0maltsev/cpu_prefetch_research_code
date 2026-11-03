#!/usr/bin/env python3
"""Operator-only R2 byte custody. No remote commands, analysis or retries."""
from __future__ import annotations
import argparse
import concurrent.futures
import ctypes
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import uuid

SOURCE = '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19/discovery-output-r2-1'
REPO = Path(__file__).resolve().parents[2]
DEST = REPO / 'build/stage17-discovery-v19-copy1/discovery-output-r2-1'
SPOOL_RESERVE = 3485469950 + 10 * 1024**3
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None and result.utcoffset() == dt.timedelta(0), 'UTC timestamp required')
    return result


def safe_path(path, create=False):
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if create:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
        info = current.lstat()
        require(not stat.S_ISLNK(info.st_mode), f'symlink rejected: {current}')
        if current != path or create:
            require(stat.S_ISDIR(info.st_mode), f'not a directory: {current}')
    return path


def load(path):
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'input must be regular')
        data = stream.read()
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs), hashlib.sha256(data).hexdigest()


def gates(inventory_path, result_path, audit_path):
    inventory, manifest_sha = load(inventory_path)
    result, result_sha = load(result_path)
    audit, audit_sha = load(audit_path)
    require(inventory['root'] == SOURCE, 'wrong source root')
    require(audit['root'] == SOURCE and audit['inventory_sha256'] == manifest_sha
            and audit['supervisor_result_sha256'] == result_sha, 'audit binding mismatch')
    for key in ('post_quiescence', 'complete', 'regular_files_only', 'no_symlinks'):
        require(audit.get(key) is True, f'missing source audit gate: {key}')
    require(audit.get('errors') == [], 'source audit errors')
    require(type(result.get('exit_code')) is int, 'supervisor has no terminal exit')
    require(result.get('partition_procs') == '', 'partition not quiescent')
    restoration = result['partition_restoration']
    require(restoration.get('verified') is True and restoration.get('partition_absent') is True,
            'restoration not verified')
    require(not result.get('partition_restoration_error'), 'restoration error retained')
    observed = timestamp(inventory['observed_at_utc'])
    require(observed >= timestamp(result['utc']) and observed >= timestamp(restoration['utc']),
            'inventory predates quiescence/restoration')
    require(observed <= timestamp(audit['observed_at_utc']) <= dt.datetime.now(dt.timezone.utc),
            'audit time order invalid')
    files = []; seen = set()
    require(isinstance(inventory['files'], list), 'inventory files must be a list')
    for item in inventory['files']:
        name = item['path']
        require(isinstance(name, str) and all(NAME.fullmatch(p) and p not in ('.', '..')
                for p in name.split('/')), 'unsafe inventory name')
        require(name not in seen, f'duplicate inventory path: {name}')
        seen.add(name)
        require(type(item['size_bytes']) is int and item['size_bytes'] >= 0, 'invalid size')
        require(isinstance(item['sha256'], str) and HEX.fullmatch(item['sha256']), 'invalid SHA256')
        if name.startswith('operator/'):
            continue
        require('/' not in name, 'R2 output must be flat regular files')
        files.append({key: item[key] for key in ('path', 'size_bytes', 'sha256')})
    require(bool(files), 'empty output inventory')
    return inventory, files, manifest_sha, result_sha, audit_sha


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def verify(path, item, expected_inode=None):
    safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), f'nonregular file: {path}')
        if expected_inode is not None:
            require((before.st_dev, before.st_ino) == expected_inode, 'temporary inode changed')
        require(before.st_size == item['size_bytes'], f'size mismatch: {item["path"]}')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                'file changed during hash')
        require(digest == item['sha256'], f'hash mismatch: {item["path"]}')
        os.fsync(stream.fileno())
    actual = path.lstat()
    require((actual.st_dev, actual.st_ino) == (after.st_dev, after.st_ino), 'path changed during hash')


def rename_noreplace(source, target):
    # Linux atomic RENAME_NOREPLACE: never clobber an existing destination.
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    fn.restype = ctypes.c_int
    if fn(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def exclusive_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    sync_dir(path.parent)


def copy_one(item, dest, work, timeout, failed, dispatch_lock, scp='/usr/bin/scp'):
    if failed.is_set():
        return {'path': item['path'], 'status': 'NOT_STARTED_AFTER_FAILURE'}
    temporary = work / (item['path'] + '.partial')
    error_log = work / (item['path'] + '.scp-stderr')
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd); os.close(fd)
        argv = [scp, '-F', '/dev/null', '-B', '-o', 'BatchMode=yes', '-o', 'Compression=no',
                '-o', 'ConnectionAttempts=1', '-o', 'ConnectTimeout=30',
                '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'ControlPath=none', '--',
                f'root@94.126.205.83:{SOURCE}/{item["path"]}', str(temporary)]
        with error_log.open('xb') as errors:
            with dispatch_lock:
                if failed.is_set():
                    return {'path': item['path'], 'status': 'NOT_STARTED_AFTER_FAILURE'}
                process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
            errors.flush(); os.fsync(errors.fileno())
        require(code == 0, f'scp exit {code}: {item["path"]}')
        verify(temporary, item, (info.st_dev, info.st_ino))
        rename_noreplace(temporary, dest / item['path'])
        sync_dir(dest); sync_dir(work)
        return dict(item, status='COPIED_VERIFIED')
    except BaseException as error:
        with dispatch_lock:
            failed.set()
        return {'path': item['path'], 'status': 'FAILED', 'error': repr(error),
                'partial_path': str(temporary), 'stderr_path': str(error_log)}


def run(args):
    inventory, files, manifest_sha, result_sha, audit_sha = gates(
        args.inventory, args.supervisor_result, args.inventory_audit)
    dest = safe_path(DEST, create=True)
    state = safe_path(dest.parent / (dest.name + '.custody'), create=True)
    require(dest.stat().st_dev == state.stat().st_dev, 'temporary files must share destination filesystem')
    lock = os.open(state / 'copy.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return locked_run(args, inventory, files, manifest_sha, result_sha, audit_sha, dest, state)
        except BaseException as error:
            exclusive_json(state / ('failure-' + uuid.uuid4().hex + '.json'),
                           {'observed_at_utc': utc(), 'status': 'FAILED_NO_NEW_CUSTODY_RECEIPT',
                            'inventory_sha256': manifest_sha, 'error': repr(error)})
            raise
    finally:
        os.close(lock)


def locked_run(args, inventory, files, manifest_sha, result_sha, audit_sha, dest, state):
    expected = {item['path'] for item in files}
    present = {path.name for path in dest.iterdir()}
    require(present <= expected, 'unexpected destination entries; preserve and investigate')
    pending = []
    for item in files:
        path = dest / item['path']
        if item['path'] in present:
            verify(path, item)
        else:
            pending.append(item)
    pending.sort(key=lambda item: item['size_bytes'], reverse=True)
    fs = os.statvfs(dest)
    require(fs.f_bavail * fs.f_frsize >= sum(f['size_bytes'] for f in pending) + SPOOL_RESERVE,
            'insufficient free space for remaining copy plus spool and reserve')
    receipt = safe_path(Path(args.receipt).parent) / Path(args.receipt).name
    if receipt.exists() or receipt.is_symlink():
        previous, _ = load(receipt)
        require(not pending and previous['status'] == 'PASS_ORIGINAL_BYTE_SECOND_COPY'
                and previous['stand_manifest_sha256'] == manifest_sha
                and previous['pc_root'] == str(dest) and previous['files'] == files
                and previous['compression'] is False, 'existing receipt conflicts')
        print(json.dumps({'status': 'ALREADY_VERIFIED', 'files': len(files), 'receipt': str(receipt)}))
        return 0
    # Fail before network if no Linux no-clobber rename facility is available.
    require(hasattr(ctypes.CDLL(None), 'renameat2'), 'renameat2 unavailable')
    work = state / ('invocation-' + uuid.uuid4().hex)
    work.mkdir(mode=0o700); sync_dir(state)
    failed = threading.Event()
    dispatch_lock = threading.Lock()
    with (work / 'progress.jsonl').open('x') as progress:
        def record(value):
            value = dict(observed_at_utc=utc(), **value)
            line = json.dumps(value, sort_keys=True)
            progress.write(line + '\n'); progress.flush(); os.fsync(progress.fileno())
            print(line, flush=True)
        record({'status': 'START', 'inventory_sha256': manifest_sha, 'already_verified': len(files)-len(pending),
                'remaining_files': len(pending), 'remaining_bytes': sum(f['size_bytes'] for f in pending)})
        # Batches prevent new dispatch after any failed in-flight transfer.
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for offset in range(0, len(pending), args.jobs):
                remaining = sum(f['size_bytes'] for f in pending[offset:])
                fs = os.statvfs(dest)
                if fs.f_bavail * fs.f_frsize < remaining + SPOOL_RESERVE:
                    record({'status': 'FAILED', 'error': 'insufficient free space',
                            'required_bytes': remaining + SPOOL_RESERVE,
                            'available_bytes': fs.f_bavail * fs.f_frsize})
                    failed.set(); break
                futures = [pool.submit(copy_one, item, dest, work, args.file_timeout_seconds, failed, dispatch_lock)
                           for item in pending[offset:offset + args.jobs]]
                for future in concurrent.futures.as_completed(futures):
                    record(future.result())
                if failed.is_set():
                    break
        if failed.is_set():
            record({'status': 'INCOMPLETE_NO_CUSTODY_RECEIPT', 'partials_retained': str(work)})
            return 1
        require({p.name for p in dest.iterdir()} == expected, 'final destination set mismatch')
        # Whole-set final original-byte verification; no JSON/raw scientific parsing.
        for item in files:
            verify(dest / item['path'], item)
        fs = os.statvfs(dest)
        require(fs.f_bavail * fs.f_frsize >= SPOOL_RESERVE, 'final spool/reserve free-space gate failed')
        document = dict(status='PASS_ORIGINAL_BYTE_SECOND_COPY', observed_at_utc=utc(),
            stand_root=SOURCE, pc_root=str(dest), compression=False,
            stand_manifest_observed_at_utc=inventory['observed_at_utc'], stand_manifest_sha256=manifest_sha,
            files=files, total_bytes=sum(f['size_bytes'] for f in files), execution_authority=False,
            scientific_validity_not_implied=True, supervisor_result_sha256=result_sha,
            source_inventory_audit_sha256=audit_sha)
        temporary_receipt = work / 'verified-receipt.json'
        exclusive_json(temporary_receipt, document)
        require(temporary_receipt.stat().st_dev == receipt.parent.stat().st_dev, 'receipt must share filesystem')
        rename_noreplace(temporary_receipt, receipt); sync_dir(receipt.parent); sync_dir(work)
        record({'status': document['status'], 'files': len(files), 'total_bytes': document['total_bytes'],
                'receipt': str(receipt)})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--supervisor-result', type=Path, required=True)
    parser.add_argument('--inventory-audit', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, default=Path(__file__).with_name('r2-copy-verification.json'))
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--file-timeout-seconds', type=int, required=True)
    args = parser.parse_args()
    require(args.file_timeout_seconds > 0, 'finite positive file timeout required')
    return run(args)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_NO_NEW_CUSTODY_RECEIPT', 'error': repr(exc)}), file=sys.stderr)
        sys.exit(1)
