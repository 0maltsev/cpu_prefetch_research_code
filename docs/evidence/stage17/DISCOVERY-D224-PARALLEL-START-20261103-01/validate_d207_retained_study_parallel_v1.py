#!/usr/bin/env python3
"""D224 bounded parallel offline reanalysis of unchanged D207 bytes after completed CLI17 custody admission.

No execution, signing, network, expiry extension or second-copy attestation.
Explicit original-byte bindings are supplied by the completed admission operator.
"""
from __future__ import annotations
import argparse
import dataclasses
import datetime
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
META_LIMIT = 32 * 1024 * 1024
CHUNK = 1024 * 1024
POLICY = 'EXT007-RAW-NONE-STAND-PRIMARY-v1'
ACCEPTANCE = 'docs/evidence/stage17/STAND-CUSTODY-D206-20261103-01/owner-acceptance.json'
PROPOSAL = 'docs/evidence/stage17/STAND-CUSTODY-D206-20261103-01/proposal.md'
CLI = 'tools/stage17_operational_cli_v17.py'
SUCCESS = b'stage17-discovery: PASS; no formal calibration credit or new authority'
SUCCESSOR_SHA256 = '661613aedbc77fd538970b8c5e79a4bbaa3d2acb7f503cb802725239b25e94bf'
CORRECTION_SHA256 = '55b4e21c3f10d7321dfa1162c748f5bd35bfc22cacfa506d5378d7088e56060a'
PARALLEL_SHA256 = '1a1e2cb6ab467b3e192ab3e64814bed7facef4577a1141ea8f92555ee42a19bf'
PARALLEL_DECISION_SHA256 = 'f433ce21102f1f5cd0ce564584e6b47ea9070ae1c1f38d96e3a16c33165cde60'
TOKEN = 'q16a_duration_discovery'
ATTEMPT = f'stage17-{TOKEN}-attempt-v5.json'
COMPLETION = f'stage17-{TOKEN}-completion-v5.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid SHA256')
    return value


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def loads(raw):
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    require(isinstance(value, dict), 'metadata must be a JSON object')
    return value


def safe_path(path):
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        require(not component.is_symlink(), 'symlink path: ' + str(component))
    return path


def read_bytes(path, expected=None):
    path = safe_path(path)
    if expected is not None:
        digest(expected)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= META_LIMIT,
                'metadata is not a bounded regular file: ' + str(path))
        raw = stream.read(META_LIMIT + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size <= META_LIMIT and stamp(before) == stamp(after),
            'metadata changed while reading')
    require(expected is None or sha(raw) == expected, 'metadata SHA256 differs: ' + str(path))
    return raw


def read_bound(path, expected):
    raw = read_bytes(path, expected)
    return loads(raw), raw


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def short(item):
    return {key: item[key] for key in ('file_name', 'size_bytes', 'sha256')}


def custody_gate(acceptance, proposal_raw, plan):
    require(acceptance['policy_id'] == plan['custody_policy_id'] == POLICY
            and acceptance['record_id'] == 'CPU-PREFETCH-V5-EXT007-D206-OWNER-ACCEPTANCE-1',
            'second-copy exception requires exact D206 acceptance')
    require(acceptance['proposal_sha256'] == sha(proposal_raw)
            and acceptance['proposal_size_bytes'] == len(proposal_raw), 'D206 proposal binding differs')
    require(type(acceptance['m_dur']) is int and acceptance['m_dur'] == 1
            and acceptance['compression'] == 'NONE' and acceptance['analysis_location'] == 'stand'
            and acceptance['independent_raw_backup'] is False
            and acceptance['new_experiment_authority'] is False
            and acceptance['automatic_retry_authority'] is False
            and acceptance['phase18_authority'] is False
            and acceptance['failed_raw_retained_on_stand'] is True, 'D206 scope differs')
    require(plan['design_id'] == 'D207-Q16A-SETUP-DISCOVERY-v2'
            and plan['schema_version'] == 'cpu-prefetch-stage17-discovery-plan/2'
            and plan['diagnostic_only'] is True and plan['phase18_authority'] is False,
            'D206 exception is scoped to EXT007 diagnostics')


def supervisor_gate(supervisor, completion):
    require(supervisor['success'] is True and type(supervisor['exit_code']) is int
            and supervisor['exit_code'] == 0 and supervisor['completion_present'] is True
            and supervisor['supervisor_errors'] == [] and supervisor['partition_procs'] == '',
            'supervisor did not finish successfully with empty partition')
    restoration = supervisor['partition_restoration']
    require(restoration['verified'] is True and restoration['partition_absent'] is True,
            'supervisor partition restoration not verified')
    require(completion['leader_reaped'] is True and completion['process_group_gone'] is True
            and completion['restoration_verified'] is True and completion['quarantined'] is False,
            'controller quiescence/restoration not verified')


