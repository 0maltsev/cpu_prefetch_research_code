"""D257 collection-only continuation after successful retained E26 qualification.

New exclusive supervisor, unchanged native/plan, same original 24-hour anchor.
No clocks, Q15, experimental retries, archive initialization or deadline reset.
D256 admission is authenticated before the original infrastructure core rearms
fresh isolation. Original ownership, signature, cleanup and analysis gates remain.
"""
from __future__ import annotations

import argparse
import ast
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
import threading
import time
import types

SCHEMA = 'software-d257-collection-resume/1'
PREPARED_SCHEMA = 'software-d254-prepared-phase/1'
SOURCE = 'aa3285f15acbd3314cae64a628c113488a8438b8'
E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26')
P = E / 'operator-preparation-v26'
CG = Path('/sys/fs/cgroup/cpu-prefetch-recovery-v26-qualified-1.service/reserved')
CORE_SHA = '49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
NANO = 10**9
DAY_SECONDS, WORK_SECONDS, CLEANUP_SECONDS = 86400, 84600, 1800
QUALIFY_PREP_SECONDS, NATIVE_SECONDS, ANALYSIS_SECONDS = 3600, 65040, 13500
COLLECTION_SECONDS = 57600
OWNER_CLEANUP_SECONDS = 120
WORKER_AS, MEMLOCK = 240518168576, 30709854208
CAP_NAMES = ('sys_ptrace', 'sys_rawio', 'dac_override', 'perfmon')
CAP_MASK = sum(1 << n for n in (19, 17, 1, 38))
ANALYSIS_CAP_MASK = 1 << 19
OPERATORS = frozenset(('run_daycap_study.py', 'prepare_collection.py', 'owner_check.py',
                       'daycap_cli.py', 'analyze_daycap.py'))
QUALIFIERS = frozenset(('run_qualification_v26.py', 'run_clock_qualification_v26.py',
                        'install_v26.py', 'isolation_core.py', 'release-bindings.json', 'finite-qualification-plan.json'))
MAX_METADATA = 128 * 1024**2


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names.split()), label + ' fields')


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise RuntimeError('noninteger JSON: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def plan_sha256(plan):
    # Native plan identity has no transport LF, as in the qualified registry.
    raw = json.dumps(plan, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def path(value):
    require(type(value) is str, 'explicit path string')
    p = Path(value)
    require(p.is_absolute() and str(p) == value and '..' not in p.parts
            and all(not q.is_symlink() for q in (p, *p.parents)), 'canonical absolute nonsymlink path')
    return p


def stamp(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def read_file(p, *, maximum=MAX_METADATA, keep=True, expected=None):
    p = path(str(p))
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    digest, blocks = hashlib.sha256(), []
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum, 'bounded regular input')
        if expected is not None:
            require(before.st_size == expected['size_bytes'], 'bound file size changed')
        remaining = before.st_size
        while remaining:
            block = stream.read(min(1024**2, remaining))
            require(bool(block), 'truncated input')
            remaining -= len(block)
            digest.update(block)
            if keep:
                blocks.append(block)
        require(not stream.read(1) and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(p.stat()),
                'input changed while reading')
    binding = dict(path=str(p), size_bytes=before.st_size, sha256=digest.hexdigest())
    if expected is not None:
        require(binding == expected, 'bound file SHA256 changed: ' + str(p))
    return b''.join(blocks) if keep else binding


def bound(value, *, keep=True, maximum=MAX_METADATA):
    fields(value, 'path size_bytes sha256', 'binding')
    require(type(value['size_bytes']) is int and 0 < value['size_bytes'] <= maximum
            and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'binding size/hash')
    return read_file(value['path'], keep=keep, maximum=maximum, expected=value)


def binding(p):
    return read_file(p, keep=False)


def save(p, document):
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(document))
        stream.flush()
        os.fsync(stream.fileno())
    if os.geteuid() == 0:
        os.chown(p, 1000, 1000)
    directory = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return binding(p)


def inventory(value, root, required, *, extras=()):
    require(path(value['path']).parent == root, 'inventory root differs')
    document = parse(bound(value))
    require(type(document.get('files')) is list and 0 < len(document['files']) <= 256, 'finite packet inventory')
    result = {}
    for row in document['files']:
        fields(row, 'path size_bytes sha256', 'inventory member')
        name = row['path']
        require(type(name) is str and Path(name).name == name and name not in ('.', '..') and name not in result,
                'unique flat inventory member')
        require(name not in ('initialize_program.py', 'initialize-program.py'), 'archive reinitialization forbidden')
        result[name] = dict(row, path=str(root / name))
        bound(result[name], keep=False)
    require(required <= set(result), 'incomplete operator closure')
    require({p.name for p in root.iterdir()} <= set(result) | {Path(value['path']).name} | set(extras),
            'unbound extra packet member')
    return result


def configuration(config_path, digest):
    raw = read_file(config_path)
    require(hashlib.sha256(raw).hexdigest() == digest, 'configuration SHA256 differs')
    c = parse(raw)
    fields(c, 'schema_version source_revision boot_id evidence_root operator_root study_root admission_start '
           'qualification_inventory operator_inventory python setpriv prepare_configuration pilot_archive pilot_sidecar '
           'resume_inputs execution_authority phase18_authority', 'study configuration')
    require(c['schema_version'] == SCHEMA and c['source_revision'] == SOURCE, 'actual clean A2 required')
    require(c['execution_authority'] is False and c['phase18_authority'] is False, 'configuration grants no authority')
    require(type(c['boot_id']) is str and re.fullmatch('[0-9a-f-]{36}', c['boot_id']), 'verified boot identity')
    require(path(c['evidence_root']) == E and path(c['study_root']) == E / 'daycap-resume-study-2', 'fixed fresh E26 roots')
    require(path(c['admission_start']['path']) == E / 'v26-ext001-execute.py.result.json', 'actual original EXT001 anchor required')
    admission_anchor(c)
    root = path(c['operator_root'])
    require(root.is_relative_to(E) and root not in (E, P), 'separate reviewed E26 operator root')
    for key in ('python', 'setpriv', 'prepare_configuration', 'pilot_sidecar'):
        bound(c[key], keep=False)
    require(path(c['setpriv']['path']) == Path('/usr/bin/setpriv'), 'fixed setpriv image')
    bound(c['pilot_archive'], keep=False, maximum=16 * 1024**3)
    extras = {Path(config_path).name} if Path(config_path).parent == root else set()
    if Path(c['prepare_configuration']['path']).parent == root:
        extras.add(Path(c['prepare_configuration']['path']).name)
    operators = inventory(c['operator_inventory'], root, OPERATORS, extras=extras)
    require(operators['run_daycap_study.py'] == binding(Path(__file__).resolve()), 'study operator changed')
    qualifiers = inventory(c['qualification_inventory'], P, QUALIFIERS,
        extras={'original-public-inputs-reuse.json', 'd124-combined-search-v26.json',
                'known-hosts-exact-localhost', 'd124-attestation-v26.json'})
    installer = types.ModuleType('bound_installed_e26_packet_verifier')
    installer.__file__ = qualifiers['install_v26.py']['path']
    exec(compile(bound(qualifiers['install_v26.py']), installer.__file__, 'exec'), installer.__dict__)
    installer.verify_packet(P, c['qualification_inventory']['sha256'], installed=True)
    require(qualifiers['isolation_core.py']['sha256'] == CORE_SHA, 'original isolation core changed')
    release = parse(bound(qualifiers['release-bindings.json']))
    require(release['source_revision'] == SOURCE and release['boot_id'] == c['boot_id'], 'actual qualification release differs')
    require(c['pilot_archive']['sha256'] == release['archive_sha256'], 'actual release archive differs')
    finite = parse(bound(qualifiers['finite-qualification-plan.json']))
    require(finite['qualification_budget_seconds'] == QUALIFY_PREP_SECONDS
            and finite['whole_study_deadline_seconds'] == DAY_SECONDS, 'finite qualification budget differs')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == c['boot_id'], 'stand boot changed')
    retained_inputs(c)
    return c, operators, qualifiers, release


