#!/usr/bin/env python3
"""Read retained facts; print existing-tool argv plus clock source binding.

No command execution, file writes, hardware access, signing or admission.
Run after actual clock completion; q15r/all additionally require the sealed
Q15-R result. Caller must have admitted EXT003's exact revision/bundle and
verified codegen report provenance. This is a preparation helper, not a verifier.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROLES = {'RUNTIME_ATOMIC_LAYOUT': 'Q15_R_ATOMIC_LAYOUT_RAW',
         'ACTUAL_CPU_MIGRATION': 'Q15_R_CPU_MIGRATION_RAW',
         'ADDRESS_RESIDENCY': 'Q15_R_ADDRESS_RESIDENCY_RAW',
         'SOFTWARE_PREFETCH_MAPPING': 'Q15_R_SOFTWARE_PREFETCH_RAW'}
PAIR = 'CPU-PREFETCH-V5-P0-NEAR-0-1-FAR-0-8-v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_bytes(path, record):
    require(path.stat().st_size == record['size_bytes'] and digest(path) == record['sha256'],
            'retained bytes differ: ' + str(path))


def command(args, kind, raw, identity, source_id):
    output = args.qualification_directory / (kind + '.json')
    require(not output.exists() and not output.is_symlink(), 'retain existing envelope: ' + str(output))
    values = dict(kind=kind, raw=str(raw), output=str(output),
                  artifact_id=args.id_prefix + '-EXT004-QUAL-' + ('CLOCK' if kind == 'SELECTED_PAIR_CLOCK' else kind.replace('_', '-')),
                  stand_id='CPU-PREFETCH-V5', binding_id=identity['binding_id'],
                  source_revision=args.source_revision, binary_sha256=identity['binary_sha256'],
                  captured_at_utc=identity['captured_at_utc'], worker_pair='near',
                  cpu_pair_selection_id=PAIR, source_artifact_id=source_id)
    argv = [str(args.bundle_root / 'release/bin/cpu_prefetch_q15_qualification_evidence_tool')]
    for key, value in values.items():
        argv.extend(['--' + key.replace('_', '-'), value])
    return argv


def prepare(args):
    commands = []
    binding = None
    if args.mode in ('clock', 'all'):
        q = args.qualification_directory
        capture = load(q / 'clock-capture-result.json')
        require(type(capture['exit_code']) is int and capture['exit_code'] == 0
                and capture['timed_out'] is False, 'clock failed: retain and stop; no retry')
        require(capture['source_revision'] == args.source_revision, 'clock revision differs')
        tool = args.bundle_root / 'release/bin/cpu_prefetch_q15_clock_qualification_tool'
        require(digest(tool) == capture['binary_sha256'], 'clock executable differs from capture')
        raw = q / 'clock-raw.json'
        require(capture['command'][-5:] == [str(tool), '--qualify-pair', 'near', '--output', str(raw)],
                'clock command/pair/path differs or count override present')
        for name in ('clock-raw.json', 'clock-stdout.txt', 'clock-stderr.txt'):
            check_bytes(q / name, capture[name])
        observed = load(raw)
        require(observed['schema_version'] == 'cpu-prefetch-stage17-q15-clock-pair-raw/1'
                and observed['pair'] == 'near'
                and (observed['producer_cpu'], observed['consumer_cpu']) == (0, 1), 'clock raw pair differs')
        for key in ('producer_pinned', 'consumer_pinned', 'producer_per_core_passed',
                    'consumer_per_core_passed', 'cross_core_passed'):
            require(observed[key] is True, 'clock raw failed: ' + key)
        source_id = args.id_prefix + '-EXT004-CLOCK-RAW'
        identity = dict(binding_id=capture['capture_id'], binary_sha256=capture['binary_sha256'],
                        captured_at_utc=capture['completed_at_utc'])
        commands.append(command(args, 'SELECTED_PAIR_CLOCK', raw, identity, source_id))
        binding = dict(artifact_id=source_id, path=str(raw), **capture['clock-raw.json'],
                       capture_id=capture['capture_id'], source_revision=capture['source_revision'],
                       binary_sha256=capture['binary_sha256'], started_at_utc=capture['started_at_utc'],
                       completed_at_utc=capture['completed_at_utc'],
                       capture_result_path=str(q / 'clock-capture-result.json'),
                       capture_result_sha256=digest(q / 'clock-capture-result.json'))
    if args.mode in ('q15r', 'all'):
        require(args.request is not None and args.codegen_facts is not None,
                '--request and --codegen-facts required after Q15-R')
        request = load(args.request)
        output = Path(request['evidence_root_binding']['absolute_path']).resolve(strict=True)
        result = load(output / 'stage17-q15-r-result-v4.json')
        require(request['action_id'] == result['action_id'] == 'Q15-R'
                and result['attempt_id'] == request['attempt_id']
                and result['request_sha256'] == digest(args.request), 'Q15-R request binding differs')
        require(result['terminal_state'] == 'Q15_R_READ_ONLY_COMPLETE'
                and result['quarantined'] is False and result['stand_id'] == 'CPU-PREFETCH-V5',
                'Q15-R not complete/usable')
        require(result['runtime_binding'] == request['runtime_binding']
                and result['release_binding'] == request['release_binding'], 'Q15-R runtime/release binding differs')
        artifacts = {}
        for item in result['artifacts']:
            require(item['role'] not in artifacts, 'duplicate Q15-R role')
            path = (output / item['file_name']).resolve(strict=True)
            require(path.parent == output, 'Q15-R artifact escaped output directory')
            check_bytes(path, item)
            artifacts[item['role']] = path
        facts = load(args.codegen_facts)
        require(facts['source_revision'] == args.source_revision and facts['reports'], 'codegen facts revision/evidence missing')
        flags = ('gcc_codegen_passed', 'clang_codegen_passed', 'gnu_objdump_passed', 'llvm_objdump_passed')
        require(all(facts[key] is True for key in flags), 'codegen outcome missing/failed')
        identity = dict(binding_id=request['request_id'], binary_sha256=result['runtime_binding']['sha256'],
                        captured_at_utc=result['completed_at_utc'])
        for kind, role in ROLES.items():
            raw = artifacts[role]
            require(load(raw)['session_id'] == request['session_id'], 'Q15 raw session differs')
            argv = command(args, kind, raw, identity, args.id_prefix + '-EXT004-' + role.replace('_', '-'))
            if kind == 'SOFTWARE_PREFETCH_MAPPING':
                for key in flags:
                    argv.extend(['--' + key.replace('_', '-'), 'true'])
            commands.append(argv)
    return dict(scope='PREPARATION_ONLY_NO_EXECUTION_AUTHORITY', argv=commands,
                clock_source_binding=binding,
                requirements=['Recheck output absence immediately before invoking; existing tool truncates output.',
                              'Retain each invocation/exit/stdout/stderr and require output eligible=true.',
                              'Verify exact codegen report hashes and source applicability; booleans alone are not provenance.',
                              'Retain this clock source binding alongside its original capture record; it is not a new capture.',
                              'Keep Q15 session controller alive until authorized Q15-W; no capture retry implied.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('clock', 'q15r', 'all'))
    for name in ('bundle-root', 'qualification-directory'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--id-prefix', required=True)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--codegen-facts', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args), indent=2))


if __name__ == '__main__':
    main()
