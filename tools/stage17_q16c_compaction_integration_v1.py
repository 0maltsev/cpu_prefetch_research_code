"""D287 cold guard witnesses and private archive-handshake instrumentation.

No authority, native code change or root-control mutation occurs here. The
root supervisor holds D286's Guard and passes a separate READ-ONLY lease FD
and its bound witness to the existing evidence owner. The admitted owner uses
wrap_runner() for its private archive runner. Native launch and every next-
capture ACK are gated; a failed AFTER observation is raised only after the
existing broker has preserved that capture's custody.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import types

import stage17_archive_metadata_fast_v1 as metadata
import stage17_locked_compaction_guard_v1 as controls
import stage17_q16c_source_execution_v1 as source_execution


def require(value, message):
    if not value:
        raise RuntimeError('Q16c compaction integration: ' + message)


def process_identity(pid):
    raw = Path('/proc/' + str(pid) + '/stat').read_text()
    fields = raw[raw.rindex(')') + 2:].split()
    require(fields[0] not in ('Z', 'X', 'x'), 'root supervisor is no longer alive')
    return int(fields[19])


def check_readonly(fd):
    require(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY,
            'separate read-only lease descriptor required')


def locked_elsewhere(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False


def export_witness(held_guard):
    """Return (description, read-only FD); caller owns and closes this FD.

    Bind description in the root operator configuration; pass this FD only to
    the Python evidence owner, never to the native worker's pass_fds tuple.
    It is a separately opened file description, not a dup of the root's lock.
    """
    require(held_guard.intent is not None and held_guard.intent['supervisor_pid'] == os.getpid(),
            'witness exporter must be the guard owner')
    observed = held_guard.verify()
    fd = os.open(held_guard.lease, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        check_readonly(fd)
        actual = os.fstat(fd)
        root = os.fstat(held_guard.fd)
        require((actual.st_dev, actual.st_ino) == (root.st_dev, root.st_ino), 'lease was replaced')
        require(locked_elsewhere(fd), 'root does not hold exclusive lease')
        raw = os.pread(fd, 4097, 0)
        require(len(raw) <= 4096 and json.loads(raw) == held_guard.expected_lease(), 'lease differs')
        description = dict(schema_version='cpu-prefetch-q16c-compaction-witness/1',
            lease_identity=[actual.st_dev, actual.st_ino], lease_sha256=hashlib.sha256(raw).hexdigest(),
            intent_sha256=held_guard.expected_lease()['intent_sha256'],
            boot_id=held_guard.intent['boot_id'], deadline_monotonic_ns=held_guard.deadline_ns,
            supervisor_pid=os.getpid(), supervisor_start_ticks=process_identity(os.getpid()),
            observed_prestate=held_guard.intent['observed_prestate'], **observed)
        return description, fd
    except BaseException:
        os.close(fd)
        raise


class ControlReadbackFailure(RuntimeError):
    def __init__(self, observation):
        super().__init__('Q16c locked-page compaction became enabled')
        self.observation = observation


class ReadOnlyWitness:
    def __init__(self, description, descriptor, *, control=None):
        fields = {'schema_version', 'lease_identity', 'lease_sha256', 'intent_sha256',
                  'boot_id', 'deadline_monotonic_ns', 'supervisor_pid', 'supervisor_start_ticks',
                  'observed_prestate', 'requested_value', 'observed_value', 'verified'}
        require(type(description) is dict and set(description) == fields, 'closed witness fields')
        require(description['schema_version'] == 'cpu-prefetch-q16c-compaction-witness/1'
                and description['requested_value'] == description['observed_value'] == 0
                and description['verified'] is True, 'unverified witness')
        for name in ('deadline_monotonic_ns', 'supervisor_pid', 'supervisor_start_ticks'):
            require(type(description[name]) is int and description[name] > 0, 'invalid witness ' + name)
        for name in ('lease_sha256', 'intent_sha256'):
            value = description[name]
            require(type(value) is str and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value), 'invalid witness digest')
        require(type(description['observed_prestate']) is int and description['observed_prestate'] in (0, 1)
                and type(description['lease_identity']) is list and len(description['lease_identity']) == 2
                and all(type(i) is int and i >= 0 for i in description['lease_identity'])
                and type(description['boot_id']) is str and bool(description['boot_id']), 'invalid witness identity')
        self.description = json.loads(controls.canonical(description))
        self.descriptor = descriptor
        self.control = controls.LinuxControl() if control is None else control
        self.verify()

    def verify(self):
        d = self.description
        require(time.monotonic_ns() < d['deadline_monotonic_ns'], 'original guard deadline expired')
        check_readonly(self.descriptor)
        st = os.fstat(self.descriptor)
        require([st.st_dev, st.st_ino] == d['lease_identity'], 'read-only lease identity differs')
        raw = os.pread(self.descriptor, 4097, 0)
        require(len(raw) <= 4096 and hashlib.sha256(raw).hexdigest() == d['lease_sha256'],
                'root lease was cleared or changed')
        require(json.loads(raw)['intent_sha256'] == d['intent_sha256'], 'root prestate binding differs')
        require(locked_elsewhere(self.descriptor), 'exclusive root lease is not held')
        require(process_identity(d['supervisor_pid']) == d['supervisor_start_ticks'], 'root supervisor identity changed')
        require(self.control.boot() == d['boot_id'], 'boot changed')
        value = self.control.read()
        require(type(value) is int and value in (0, 1), 'unsupported actual control value')
        observed = dict(requested_value=0, observed_value=value, verified=value == 0,
                        witness_sha256=hashlib.sha256(controls.canonical(d)).hexdigest())
        if value != 0:
            raise ControlReadbackFailure(observed)
        return observed


class Observations:
    """Small external receipts; caller binds roots/budget to its signed lineage."""
    def __init__(self, witness, evidence_root, *, request_sha256, plan_sha256, capture_count):
        require(type(capture_count) is int and 0 < capture_count <= 180, 'finite capture count')
        for value in (request_sha256, plan_sha256):
            require(type(value) is str and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value), 'request/plan digest required')
        self.witness = witness
        self.root = Path(evidence_root)
        require(self.root.is_absolute() and not any(p.is_symlink() for p in (self.root, *self.root.parents)),
                'absolute nonsymlink receipt root required')
        witness.verify()
        self.root.mkdir(mode=0o700)
        self.request_sha256, self.plan_sha256 = request_sha256, plan_sha256
        self.count, self.next_ordinal, self.active = capture_count, 0, None

    def verify(self):
        return self.witness.verify()

    def observe(self, ordinal, moment, checkpoint=None):
        report = dict(schema_version='cpu-prefetch-q16c-compaction-observation/1',
                      capture_ordinal=ordinal, moment=moment, request_sha256=self.request_sha256,
                      plan_sha256=self.plan_sha256, checkpoint=checkpoint,
                      observed_monotonic_ns=time.monotonic_ns(), scientific_validity='NOT_ASSESSED',
                      execution_authority=False)
        failure = None
        try:
            report['control'] = self.witness.verify()
        except Exception as error:
            failure = error
            report['control'] = dict(getattr(error, 'observation',
                dict(requested_value=0, observed_value=None, verified=False)), error=repr(error))
        require(len(controls.canonical(report)) <= 8192, 'platform receipt exceeds finite bound')
        controls.publish(self.root / ('capture-' + str(ordinal) + '-' + moment + '.json'), report)
        if failure is not None:
            raise failure

    def before_capture(self, ordinal):
        require(ordinal == self.next_ordinal and self.active is None and ordinal < self.count,
                'capture authorization order changed')
        self.observe(ordinal, 'before-native-authorization')
        self.active = ordinal

    def after_capture(self, ordinal, checkpoint):
        require(ordinal == self.active == self.next_ordinal, 'capture checkpoint order changed')
        self.observe(ordinal, 'after-native-checkpoint', checkpoint)
        self.active = None
        self.next_ordinal += 1

    def complete(self):
        self.verify()
        require(self.active is None and self.next_ordinal == self.count, 'missing platform observations')


def channel_namespace(original, observations):
    """Fail AFTER only at ACK, preserving the unchanged custody transaction."""
    class GuardedChannel(original.ArchiveChannel):
        def __init__(self, *args, **kwargs):
            require(kwargs['captures'] == observations.count, 'platform/native capture counts differ')
            super().__init__(*args, **kwargs)
            self.platform_failure = None

        def receive(self, *, deadline_ns):
            pending = super().receive(deadline_ns=deadline_ns)
            try:
                observations.after_capture(pending.ordinal, pending.binding)
            except Exception as error:
                # The existing runner next archives and verifies custody, then
                # calls acknowledge(). Do not bypass its archive on failure.
                self.platform_failure = error
            return pending

        def acknowledge(self, receipt_binding, *, deadline_ns):
            if self.platform_failure is not None:
                raise RuntimeError('Q16c platform observation failed; capture archived; next capture denied') from self.platform_failure
            observations.verify()
            if self.ordinal + 1 < observations.count:
                observations.before_capture(self.ordinal + 1)
            return super().acknowledge(receipt_binding, deadline_ns=deadline_ns)

    return types.SimpleNamespace(**{**vars(original), 'ArchiveChannel': GuardedChannel})


def wrap_runner(original, observations):
    """Retain original worker supervision/custody body in a private namespace."""
    scope = dict(original.__globals__)
    original_subprocess = scope['subprocess']
    scope['channel'] = channel_namespace(scope['channel'], observations)

    def start(*args, **kwargs):
        require(observations.witness.descriptor not in kwargs.get('pass_fds', ()),
                'root lease witness must not be inherited by the native worker')
        observations.before_capture(0)
        return original_subprocess.Popen(*args, **kwargs)

    scope['subprocess'] = types.SimpleNamespace(**{**vars(original_subprocess), 'Popen': start})
    runner = metadata._clone(original, scope)

    def run(*args, **kwargs):
        result = runner(*args, **kwargs)
        try:
            observations.complete()
        except Exception as error:
            # The original body has already proved cleanup at this point.
            # Preserve that proof for the controller's existing failure path.
            error_type = scope.get('FixedActionExecutionError', RuntimeError)
            failure = error_type('PLATFORM_AFTER_WORKER', str(error))
            failure.cleanup_proof = result
            raise failure from error
        return result

    run.instrumented_runner = runner
    return run


def make_executor(observations):
    """Compose source sealing with guarded transport in a private Q16c factory.

    The prior factory and every historical executor remain unchanged. This
    factory exposes Q16c only, and retains all normal signed-action admission.
    """
    previous = source_execution.previous

    def private_base():
        result = previous.make_executor()
        guarded = wrap_runner(result.run_archived_worker, observations)
        result.run_archived_worker = guarded
        result.execute_fixed_action.__globals__['run_archived_worker'] = guarded
        return result

    scope = dict(source_execution.make_executor.__globals__)
    scope['previous'] = types.SimpleNamespace(**{**vars(previous), 'make_executor': private_base})
    result = metadata._clone(source_execution.make_executor, scope)()
    execute = result.execute_fixed_action

    def q16c_only(**arguments):
        request = arguments['request']
        require(request['action_id'] == 'Q16c', 'guarded executor is Q16c-only')
        require(hashlib.sha256(result.previous.canonical(request)).hexdigest() == observations.request_sha256,
                'platform request binding differs')
        plan = request['action_inputs']['plan']
        require(hashlib.sha256(result.archive.canonical(plan)).hexdigest() == observations.plan_sha256,
                'platform plan binding differs')
        require(type(plan.get('captures')) is list and len(plan['captures']) == observations.count,
                'platform/native capture counts differ before launch')
        return execute(**arguments)

    result.execute_fixed_action = q16c_only
    return result