class Budget:
    def __init__(self, start_ns):
        require(type(start_ns) is int and 0 < start_ns <= time.monotonic_ns(), 'actual same-boot monotonic start required')
        self.start = start_ns
        self.work = start_ns + WORK_SECONDS * NANO
        self.end = start_ns + DAY_SECONDS * NANO
        self.qualify_prep = min(1210558041457866, time.monotonic_ns() + QUALIFY_PREP_SECONDS * NANO,
            self.end - (COLLECTION_SECONDS + ANALYSIS_SECONDS + 2 * CLEANUP_SECONDS) * NANO)
        require(self.qualify_prep > time.monotonic_ns(), 'remaining original study cannot fit bounded collection, analysis and cleanup')

    def phase(self, seconds):
        ceiling = self.work - (ANALYSIS_SECONDS + CLEANUP_SECONDS) * NANO if seconds == COLLECTION_SECONDS else self.work
        deadline = min(ceiling, time.monotonic_ns() + seconds * NANO)
        require(deadline > time.monotonic_ns(), 'study work cutoff reached')
        return deadline


def admission_anchor(c):
    record = parse(bound(c['admission_start']))
    start, end = record['started_monotonic_ns'], record['completed_monotonic_ns']
    require(record['operator'] == 'v26-ext001-execute.py' and record['exit_code'] == 0
            and record['leader_reaped'] is True and type(start) is int and type(end) is int
            and 0 < start <= end <= time.monotonic_ns(), 'actual successful EXT001 monotonic anchor required')
    return start


def seconds_left(deadline):
    remaining = (deadline - time.monotonic_ns()) / NANO
    require(remaining > 0, 'absolute deadline reached')
    return remaining


def start_ticks(pid):
    text = Path(f'/proc/{pid}/stat').read_text()
    return int(text[text.rfind(')') + 2:].split()[19])


def descendants(pid):
    result, pending = {}, [pid]
    while pending:
        parent = pending.pop()
        try:
            children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
        except FileNotFoundError:
            continue
        for child in children:
            child = int(child)
            try:
                result[child] = start_ticks(child)
            except FileNotFoundError:
                continue
            pending.append(child)
            require(len(result) <= 4096, 'owned process-tree bound exceeded')
    return result


def executable_identity(pid):
    # /proc/PID/exe intentionally resolves a sealed memfd as well as an image.
    digest, size = hashlib.sha256(), 0
    with open(f'/proc/{pid}/exe', 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_METADATA, 'bounded actual native image')
        for block in iter(lambda: stream.read(1024**2), b''):
            size += len(block)
            require(size <= MAX_METADATA, 'native image bound')
            digest.update(block)
        require(stamp(before) == stamp(os.fstat(stream.fileno())), 'native image changed')
    return size, digest.hexdigest()


def send_pidfd(pid, ticks, sig, *, native=None):
    fd = os.pidfd_open(pid)
    try:
        require(start_ticks(pid) == ticks, 'owned PID reused')
        if native is not None:
            require(executable_identity(pid) in native, 'native executable identity changed')
        require(start_ticks(pid) == ticks, 'owned PID changed during identity read')
        signal.pidfd_send_signal(fd, sig)
    finally:
        os.close(fd)


def subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.prctl(36, 1, 0, 0, 0) == 0, 'owned child subreaper setup failed')
    observed = ctypes.c_int()
    require(libc.prctl(37, ctypes.byref(observed), 0, 0, 0) == 0 and observed.value == 1,
            'owned child subreaper readback failed')


def reap_adopted():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


