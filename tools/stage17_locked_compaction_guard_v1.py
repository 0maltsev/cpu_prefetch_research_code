"""D286 proposed platform guard; no experiment or continuation entry point.

Hold this context in the existing root recovery supervisor for the entire native
family. That supervisor must invoke verify() before every capture and retain its
existing deadlines and signal/child-reaping recovery. A crashed guard leaves its
durable lease occupied; explicit recover() is required before another use.
Changing this scientific platform control requires an approved amendment.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

CONTROL = Path('/proc/sys/vm/compact_unevictable_allowed')
BOOT = Path('/proc/sys/kernel/random/boot_id')
LEASE = Path('/run/cpu-prefetch-locked-compaction-v1.lease')


def require(value, message):
    if not value:
        raise RuntimeError('locked compaction guard: ' + message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def publish(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class LinuxControl:
    def boot(self):
        return BOOT.read_text().strip()

    def read(self):
        value = CONTROL.read_text().strip()
        require(value in ('0', '1'), 'unsupported actual sysctl value')
        return int(value)

    def write(self, value):
        require(type(value) is int and value in (0, 1), 'unsupported requested value')
        with CONTROL.open('w') as stream:
            stream.write(str(value) + '\n')


class Guard:
    """Exclusive, durable prestate and exact restoration, including failed entry."""
    def __init__(self, evidence_root, *, deadline_ns, control=None, lease=LEASE):
        self.root = Path(evidence_root).absolute()
        self.deadline_ns = deadline_ns
        self.control = control if control is not None else LinuxControl()
        self.lease = Path(lease)
        self.fd = None
        self.intent = None

    def lock(self):
        self.fd = os.open(self.lease, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.unlock()
            raise

    def unlock(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def lease_record(self):
        raw = os.pread(self.fd, 4097, 0)
        require(len(raw) <= 4096, 'oversized lease')
        return json.loads(raw) if raw else None

    def set_lease(self, value):
        raw = canonical(value)
        require(len(raw) <= 4096, 'oversized lease')
        # The lease is empty on entry. A partial write remains occupied and
        # cannot be mistaken for a usable lease after a crash.
        require(os.pwrite(self.fd, raw, 0) == len(raw), 'incomplete lease write')
        os.fsync(self.fd)

    def expected_lease(self):
        return dict(intent_path=str(self.root / 'intent.json'),
                    intent_sha256=hashlib.sha256(canonical(self.intent)).hexdigest())

    def verify(self):
        require(type(self.deadline_ns) is int and time.monotonic_ns() < self.deadline_ns,
                'original finite deadline expired')
        require(self.fd is not None and self.intent is not None, 'guard not acquired')
        require(self.control.boot() == self.intent['boot_id'], 'boot changed')
        require(self.lease_record() == self.expected_lease(), 'lease identity changed')
        actual = self.control.read()
        require(actual == 0, 'locked-page compaction became enabled')
        return dict(requested_value=0, observed_value=actual, verified=True)

    def __enter__(self):
        require(type(self.deadline_ns) is int and time.monotonic_ns() < self.deadline_ns,
                'original finite deadline expired')
        require(all(not p.is_symlink() for p in (self.root, *self.root.parents)),
                'nonsymlink evidence directory required')
        self.lock()
        try:
            require(self.lease_record() is None, 'unrestored prior lease; explicit recovery required')
            self.root.mkdir(mode=0o700)
            intent = dict(schema_version='cpu-prefetch-locked-compaction-intent/1',
                          boot_id=self.control.boot(), control_path=str(CONTROL),
                          requested_value=0, observed_prestate=self.control.read(),
                          deadline_monotonic_ns=self.deadline_ns,
                          supervisor_pid=os.getpid(), experiment_authority=False)
            publish(self.root / 'intent.json', intent)
            self.intent = intent
            self.set_lease(self.expected_lease())
            if intent['observed_prestate'] != 0:
                self.control.write(0)
            observed = self.verify()
            publish(self.root / 'prepared.json', dict(**observed, boot_id=intent['boot_id']))
            return self
        except BaseException:
            try:
                # Never restore if durable lease publication did not complete:
                # no control mutation has yet been attempted in that case.
                if self.intent is not None and self.lease_record() == self.expected_lease():
                    self.restore()
            finally:
                self.unlock()
            raise

    def restore(self):
        require(self.fd is not None and self.intent is not None, 'missing recovery prestate')
        require(self.control.boot() == self.intent['boot_id'], 'cannot restore across boots')
        before = self.intent['observed_prestate']
        report = dict(schema_version='cpu-prefetch-locked-compaction-restoration/1',
                      boot_id=self.intent['boot_id'], requested_value=before,
                      observed_value=before, verified=True,
                      intent_sha256=self.expected_lease()['intent_sha256'])
        path = self.root / 'restoration.json'
        occupied = self.lease_record()
        if occupied is None:
            require(path.is_file() and path.read_bytes() == canonical(report)
                    and self.control.read() == before, 'no verified prior restoration')
            return report
        require(occupied == self.expected_lease(), 'recovery lease identity changed')
        actual = self.control.read()
        if actual != before:
            self.control.write(before)
        observed = self.control.read()
        require(observed == before, 'exact original sysctl restoration failed')
        if path.exists():
            require(path.read_bytes() == canonical(report), 'prior restoration receipt changed')
        else:
            publish(path, report)
        # Keep recovery occupied until both exact readback and durable receipt.
        os.ftruncate(self.fd, 0)
        os.fsync(self.fd)
        return report

    def __exit__(self, *exception):
        try:
            self.restore()
        finally:
            self.unlock()


def recover(evidence_root, *, control=None, lease=LEASE):
    """Explicit recovery after owner death; never overrides a live holder."""
    root = Path(evidence_root).absolute()
    require(all(not p.is_symlink() for p in (root, *root.parents)), 'nonsymlink recovery root')
    raw = (root / 'intent.json').read_bytes()
    require(len(raw) <= 4096, 'oversized recovery intent')
    intent = json.loads(raw)
    require(intent['schema_version'] == 'cpu-prefetch-locked-compaction-intent/1'
            and intent['control_path'] == str(CONTROL) and intent['requested_value'] == 0
            and type(intent['observed_prestate']) is int and intent['observed_prestate'] in (0, 1),
            'invalid recovery intent')
    guard = Guard(root, deadline_ns=0, control=control, lease=lease)
    guard.intent = intent
    guard.lock()
    try:
        return guard.restore()
    finally:
        guard.unlock()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('smoke-check', 'recover'))
    parser.add_argument('--evidence-root', type=Path, required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'root control owner required')
    if args.mode == 'recover':
        report = recover(args.evidence_root)
    else:
        # Immediate bounded control/readback/restoration check, with no worker.
        with Guard(args.evidence_root, deadline_ns=time.monotonic_ns() + 5 * 10**9) as guard:
            report = guard.verify()
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