def admission_gate(record, *, repository, output_root, request_path, authorization_path,
                   expected, stdout):
    require(type(record['exit_code']) is int and record['exit_code'] == 0,
            'CLI custody admission did not succeed')
    require(record['bindings'] == expected, 'admission bindings differ')
    require(record['repository_root'] == str(repository) and record['output_root'] == str(output_root),
            'admission root differs')
    argv = record['argv']
    require(isinstance(argv, list) and len(argv) >= 3
            and all(isinstance(v, str) for v in argv), 'invalid admission argv')
    # Accept the actual Python executable, with optional -B, then this exact CLI.
    offset = 2 if len(argv) > 1 and argv[1] == '-B' else 1
    require(Path(argv[0]).is_absolute() and argv[offset:offset + 2] ==
            [str(repository / CLI), 'admit-discovery-retention'], 'not actual CLI17 retention command')
    tail = argv[offset + 2:]
    require(len(tail) % 2 == 0, 'malformed admission flags')
    options = dict(zip(tail[::2], tail[1::2]))
    allowed = {'--repository-root', '--evidence-root', '--authorization', '--signature',
               '--output-root', '--pilot-archive', '--pilot-sidecar', '--request'}
    require(len(options) * 2 == len(tail) and set(options) <= allowed, 'duplicate/unknown admission flags')
    for key, value in {'--repository-root': str(repository), '--authorization': str(authorization_path),
                       '--output-root': str(output_root)}.items():
        require(options.get(key) == value, 'admission command differs: ' + key)
    require(all(key in options and Path(options[key]).is_absolute()
                for key in ('--evidence-root', '--signature')), 'missing admission evidence/signature')
    require('--request' not in options or options['--request'] == str(request_path), 'admission request differs')
    require(stdout.strip() == SUCCESS, 'CLI admission success output missing/different')


def inventory_gate(root, result, registry):
    required = {registry.REPORT_NAME, 'studyhardware.json'} | {
        name for ordinal in range(36) for name in registry.capture_names(ordinal)}
    items = result['artifacts']
    names = [item['file_name'] for item in items]
    require(len(names) == len(required) and set(names) == required,
            'full36 exact worker artifact set required; no selection on partial')
    bindings = {item['file_name']: short(item) for item in items}
    observed = {}
    for name in sorted(required | {ATTEMPT, COMPLETION, registry.RESULT_NAME}):
        info = (root / name).lstat()
        require(stat.S_ISREG(info.st_mode), 'missing/unsafe retained file: ' + name)
        if name in bindings:
            require(type(bindings[name]['size_bytes']) is int and info.st_size == bindings[name]['size_bytes'],
                    'incomplete retained file: ' + name)
            digest(bindings[name]['sha256'])
        observed[name] = stamp(info)
    # Operator provenance may coexist in a subdirectory, but never substitutes for required files.
    return observed


def unchanged(root, observed):
    require(all(stamp((root / name).lstat()) == value for name, value in observed.items()),
            'retained files changed during validation')


def load_runtime(repository):
    sys.path.insert(0, str(repository / 'tools'))
    cli = importlib.import_module('stage17_operational_cli_v17')
    registry = importlib.import_module('stage17_output_registry_v10')
    successor = safe_path(Path(__file__).with_name('stage17_discovery_validation_v3.py'))
    successor_raw = read_bytes(successor, SUCCESSOR_SHA256)
    read_bytes(Path(__file__).with_name('0213-discovery-whole-plot-readback-validation.md'), CORRECTION_SHA256)
    name = 'stage17_discovery_validation_v3'
    validator = sys.modules.get(name)
    if validator is None:
        spec = importlib.util.spec_from_file_location(name, successor)
        require(spec is not None and spec.loader is not None, 'cannot load bound successor')
        validator = importlib.util.module_from_spec(spec)
        sys.modules[name] = validator
        exec(compile(successor_raw, str(successor), 'exec'), validator.__dict__)
    require(safe_path(validator.__file__) == successor, 'successor path differs')
    cli.activate()
    modules = (cli, registry, validator, validator.contract, validator.selector,
               validator.codec, validator.environment)
    for module in modules:
        if module is not validator:
            require(safe_path(module.__file__).parent == repository / 'tools', 'dependency outside original production root')
    require(cli.registry is registry and validator.registry is registry, 'runtime registry wiring differs')
    parallel_path = safe_path(Path(__file__).with_name('stage17_discovery_validation_parallel_v1.py'))
    parallel_raw = read_bytes(parallel_path, PARALLEL_SHA256)
    read_bytes(Path(__file__).with_name('0224-parallel-retained-discovery-validation.md'), PARALLEL_DECISION_SHA256)
    parallel_name = 'stage17_discovery_validation_parallel_v1'
    parallel = sys.modules.get(parallel_name)
    if parallel is None:
        spec = importlib.util.spec_from_file_location(parallel_name, parallel_path)
        require(spec is not None and spec.loader is not None, 'cannot load bound parallel adapter')
        parallel = importlib.util.module_from_spec(spec)
        sys.modules[parallel_name] = parallel
        exec(compile(parallel_raw, str(parallel_path), 'exec'), parallel.__dict__)
    require(safe_path(parallel.__file__) == parallel_path and parallel.base is validator,
            'parallel adapter dependency wiring differs')
    return cli, registry, parallel, (*modules, parallel)