class OwnedProcess:
    """Signal authenticated native descendants before touching their owner."""
    def __init__(self, argv, log, native, *, protect_native=True):
        self.process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                        start_new_session=True, close_fds=True)
        self.leader_ticks = start_ticks(self.process.pid)
        self.native = native
        self.protect_native = protect_native
        self.observed = {}
        self.forced = []

    def observe(self):
        try:
            if start_ticks(self.process.pid) == self.leader_ticks:
                self.observed.update(descendants(self.process.pid))
        except FileNotFoundError:
            pass
        # Subreaper adoption after owner loss stays inside this dedicated driver.
        self.observed.update(descendants(os.getpid()))
        return dict(self.observed)

    def live(self):
        result = {}
        for pid, ticks in self.observe().items():
            if pid == self.process.pid:
                continue
            try:
                if start_ticks(pid) == ticks:
                    result[pid] = ticks
            except FileNotFoundError:
                pass
        return result

    def stop(self, deadline):
        # Never SIGTERM the owner first: its native group can be in a separate
        # session. Match the actual executable bytes, then give recovery 120s.
        for pid, ticks in self.live().items():
            try:
                if executable_identity(pid) in self.native:
                    send_pidfd(pid, ticks, signal.SIGTERM, native=self.native)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if not self.protect_native and self.process.poll() is None:
            send_pidfd(self.process.pid, self.leader_ticks, signal.SIGTERM)
        grace = min(deadline, time.monotonic_ns() + OWNER_CLEANUP_SECONDS * NANO)
        while time.monotonic_ns() < grace:
            if self.process.poll() is not None:
                reap_adopted()
                if not self.live():
                    return
            time.sleep(.05)
        # A failed cleanup is retained even if forced reaping later succeeds.
        # Escalation remains pidfd-bound to our own native executable bytes.
        for pid, ticks in self.live().items():
            try:
                if executable_identity(pid) in self.native:
                    self.forced.append(pid)
                    send_pidfd(pid, ticks, signal.SIGKILL, native=self.native)
            except (FileNotFoundError, ProcessLookupError):
                pass
        grace = min(deadline, time.monotonic_ns() + OWNER_CLEANUP_SECONDS * NANO)
        while time.monotonic_ns() < grace and self.process.poll() is None:
            time.sleep(.05)
        for pid, ticks in self.live().items():
            try:
                send_pidfd(pid, ticks, signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if self.process.poll() is None:
            send_pidfd(self.process.pid, self.leader_ticks, signal.SIGTERM)
        grace = min(deadline, time.monotonic_ns() + 10 * NANO)
        while time.monotonic_ns() < grace and (self.process.poll() is None or self.live()):
            self.process.poll()
            reap_adopted()
            time.sleep(.05)
        for pid, ticks in self.live().items():
            try:
                self.forced.append(pid)
                send_pidfd(pid, ticks, signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if self.process.poll() is None:
            self.forced.append(self.process.pid)
            send_pidfd(self.process.pid, self.leader_ticks, signal.SIGKILL)
        self.process.wait(timeout=min(5, seconds_left(deadline)))
        reap_adopted()
        require(not descendants(os.getpid()), 'owned descendants remain after cleanup')

    def wait(self, deadline):
        while self.process.poll() is None:
            self.observe()
            seconds_left(deadline)
            time.sleep(min(.1, seconds_left(deadline)))
        self.process.wait()
        reap_adopted()
        # An exited owner is not proof that its separate native group is gone.
        require(not self.live(), 'owner exited with live descendants')
        return self.process.returncode


def restoration_status(receipt, *, attempt_id, request_sha256, authorization_sha256, expected_prestate):
    for name, expected in (("attempt_id", attempt_id), ("request_sha256", request_sha256),
                           ("authorization_sha256", authorization_sha256), ("action_id", "Q16b")):
        if receipt.get(name) != expected:
            raise ValueError("executor receipt binding differs: " + name)
    schema = receipt.get("schema_version")
    if schema == "cpu-prefetch-stage17-phase-action-failure/6":
        operation = receipt.get("quarantine_operation")
        if not isinstance(operation, dict) or type(operation.get("performed")) is not bool:
            raise ValueError("failure quarantine observation missing")
        quarantined = operation["performed"]
        readback = receipt.get("recovery_readback")
        expected_field = 'requested_hex'
        complete = False
    elif schema == "cpu-prefetch-stage17-phase-action-completion/6":
        quarantined = receipt.get("quarantined")
        if type(quarantined) is not bool:
            raise ValueError("completion quarantine observation missing")
        readback = receipt.get("live_restoration_readback")
        expected_field = 'expected_hex'
        complete = True
    else:
        raise ValueError("unsupported executor receipt schema")
    for field in ("leader_reaped", "process_group_gone", "restoration_verified"):
        if type(receipt.get(field)) is not bool:
            raise ValueError("missing actual restoration/cleanup observation: " + field)
    verified = (receipt["restoration_verified"] and not quarantined
                and receipt["leader_reaped"] and receipt["process_group_gone"])
    if verified:
        if not isinstance(readback, list) or not readback:
            raise ValueError("claimed restoration lacks actual readback")
        expected = {row["cpu"]: row["complete_value_hex"] for row in expected_prestate}
        require(set(expected) == {0, 1, 8}, "exact restoration CPU coverage required")
        seen = set()
        for row in readback:
            if (not isinstance(row, dict) or type(row.get("cpu")) is not int
                    or row["cpu"] < 0 or row["cpu"] in seen or row.get("matches") is not True
                    or not isinstance(row.get(expected_field), str)
                    or re.fullmatch(r"[0-9a-f]{16}", row[expected_field]) is None
                    or row.get("observed_hex") != row[expected_field]):
                raise ValueError("invalid hardware restoration readback")
            require(expected.get(row["cpu"]) == row[expected_field], "restoration differs from signed prestate")
            seen.add(row["cpu"])
        require(seen == set(expected), "restoration omits CPUs")
    return {"hardware_restoration_verified": verified, "executor_completed": complete,
            "executor_quarantined": quarantined}


RETAINED_BINDINGS = {'administration_manifest': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/d256-admin-1/manifest.json',
                             '69baa4f6ea40f461be1dccff5f40ed4c4cea7db0ce1da3008af11b4c3fb8d871'),
 'clocks': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/clock-qualification-v26-1/complete.json',
            '85af984ddc7ff2bae31ed1c484dfa10fe663ed2ffa423ab5f040b5d5776b18b2'),
 'current_journal': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/journal/stage17-state-journal-000009.json',
                     'cbdebb6569c179c025b26bdd6a28dccd78ceb465c2377c964a5e6d821395d3d4'),
 'isolation_operator': ('/run/cpu-prefetch-recovery-v26-qualified-1/isolation_core.py',
                        '49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'),
 'original_preparation': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/isolation-preparation-v26-1/prospective-prestate.json',
                          '1d1df544667430cf0d834ece3ede04e9a5b05751503d819c869bf30be002e0ef'),
 'original_study': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/daycap-study-1/study-result.json',
                    'cf80e3f418303b05a2c700b83c9c794feb6c0c7346000e483e3bbd0aa272f481'),
 'q15_completion': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/stage17-q15_w-completion-v4.json',
                    '3476322c1521674c0801422bd3630850b20a0afd805a1d2a0d6d09b4b40cde92'),
 'q15_r': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/stage17-q15-r-result-v4.json',
           'fc9aa0d4f5cab80b9151eeeb02ab7b3ccde2f8e7ee3bc114284e918a242ac215'),
 'q15_session': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/q15-owned-session-terminal-1.json',
                 '48e69fe769a8dd4b46093c90f990b424873bdc660c1707ecc108f8fb2d118974'),
 'q15_w': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/stage17-q15-w-result-v4.json',
           'ac9ffcb7aaa0e161ebc1ac91d3179a2e23d3a2e90a5749f3862c0079164c084d'),
 'restoration': ('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/clock-qualification-v26-1/restoration.json',
                 'f8bbf300384c06d35cd89993f11d4876c1fdae8d5ee98733259c867aae3c5f4e')}

