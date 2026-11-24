#!/usr/bin/env python3
"""Read-only E22 software diagnostic; never authors authority or starts workers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-22')
R = E / 'admission-root'
NAME = 'cpu-prefetch-pilot-candidate-2.0.0-c962fd7-clean-aba9b921f5fc'
CANDIDATE_SHA = 'd4742c078f47665c3270dcf5d042f2146188f5a0cfa0c202964748e697385542'
INPUT_SHA = 'c0dafbedf1bd36e470c9fc5813635a25f2d75a422b60da3a42ce0dcd51d248aa'
RECEIPT_SHA = 'c41349163b688116d2b197a541724e2d7e8871c258f220c8f5c03f3d0ad2c17a'
PLAN_SHA = '59898ca78f6b79c14e845859052027241c54298c9f65dcb1042b05b18be6af2e'
REVISION = 'c962fd757f0b215088e6a91e760af0616ab9636b'


def read_bound(path, expected=None):
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('absolute nonsymlink path required: ' + str(path))
    if not path.is_file():
        raise ValueError('regular file required: ' + str(path))
    with path.open('rb') as stream:
        data = stream.read(128 * 1024**2 + 1)
    if len(data) > 128 * 1024**2:
        raise ValueError('bounded metadata exceeded')
    binding = dict(path=str(path), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    if expected is not None and binding['sha256'] != expected:
        raise ValueError('SHA mismatch: ' + str(path))
    return data, binding


def check(candidate_path, report):
    if candidate_path.resolve().is_relative_to(R.resolve()):
        raise ValueError('candidate must remain outside qualified repository')
    candidate_bytes, report['candidate_controller'] = read_bound(candidate_path, CANDIDATE_SHA)
    inputs_bytes, report['action_inputs'] = read_bound(E / 'formal-q16a-authoring-1/action-inputs.json', INPUT_SHA)
    receipt_bytes, report['original_receipt'] = read_bound(E / 'ext002-authoring-1/ext002-runtime-release-provenance.json', RECEIPT_SHA)
    _, report['plan'] = read_bound(E / 'formal-q16a-authoring-1/plan.json', PLAN_SHA)
    receipt = json.loads(receipt_bytes)
    sys.path.insert(0, str(R / 'tools'))
    import stage17_operational_cli_v18 as cli
    archive = E.parent / (NAME + '.tar.gz')
    # Original qualified modules validate original pins and journal. No candidate
    # module replaces any qualified module in sys.modules.
    validation = cli._validation(R, E, archive, Path(str(archive) + '.sha256'), False)
    context = validation.resolutions['S17-EXT-006'].semantic_context
    if context['source_revision'] != REVISION:
        raise ValueError('qualified source differs from E22 c962')
    keys = ('archive_profile_binding', 'archive_bundle_root', 'archive_runtime_root')
    report['qualified_archive_context'] = {key: context[key] for key in keys}
    if any(context[key] != receipt[key] for key in keys):
        raise ValueError('actual EXT006 context differs from original receipt')
    report['journal_state'] = validation.current_state
    report['resolutions'] = {key: dict(resolution_id=value.resolution_id, sha256=value.sha256)
                             for key, value in validation.resolutions.items()}
    name = 'unqualified_e22_candidate_controller_diagnostic'
    spec = importlib.util.spec_from_file_location(name, candidate_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Execute the exact hashed bytes; no loader cache or candidate sibling imports.
    exec(compile(candidate_bytes, str(candidate_path), 'exec'), module.__dict__)
    request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
                   action_id='Q16a',
                   stand_id=validation.resolutions['S17-EXT-002'].semantic_context['stand_id'],
                   action_inputs=json.loads(inputs_bytes))
    report['operation'] = 'candidate.validate_action_inputs(minimal_in_memory_request, original_journal_validation)'
    extent = module.validate_action_inputs(request, validation)
    report['capture_count'] = len(extent.captures)
    report['derived_deadline_policy'] = module.deadline_policy(extent)
    report['qualified_source_revision'] = REVISION
    report['source_files'] = []
    for module_name, loaded in sorted(sys.modules.items()):
        source = getattr(loaded, '__file__', None)
        if source and Path(source).is_absolute() and Path(source).is_relative_to(R / 'tools'):
            _, binding = read_bound(Path(source))
            report['source_files'].append(dict(module=module_name, **binding))
    report['status'] = 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-controller', type=Path, required=True)
    args = parser.parse_args()
    report = dict(schema_version='e22-candidate-controller-software-diagnostic/1',
                  status='FAIL', software_only=True, candidate_qualified=False,
                  execution_authority=False, request_written=False,
                  authorizations_created=False, workers_started=False,
                  scope='Input admission only; no signature, executor, hardware, or launch validation')
    try:
        check(args.candidate_controller, report)
    except Exception as error:
        report['error'] = dict(type=type(error).__name__, message=str(error))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