def validate(args):
    repository = safe_path(args.repository_root)
    root = safe_path(args.output_root)
    scratch = safe_path(args.scratch_directory)
    output = safe_path(args.output)
    require(root.is_dir() and scratch.is_dir(), 'output/scratch directory missing')
    require(not scratch.is_relative_to(root) and not root.is_relative_to(scratch),
            'scratch must be separate from immutable raw directory')
    require(output.parent == scratch and not output.exists(), 'report must be NEW directly inside approved scratch')
    request, request_raw = read_bound(args.request, args.request_sha256)
    authorization, authorization_raw = read_bound(args.authorization, args.authorization_sha256)
    plan_doc, plan_raw = read_bound(args.plan, args.plan_sha256)
    result, result_raw = read_bound(root / 'stage17-action-result-v5.json', args.admitted_result_sha256)
    acceptance, acceptance_raw = read_bound(args.d206_acceptance, args.d206_acceptance_sha256)
    proposal_raw = read_bytes(args.d206_proposal, args.d206_proposal_sha256)
    # Both original D206 documents are explicitly hash-pinned by the operator;
    # the release projection need not contain evidence outside its source closure.
    custody_gate(acceptance, proposal_raw, plan_doc)
    supervisor, supervisor_raw = read_bound(args.supervisor_result, args.supervisor_sha256)
    completion_raw = read_bytes(root / COMPLETION)
    completion = loads(completion_raw)
    supervisor_gate(supervisor, completion)
    admission, admission_raw = read_bound(args.admission_record, args.admission_sha256)
    stdout = read_bytes(args.admission_stdout, admission['stdout']['sha256'])
    stderr = read_bytes(args.admission_stderr, admission['stderr']['sha256'])
    for key, raw, path in (('stdout', stdout, args.admission_stdout), ('stderr', stderr, args.admission_stderr)):
        require(admission[key] == dict(path=str(safe_path(path)), size_bytes=len(raw), sha256=sha(raw)),
                'admission captured output binding differs')
    expected = dict(plan_sha256=args.plan_sha256, request_sha256=args.request_sha256,
                    authorization_sha256=args.authorization_sha256, result_sha256=args.admitted_result_sha256,
                    supervisor_sha256=args.supervisor_sha256)
    admission_gate(admission, repository=repository, output_root=root,
                   request_path=safe_path(args.request), authorization_path=safe_path(args.authorization),
                   expected=expected, stdout=stdout)
    previous, previous_raw = read_bound(args.previous_validation, args.previous_validation_sha256)
    require(previous['status'] == 'FULL_STUDY_VALIDATION_REJECTED'
            and previous['error'] == 'whole plot restore prestate: differs'
            and all(previous.get(k) == v for k,v in expected.items()),
            'D213 requires the original rejected report for these exact bytes')
    cli, registry, validator, modules = load_runtime(repository)
    require(request_raw == registry.canonical(request), 'request not canonical')
    require(request['action_id'] == registry.ACTION and request['synthetic_test_only'] is False,
            'actual EXT007 discovery request required')
    require(request['action_inputs']['plan'] == plan_doc, 'request plan differs')
    plan = validator.contract.validate_plan(plan_doc)
    require(plan_raw == plan.canonical_bytes and plan.sha256 == args.plan_sha256
            and len(plan.captures) == 36, 'plan original canonical binding/full36 differs')
    require(authorization['request_binding'] == dict(path=str(safe_path(args.request)),
            size_bytes=len(request_raw), sha256=sha(request_raw)), 'authorization request binding differs')
    require(authorization['evidence_root_binding'] == request['evidence_root_binding'], 'authority root differs')
    pinned = registry.pin_registry(repository)
    for family, doc in (('fixed-action-request', request), ('phase-action-authorization', authorization)):
        registry.validate_document(pinned, doc, registry.schema_path(family), family)
    observed = inventory_gate(root, result, registry)
    require(stamp((root / COMPLETION).stat())[2] == len(completion_raw)
            and read_bytes(root / COMPLETION) == completion_raw, 'completion changed')
    # This adapter holds ALREADY ADMITTED documents only; it is never passed to
    # prepare_action/execute_once and makes no fresh signature/expiry decision.
    prepared = SimpleNamespace(request=request, request_bytes=request_raw, authorization=authorization,
        authorization_bytes=authorization_raw, runtime=request['runtime_binding'],
        release=request['release_binding'], registry=pinned)
    report = cli.admit_retention(prepared, root)  # hashes every raw artifact using bounded chunks
    require(read_bytes(root / registry.RESULT_NAME, args.admitted_result_sha256) == result_raw,
            'admitted result changed')
    require(len(report['captures']) == 36, 'no selection on partial study')
    retention_binding = short(next(v for v in result['artifacts'] if v['file_name'] == registry.REPORT_NAME))
    summary = dict(scope='D207_D213_INDEPENDENT_VALIDATOR_V3',
        previous_validation_sha256=sha(previous_raw), correction_decision_sha256=CORRECTION_SHA256,
        successor_validator_sha256=SUCCESSOR_SHA256,
        parallel_adapter_sha256=PARALLEL_SHA256, parallel_decision_sha256=PARALLEL_DECISION_SHA256,
        analysis_workers=8, worker_address_space_limit_bytes=8*1024**3, maximum_analysis_seconds=86400,
        started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **expected, admission_sha256=sha(admission_raw), d206_acceptance_sha256=sha(acceptance_raw),
        d206_proposal_sha256=sha(proposal_raw), custody_policy_id=POLICY, m_dur=1,
        independent_raw_backup=False, analysis_location='stand', output_root=str(root),
        repository_root=str(repository), scratch_directory=str(scratch), retention_binding=retention_binding,
        formal_runs_contributed=0, execution_authority=False, phase18_authority=False,
        implementation_sha256={(str(Path(m.__file__).relative_to(repository)) if safe_path(m.__file__).parent == repository / 'tools' else 'analysis/'+Path(m.__file__).name):sha(read_bytes(Path(m.__file__)))
                               for m in modules})
    # Exclusive-create before expensive reconciliation. If interrupted, the partial
    # report remains non-reusable; raw is never written or deleted.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    previous_tempdir = tempfile.tempdir
    try:
        tempfile.tempdir = str(scratch)
        try:
            validated = validator.validate_retained_study(action_inputs=request['action_inputs'],
                retention_report=report, retention_binding=retention_binding, output_root=root,
                worker_count=8, worker_memory_bytes=8*1024**3, analysis_timeout_seconds=86400,
                progress=lambda ordinal,completed,total: print(json.dumps(dict(event='capture_validated',ordinal=ordinal,completed=completed,total=total,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())),flush=True))
            unchanged(root, observed)
            summary.update(status='FULL_STUDY_VALIDATED', validated_study=dataclasses.asdict(validated))
            code = 0
        except Exception as error:
            summary.update(status='FULL_STUDY_VALIDATION_REJECTED', error=str(error))
            code = 1
        summary['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with os.fdopen(fd, 'w') as stream:
            fd = -1
            json.dump(summary, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    finally:
        tempfile.tempdir = previous_tempdir
        if fd != -1:
            os.close(fd)
    return code, summary


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'output-root', 'scratch-directory', 'output', 'plan', 'request',
                 'authorization', 'd206-acceptance', 'd206-proposal', 'supervisor-result',
                 'admission-record', 'admission-stdout', 'admission-stderr', 'previous-validation'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('plan-sha256', 'request-sha256', 'authorization-sha256', 'admitted-result-sha256',
                 'd206-acceptance-sha256', 'd206-proposal-sha256', 'supervisor-sha256', 'admission-sha256',
                 'previous-validation-sha256'):
        p.add_argument('--' + name, required=True)
    return p


def main():
    try:
        code, summary = validate(parser().parse_args())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('PREVALIDATION_REJECTED: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(dict(status=summary['status'], execution_authority=False)))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