def retained_inputs(c):
    d = parse(bound(c['resume_inputs']))
    fields(d, 'schema_version boot_id source_revision worker_sha256 isolation_configuration bindings '
           'execution_authority phase18_authority', 'retained qualification inputs')
    require(d['schema_version'] == 'software-d257-retained-qualification/1'
            and d['source_revision'] == SOURCE and d['boot_id'] == c['boot_id']
            and d['worker_sha256'] == '305cedfc5438c68ececfa6a0f954d757112a50c87f687b93ad7b013b7ed757dd'
            and d['execution_authority'] is False and d['phase18_authority'] is False,
            'retained qualification source, boot or authority differs')
    require(set(d['bindings']) == set(RETAINED_BINDINGS), 'closed retained evidence population')
    documents = {}
    for key, (expected_path, digest) in RETAINED_BINDINGS.items():
        b = d['bindings'][key]
        require((b['path'], b['sha256']) == (expected_path, digest), 'retained evidence binding differs: '+key)
        raw = bound(b)
        if key != 'isolation_operator':
            documents[key] = parse(raw)
    require(documents['clocks']['both_pairs_passed'] is True, 'retained clocks did not pass')
    require(documents['q15_r']['terminal_state'] == 'Q15_R_READ_ONLY_COMPLETE'
            and documents['q15_r']['quarantined'] is False, 'retained Q15-R failed')
    require(documents['q15_w']['terminal_state'] == 'Q15_W_RESTORED_COMPLETE'
            and documents['q15_w']['restoration_verified'] is True
            and documents['q15_w']['quarantined'] is False, 'retained Q15-W failed')
    require(all(documents['q15_completion'][key] is True for key in
                ('leader_reaped','process_group_gone','restoration_verified'))
            and documents['q15_completion']['quarantined'] is False, 'retained Q15 cleanup failed')
    require(documents['q15_session']['exit_code'] == 0 and documents['q15_session']['leader_reaped'] is True
            and documents['q15_session']['cleanup_error'] is None, 'retained Q15 session failed')
    require(all(documents['restoration'][key] is True for key in
                ('verified','partition_absent','root_restoration_verified','maintenance_restoration_verified'))
            and documents['restoration']['errors'] == [], 'original isolation restoration failed')
    old = documents['original_study']
    require(old['success'] is False and old['automatic_retries'] == 0
            and old['reduced_q16b_calibration_done'] is False and len(old['phases']) == 1
            and old['phases'][0]['phase'] == 'qualification', 'original Q16b was already attempted')
    original = documents['original_preparation']['operator_config']
    expected_config = dict(original, evidence_root=str(E/'isolation-resume-1'),
                           lifecycle_seconds=72000, protected_work_ns=65160*NANO)
    require(d['isolation_configuration'] == expected_config, 'fresh isolation configuration differs')
    require(d['bindings']['isolation_operator']['sha256'] == CORE_SHA, 'original infrastructure source differs')
    return d


def load_resume_isolation(c):
    inputs = retained_inputs(c)
    b = inputs['bindings']['isolation_operator']
    iso = types.ModuleType('bound_d257_original_infrastructure')
    iso.__file__ = b['path']
    exec(compile(bound(b), iso.__file__, 'exec'), iso.__dict__)
    config = inputs['isolation_configuration']
    iso.configure({'operator_config': config})
    old = parse(bound(inputs['bindings']['original_preparation']))
    def preparation():
        pre = parse(read_file(iso.Q/'prospective-prestate.json'))
        require(pre['operator_config'] == config and pre['operator_script_sha256'] == CORE_SHA
                and pre['source_revision'] == SOURCE and pre['boot_id'] == c['boot_id']
                and pre['partition_path'] == str(CG), 'fresh observed isolation proof differs')
        require(pre['prestate']['root'] == old['prestate']['root'], 'root state changed since qualification')
        for name, state in old['prestate']['maintenance_before'].items():
            actual = pre['prestate']['maintenance_before'][name]
            require(actual['UnitFileState'] == state['UnitFileState']
                    and (name not in iso.TIMER_SERVICES or actual['ActiveState'] == state['ActiveState']),
                    'maintenance state changed since qualification')
        return pre
    return types.SimpleNamespace(ISO=iso, Q=iso.Q, config=config, preparation=preparation,
        isolated_state=iso.isolated_state, restore=iso.restore)


def prepared(c, operators, release, *, allow_completed=False):
    p = E / 'daycap-collection-preparation-1/prepared-phase.json'
    pb = binding(p)
    d = parse(bound(pb))
    fields(d, 'schema_version source_revision boot_id repository_root evidence_root output_root worker files wrappers '
           'execution_authority phase18_authority', 'prepared phase')
    require(d['schema_version'] == PREPARED_SCHEMA and d['source_revision'] == c['source_revision']
            and d['boot_id'] == c['boot_id'], 'prepared actual release differs')
    require(d['execution_authority'] is False and d['phase18_authority'] is False, 'preparation grants no authority')
    require(path(d['repository_root']) == E / 'admission-root' and path(d['evidence_root']) == E, 'prepared roots')
    fields(d['files'], 'request authorization signature plan cli_configuration analysis_config limits hardware_control', 'prepared files')
    files = {k: bound(v) for k, v in d['files'].items()}
    fields(d['wrappers'], 'cli owner_check analysis', 'prepared wrappers')
    for key, name in (('cli', 'daycap_cli.py'), ('owner_check', 'owner_check.py'), ('analysis', 'analyze_daycap.py')):
        require(d['wrappers'][key] == operators[name], 'actual reviewed wrapper differs')
    require(d['worker']['sha256'] == release['worker_sha256'], 'actual qualified worker hash differs')
    require(path(d['worker']['path']) == E / 'local-bundle-extract' / release['bundle_name'] /
            'release/bin/cpu_prefetch_runner', 'actual qualified worker path differs')
    bound(d['worker'], keep=False)
    plan, request, auth = (parse(files[k]) for k in ('plan', 'request', 'authorization'))
    require(plan['source_revision'] == SOURCE and plan['clean_source'] is True and plan['action_id'] == 'Q16b'
            and plan['schema_version'] == 'cpu-prefetch-stage17-formal-service-plan/3'
            and plan['method_id'] == 'SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1'
            and len(plan['captures']) == 120 and plan['repetitions_per_cell'] == 2
            and plan['budget']['watchdog_ns'] == NATIVE_SECONDS * NANO, 'exact approved120 daycap family required')
    require(request['schema_version'] == 'cpu-prefetch-stage17-fixed-action-request/6'
            and request['action_id'] == 'Q16b' and request['action_inputs']['plan'] == plan,
            'signed request/actual plan differs')
    require(auth['request_binding'] == d['files']['request'] and auth['action_id'] == 'Q16b', 'actual authorization binding')
    output = path(d['output_root'])
    require(output == path(request['evidence_root_binding']['absolute_path']) and output.name == plan_sha256(plan),
            'exact signed family output root required')
    if not allow_completed:
        require(not any((output / name).exists() for name in ('stage17-q16b-completion-v6.json',
                'stage17-q16b-failure-v6.json', 'stage17-attempt.json')), 'family already consumed; no retry')
    limits = parse(files['limits'])
    fields(limits, 'address_space_bytes memlock_bytes', 'owner limits')
    require(limits == dict(address_space_bytes=WORKER_AS, memlock_bytes=MEMLOCK)
            and max(i['execution_budget']['memory_bytes'] for i in plan['captures']) == WORKER_AS
            and max(i['resources']['total_mapping_bytes'] for i in plan['captures']) == MEMLOCK,
            'limits must equal actual plan worker/mapping maxima')
    require(parse(files['hardware_control']) == request['action_inputs']['hardware_control'], 'actual signed hardware prestate')
    cli_config = parse(files['cli_configuration'])
    require(cli_config['repository_root'] == d['repository_root'] and cli_config['boot_id'] == c['boot_id'], 'actual CLI configuration')
    analysis = parse(files['analysis_config'])
    require(analysis['repository_root'] == d['repository_root'] and analysis['evidence_root'] == str(E)
            and analysis['boot_id'] == c['boot_id'] and analysis['execution_authority'] is False, 'analysis scope differs')
    for key in ('request', 'authorization', 'signature'):
        require(analysis['files'][key] == d['files'][key], 'analysis signed input differs')
    require(path(analysis['analysis_root']).is_relative_to(E), 'fresh E26 analysis root required')
    return pb, d, request, analysis


def cli_command(c, d):
    return [c['python']['path'], '-B', d['wrappers']['cli']['path'], '--configuration',
        d['files']['cli_configuration']['path'], '--configuration-sha256', d['files']['cli_configuration']['sha256'],
        'execute-formal', '--repository-root', d['repository_root'], '--evidence-root', str(E),
        '--authorization', d['files']['authorization']['path'], '--signature', d['files']['signature']['path'],
        '--pilot-archive', c['pilot_archive']['path'], '--pilot-sidecar', c['pilot_sidecar']['path']]


def private_command(c, args, role, mode, prepared_sha, deadline):
    argv = [c['python']['path'], '-B', str(Path(__file__).resolve()), '--' + mode, '--role', role,
            '--config', str(args.config), '--config-sha256', args.config_sha256,
            '--global-deadline-ns', str(deadline)]
    if prepared_sha:
        argv += ['--prepared-phase-sha256', prepared_sha]
    return argv


def owner_entry(c, operators, release, args):
    require(args.role in ('check', 'collection', 'analysis'), 'fixed owner role')
    intent = parse(read_file(Path(c['study_root']) / 'study-intent.json'))
    require(intent['configuration_sha256'] == args.config_sha256 and intent['source_revision'] == SOURCE,
            'private owner requires actual exclusive study intent')
    require(os.getppid() == intent['supervisor_pid'] and start_ticks(os.getppid()) == intent['supervisor_start_ticks'],
            'private owner requires the actual live study parent')
    pb, d, _, _ = prepared(c, operators, release) if args.role != 'analysis' else prepared_after(c, operators, release)
    require(pb['sha256'] == args.prepared_phase_sha256, 'bound prepared phase changed')
    seconds_left(args.global_deadline_ns)
    native = args.role != 'analysis'
    if args.owner:
        require(os.geteuid() == 0 and threading.active_count() == 1 and len(list(Path('/proc/self/task').iterdir())) == 1,
                'single-threaded root owner handoff required')
        resource.setrlimit(resource.RLIMIT_AS, ((WORKER_AS if native else 16 * 1024**3),) * 2)
        resource.setrlimit(resource.RLIMIT_MEMLOCK, ((MEMLOCK if native else 8 * 1024**2),) * 2)
        if native:
            require((CG / 'cgroup.procs').read_text().strip() == '', 'fresh retained partition must be empty')
            fd = os.open(CG / 'cgroup.procs', os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                raw = (str(os.getpid()) + '\n').encode()
                require(os.write(fd, raw) == len(raw), 'partition entry short write')
            finally:
                os.close(fd)
        os.sched_setaffinity(0, {2 if native else 3})
        names = CAP_NAMES if native else ('sys_ptrace',)
        caps = '-all,' + ','.join('+' + name for name in names)
        argv = [c['setpriv']['path'], '--reuid=1000', '--regid=1000', '--clear-groups',
                '--bounding-set=' + caps, '--inh-caps=' + caps, '--ambient-caps=' + caps,
                *private_command(c, args, args.role, 'inner', pb['sha256'], args.global_deadline_ns)]
        os.execv(argv[0], argv)
    require(os.getresuid() == (1000,) * 3 and os.getresgid() == (1000,) * 3 and not os.getgroups(), 'owner identity differs')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    mask = CAP_MASK if native else ANALYSIS_CAP_MASK
    require(all(int(status[k].strip(), 16) == mask for k in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')),
            'owner actual capability mask differs')
    require(os.sched_getaffinity(0) == {2 if native else 3}, 'owner placement differs')
    if native:
        require(resource.getrlimit(resource.RLIMIT_AS) == (WORKER_AS,) * 2
                and resource.getrlimit(resource.RLIMIT_MEMLOCK) == (MEMLOCK,) * 2, 'owner finite limits differ')
    if args.role == 'check':
        argv = [c['python']['path'], '-B', d['wrappers']['owner_check']['path'], '--prepared-phase', pb['path'],
                '--prepared-phase-sha256', pb['sha256'], '--global-deadline-ns', str(args.global_deadline_ns)]
    elif args.role == 'collection':
        collection_intent = parse(read_file(Path(c['study_root']) / 'collection-intent.json'))
        require(collection_intent['prepared_phase'] == pb and collection_intent['argv'] == cli_command(c, d)
                and collection_intent['owner_check_passed'] is True and collection_intent['automatic_retries'] == 0
                and collection_intent['deadline_monotonic_ns'] == args.global_deadline_ns,
                'collection requires exact checked intent')
        argv = cli_command(c, d)
    else:
        b = d['files']['analysis_config']
        argv = [c['python']['path'], '-B', d['wrappers']['analysis']['path'], '--config', b['path'],
                '--config-sha256', b['sha256'], '--global-deadline-ns', str(args.global_deadline_ns)]
    os.execv(argv[0], argv)


def prepared_after(c, operators, release):
    # Completed execution is expected here. Authenticate metadata exactly as
    # before execution without reusing the pre-execution no-attempt assertion.
    return prepared(c, operators, release, allow_completed=True)


class Study:
    def __init__(self, args, budget, c, operators, qualifiers, release):
        self.args, self.budget, self.c = args, budget, c
        self.operators, self.qualifiers, self.release = operators, qualifiers, release
        self.root = Path(c['study_root'])
        self.clock = load_resume_isolation(c)
        self.active = None
        self.result = dict(schema_version='software-d257-collection-resume-result/1', source_revision=SOURCE,
            configuration_sha256=args.config_sha256, success=False, errors=[], phases=[],
            reduced_q16b_calibration_done=False,
            automatic_retries=0, ext007_admitted=False, execution_authority=False, phase18_authority=False,
            start_monotonic_ns=budget.start, work_cutoff_ns=budget.work, hard_deadline_ns=budget.end,
            supervisor_pid=os.getpid(), supervisor_start_ticks=start_ticks(os.getpid()))

    def command(self, label, argv, deadline):
        configuration(self.args.config, self.args.config_sha256)
        seconds_left(deadline)
        record = dict(phase=label, argv=argv, started_monotonic_ns=time.monotonic_ns(), deadline_ns=deadline)
        owned = None
        try:
            with (self.root / (label + '.log')).open('xb') as log:
                # Size is read from the actual qualified image, never guessed.
                worker = E / 'local-bundle-extract' / self.release['bundle_name'] / 'release/bin/cpu_prefetch_runner'
                native = {(worker.stat().st_size, self.release['worker_sha256'])}
                clock = E / 'local-bundle-extract' / self.release['bundle_name'] / 'release/bin/cpu_prefetch_q15_clock_qualification_tool'
                native.add((clock.stat().st_size, self.release['clock_sha256']))
                self.active = OwnedProcess(argv, log, native, protect_native=label in ('qualification', 'collection'))
                owned = self.active
                record['pid'] = self.active.process.pid
                code = self.active.wait(deadline)
                require(code == 0, label + ' failed: ' + str(code))
                record['exit_code'] = code
                self.active = None
        finally:
            record['exit_code'] = owned.process.returncode if owned is not None else None
            record['leader_reaped'] = owned is not None and owned.process.returncode is not None
            record['completed_monotonic_ns'] = time.monotonic_ns()
            self.result['phases'].append(record)
            save(self.root / (label + '-result.json'), record)

    def check_isolation(self):
        pre = self.clock.preparation()
        iso = self.clock.ISO
        require([iso.CG.stat().st_dev, iso.CG.stat().st_ino] == pre['prestate']['partition_identity'],
                'actual retained qualification partition identity changed')
        require([iso.CG.parent.stat().st_dev, iso.CG.parent.stat().st_ino] == pre['prestate']['unit_identity'],
                'actual qualification unit identity changed')
        state = self.clock.isolated_state()
        require(state['partition']['cgroup.procs'] == ''
                and 'populated 0' in state['partition']['cgroup.events'].splitlines(), 'actual retained partition not empty')
        iso.verify_remaining_lifetime(pre['prestate'], NATIVE_SECONDS * NANO, OWNER_CLEANUP_SECONDS * NANO)
        return pre

    def restore(self):
        report = dict(verified=False, errors=[])
        try:
            iso = self.clock.ISO
            if not (self.clock.Q / 'prospective-prestate.json').exists():
                require(not CG.parent.exists(), 'unrecorded/live resume isolation remains')
                old = parse(bound(retained_inputs(self.c)['bindings']['original_preparation']))['prestate']
                require(iso.root_state() == old['root'], 'original actual root differs before rearm')
                for name, state in old['maintenance_before'].items():
                    actual = iso.systemd_state(name)
                    require(actual['UnitFileState'] == state['UnitFileState']
                            and (name not in iso.TIMER_SERVICES or actual['ActiveState'] == state['ActiveState']),
                            'maintenance differs before rearm')
                prior = self.clock.Q / 'restoration.json'
                if prior.exists():
                    require(parse(read_file(prior))['verified'] is True, 'partial rearm cleanup failed')
                report.update(verified=True, not_rearmed=True)
                self.result['partition_restoration'] = report
                save(self.root / 'partition-restoration.json', report)
                return True
            pre = self.clock.preparation()
            receipt = self.clock.Q / 'restoration.json'
            if receipt.exists():
                prior = parse(read_file(receipt))
                require(prior['verified'] is True and not iso.CG.exists(), 'prior isolation restoration incomplete')
                require(iso.root_state() == pre['prestate']['root'], 'original actual root differs')
                for name, state in pre['prestate']['maintenance_before'].items():
                    actual = iso.systemd_state(name)
                    require(actual['UnitFileState'] == state['UnitFileState']
                            and (name not in iso.TIMER_SERVICES or actual['ActiveState'] == state['ActiveState']),
                            'original maintenance readback differs')
                report.update(verified=True, already_restored=True, receipt=binding(receipt))
            else:
                # Original core independently attempts maintenance restoration
                # even if its exact empty-unit/keeper identity checks fail.
                self.clock.restore(pre['prestate'])
                actual = parse(read_file(receipt))
                require(actual['verified'] is True and actual['partition_absent'] is True,
                        'original core restoration not verified')
                report.update(verified=True, receipt=binding(receipt))
        except BaseException as error:
            report['errors'].append(repr(error))
        self.result['partition_restoration'] = report
        save(self.root / 'partition-restoration.json', report)
        return report['verified']

    def bounded_restore(self):
        """Fork the original restoration so its total work also has a ceiling.

        The child inherits the already authenticated core, not new configuration
        or executable callbacks. PID1/keeper operations remain the core's own
        identity-checked operations. No new service is created.
        """
        deadline = min(self.budget.end - 5 * NANO, time.monotonic_ns() + CLEANUP_SECONDS * NANO)
        require(deadline > time.monotonic_ns(), 'no absolute restoration time remains')
        pid = os.fork()
        if pid == 0:
            try:
                os._exit(0 if self.restore() else 1)
            except BaseException:
                os._exit(1)
        ticks, observed = start_ticks(pid), {}
        status_code = None
        while time.monotonic_ns() < deadline:
            observed.update(descendants(pid))
            done, status_code = os.waitpid(pid, os.WNOHANG)
            if done:
                record = self.root / 'partition-restoration.json'
                require(record.is_file(), 'root restoration child omitted its observation')
                report = parse(read_file(record))
                self.result['partition_restoration'] = report
                reap_adopted()
                require(not descendants(os.getpid()), 'root restoration left owned descendants')
                return os.waitstatus_to_exitcode(status_code) == 0 and report['verified'] is True
            time.sleep(.1)
        # Only this fork and its actual descendants; never enumerate host jobs.
        observed.update(descendants(pid))
        for child, start in reversed(list(observed.items())):
            try:
                send_pidfd(child, start, signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError):
                pass
        try:
            send_pidfd(pid, ticks, signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass
        # The hard deadline never permits a new operational phase.
        reap_deadline = min(self.budget.end, time.monotonic_ns() + 2 * NANO)
        while time.monotonic_ns() < reap_deadline:
            reap_adopted()
            if not descendants(os.getpid()):
                break
            time.sleep(.02)
        self.result['partition_restoration'] = dict(verified=False, errors=['original core restoration deadline expired'])
        save(self.root / 'partition-restoration-timeout.json', self.result['partition_restoration'])
        return False

    def collection_receipt(self, d, request):
        output = Path(d['output_root'])
        receipts = [output / name for name in ('stage17-q16b-completion-v6.json', 'stage17-q16b-failure-v6.json')
                    if (output / name).is_file()]
        require(len(receipts) == 1, 'exactly one completion/failure receipt required')
        b = binding(receipts[0])
        state = restoration_status(parse(bound(b)), attempt_id=request['attempt_id'],
            request_sha256=d['files']['request']['sha256'], authorization_sha256=d['files']['authorization']['sha256'],
            expected_prestate=request['action_inputs']['hardware_control']['prestate'])
        self.result['collection_receipt'] = dict(binding=b, **state)
        require(state['executor_completed'] and state['hardware_restoration_verified'] and not state['executor_quarantined'],
                'collection did not complete with actual native/MSR restoration')

    def analysis_result(self, analysis):
        root = path(analysis['analysis_root'])
        complete_binding = binding(root / 'analysis-complete.json')
        complete = parse(bound(complete_binding))
        require(complete['status'] == 'ALL_120_ANALYZED' and complete['calibration_status'] == 'DESCRIPTIVE'
                and complete['captures'] == 120 and complete['cells'] == 60 and complete['repetitions_per_cell'] == 2
                and complete['all_raw_reconstructed_and_hash_checked'] is True and complete['canonical_spools_removed'] is True
                and complete['ext007_admitted'] is False
                and complete['execution_authority'] is False and complete['phase18_authority'] is False,
                'all120 independent analysis must be complete and DESCRIPTIVE without EXT007 authority')
        calibration = parse(bound(complete['report']))
        actual_plan = parse(bound(analysis['files']['request']))['action_inputs']['plan']
        require(calibration['source_revision'] == SOURCE and calibration['plan_sha256'] == plan_sha256(actual_plan)
                and calibration['stand_id'] == actual_plan['stand_id'], 'analysis actual signed source/plan/stand differs')
        require(calibration['action_id'] == 'Q16b' and calibration['method_id'] == 'SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1'
                and calibration['status'] == 'DESCRIPTIVE' and calibration['descriptive_summary_complete'] is True
                and calibration['tolerance_claim'] is None and calibration['tolerance_guarantee'] is False
                and calibration['report_provenance_authenticated'] is False
                and calibration['independent_runs_authenticated'] is False and calibration['family_validity_established'] is False
                and calibration['execution_authority'] is False and calibration['phase18_authority'] is False,
                'actual bound descriptive calibration incomplete or claiming old guarantee')
        require(len(calibration['run_sources']) == 120 and all(row['validity'] == 'VALID' for row in calibration['run_sources'])
                and len(calibration['derived_result']['cells']) == 60
                and all(row['valid_runs'] == 2 for row in calibration['derived_result']['cells']), 'complete120/cell evidence required')
        self.result['analysis_completion'] = complete_binding

    def run(self):
        self.root.mkdir(mode=0o700, exist_ok=False)
        os.chown(self.root, 1000, 1000)
        save(self.root / 'study-intent.json', self.result)
        old_handlers = {}
        def interrupted(number, frame):
            raise RuntimeError('study interrupted: ' + str(number))
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            old_handlers[sig] = signal.signal(sig, interrupted)
        restored = False
        pb = d = request = analysis = None
        try:
            inputs = retained_inputs(self.c)
            self.command('retained-admission', ['/usr/sbin/runuser', '-u', 'omaltsev', '--',
                self.c['python']['path'], '-B', str(E / 'd256-admin-1/stage17_e26_transition_repair.py'),
                'validate', '--manifest-sha256', inputs['bindings']['administration_manifest']['sha256'],
                '--pilot-archive', self.c['pilot_archive']['path'],
                '--pilot-sidecar', self.c['pilot_sidecar']['path']], self.budget.qualify_prep)
            admission = parse(read_file(self.root / 'retained-admission.log'))
            require(admission['status'] == 'PASS'
                    and admission['current_state'] == 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
                    and admission['resolutions'] == 6 and admission['transitions'] == 3
                    and admission['pilot_ready'] is False, 'retained actual qualification admission failed')
            config = self.c['prepare_configuration']
            self.command('preparation', [self.c['python']['path'], '-B', self.operators['prepare_collection.py']['path'],
                '--config', config['path'], '--config-sha256', config['sha256'], '--global-deadline-ns', str(self.budget.qualify_prep)],
                self.budget.qualify_prep)
            pb, d, request, analysis = prepared(self.c, self.operators, self.release)
            require(time.monotonic_ns() + (self.clock.config['lifecycle_seconds'] + self.clock.config['stop_seconds']) * NANO < self.budget.end,
                    'fresh keeper would exceed original absolute deadline')
            self.clock.ISO.prepare(self.clock.config)
            self.check_isolation()
            self.result['qualification_reused'] = True
            self.result['qualification_inputs'] = self.c['resume_inputs']
            self.check_isolation()
            self.command('owner-check', private_command(self.c, self.args, 'check', 'owner', pb['sha256'], self.budget.qualify_prep),
                         self.budget.qualify_prep)
            require(not descendants(os.getpid()), 'owner check left descendants')
            self.check_isolation()
            deadline = self.budget.phase(COLLECTION_SECONDS)
            save(self.root / 'collection-intent.json', dict(prepared_phase=pb, argv=cli_command(self.c, d),
                automatic_retries=0, owner_check_passed=True, deadline_monotonic_ns=deadline))
            self.command('collection', private_command(self.c, self.args, 'collection', 'owner', pb['sha256'], deadline), deadline)
            self.collection_receipt(d, request)
        except BaseException as error:
            self.result['errors'].append(repr(error))
        finally:
            for sig in old_handlers:
                signal.signal(sig, lambda n, f: self.result['errors'].append('signal during cleanup: ' + str(n)))
            if self.active is not None:
                try:
                    self.active.stop(self.budget.end)
                    if self.active.forced:
                        self.result['errors'].append('forced owned process cleanup: ' + repr(self.active.forced))
                except BaseException as error:
                    self.result['errors'].append('owned process cleanup: ' + repr(error))
                self.result['owned_process_cleanup'] = dict(pid=self.active.process.pid,
                    exit_code=self.active.process.returncode, leader_reaped=self.active.process.returncode is not None,
                    forced=list(self.active.forced))
                self.active = None
            if d is not None and request is not None and 'collection_receipt' not in self.result:
                try:
                    self.collection_receipt(d, request)
                except BaseException as error:
                    self.result['errors'].append('collection failure/restoration receipt: ' + repr(error))
            # Always consult the actual original fresh-qualification prestate.
            try:
                restored = self.bounded_restore()
            except BaseException as error:
                self.result['errors'].append('original-prestate restoration: ' + repr(error))
        try:
            if not self.result['errors'] and restored:
                for sig in old_handlers:
                    signal.signal(sig, interrupted)
                deadline = min(self.budget.work, time.monotonic_ns() + ANALYSIS_SECONDS * NANO)
                self.command('analysis', private_command(self.c, self.args, 'analysis', 'owner', pb['sha256'], deadline), deadline)
                self.analysis_result(analysis)
                seconds_left(self.budget.work)
                self.result['success'] = True
        except BaseException as error:
            self.result['errors'].append('analysis: ' + repr(error))
        finally:
            for sig in old_handlers:
                signal.signal(sig, lambda n, f: self.result['errors'].append('signal during final cleanup: ' + str(n)))
            if self.active is not None:
                try:
                    self.active.stop(self.budget.end)
                except BaseException as error:
                    self.result['errors'].append('analysis cleanup: ' + repr(error))
                self.active = None
                self.result['success'] = False
            if not restored or self.result['errors'] or time.monotonic_ns() >= self.budget.end:
                self.result['success'] = False
            self.result['reduced_q16b_calibration_done'] = self.result['success']
            self.result['completed_monotonic_ns'] = time.monotonic_ns()
            save(self.root / 'study-result.json', self.result)
            for sig, old in old_handlers.items():
                signal.signal(sig, old)
        return self.result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ('run', 'owner', 'inner'):
        modes.add_argument('--' + name, action='store_true')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--role', choices=('check', 'collection', 'analysis'))
    parser.add_argument('--prepared-phase-sha256')
    parser.add_argument('--global-deadline-ns', type=int)
    args = parser.parse_args()
    c, operators, qualifiers, release = configuration(args.config, args.config_sha256)
    if args.owner or args.inner:
        owner_entry(c, operators, release, args)
        return 1
    require(os.geteuid() == 0, 'root study driver required')
    require(threading.active_count() == 1, 'single-threaded root supervisor required')
    require('cpu-prefetch-recovery-v26-qualified-1.service' not in Path('/proc/self/cgroup').read_text(),
            'root supervisor must remain outside qualification unit')
    os.sched_setaffinity(0, {3})
    require(not descendants(os.getpid()), 'dedicated root supervisor must have no preexisting children')
    subreaper()
    budget = Budget(admission_anchor(c))
    result = Study(args, budget, c, operators, qualifiers, release).run()
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
