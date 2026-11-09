"""Bind actual E25 qualification to the already authored D240 continuation.

Authoring only: no registration, signing, collection, or hardware writes.
All inputs must exist. No preview or synthetic production entry point.
"""

import sys
from pathlib import Path
sys.path.insert(0, '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25/d242-admin-1')
import stage17_state_journal_v53 as d242
d242.activate()
import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import render_continuation as renderer
import audit_namespaces_v25 as audit


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_analysis_completion(reader, binding):
    # Operational timing metadata is not a scientific integer-only plan.
    # Read and pin the original receipt bytes; never rewrite elapsed_seconds.
    import math
    result = audit.parse(reader.read(binding))
    require(type(result) is dict, 'analysis completion object required')
    elapsed = result.get('elapsed_seconds')
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
            'invalid operational elapsed time')
    require(result.get('status') == 'ANALYSIS_EXITED'
            and type(result.get('exit_code')) is int and result['exit_code'] == 0
            and result.get('all_own_children_reaped') is True
            and result.get('raw_mutation') is False
            and result.get('execution_authority') is False,
            'analysis completion is not successful and quiescent')
    return result


def hardware(validation, original):
    mapping = validation.resolutions['S17-EXT-004'].semantic_context['hardware_mapping']
    q15w = validation.resolutions['S17-EXT-005'].semantic_context['q15_w']
    result = dict(mapping_id=mapping['mapping_id'], q15_w_result_sha256=q15w['result_sha256'],
                  prestate=copy.deepcopy(q15w['request']['action_inputs']['prestate']))
    require(result['prestate'] == mapping['prestate'], 'fresh Q15-R/W prestate differs')
    require(all(result[k] == original[k] for k in ('mapping_id', 'prestate')),
            'continuation hardware differs from original qualified control')
    return result


def resources(plan, parent):
    require(plan['budget'] == parent['budget'], 'original family budget changed')
    worker = max(c['execution_budget']['memory_bytes'] for c in plan['captures'])
    mapped = max(c['resources']['total_mapping_bytes'] for c in plan['captures'])
    require(worker == 240518168576 and mapped == 24877350912,
            'retained geometry/worker ceiling differs')
    require(plan['budget']['memory_bytes'] == 246960619520, 'family AS differs')
    return dict(required_worker_as_bytes=worker, max_native_mapping_bytes=mapped,
                required_family_as_bytes=plan['budget']['memory_bytes'],
                operational_memory_reserve_bytes=8589934592)


def check_audits(reports, plan_binding, identities, parent_binding):
    require(len(reports) == 2, 'local and stand audits required')
    wanted = audit.Matcher(identities).wanted
    modes = set()
    for report in reports:
        require(report['status'] == 'PASS_SCOPED_HISTORY_AUDIT'
                and not report['matches'] and not report['errors']
                and report['checked_files'] > 0 and report['execution_authority'] is False,
                'namespace audit did not pass')
        require(set(report['needles']) == wanted, 'namespace audit covers different identities')
        require(report['plan_binding']['sha256'] == plan_binding['sha256']
                and report['plan_binding']['size_bytes'] == plan_binding['size_bytes']
                and report['parent_plan_binding']['sha256'] == parent_binding['sha256'],
                'namespace audit belongs to a different plan')
        require(report['parent_contract']['original_numeric_seeds_preserved'] is True
                and report['parent_contract']['numeric_seeds_collision_scanned'] is False,
                'namespace audit seed policy differs')
        roots = report['roots']
        if any('/stage17-owner-evidence/' in p for p in roots):
            modes.add('stand')
        elif any(p.endswith('/docs/evidence') for p in roots):
            modes.add('local')
        else:
            raise ValueError('unknown audit scope')
    require(modes == {'local', 'stand'}, 'two distinct audit scopes required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--audit', nargs=2, action='append', required=True,
                        metavar=('PATH', 'SHA256'))
    args = parser.parse_args()
    root = args.repository_root.resolve(strict=True)
    sys.path.insert(0, str(root/'tools'))
    admission = importlib.import_module('stage17_q16a_continuation_admission_v1')
    controller = importlib.import_module('stage17_phase_controller_v26')
    require(all(Path(m.__file__).resolve().parent == root/'tools'
                for m in (admission, controller)), 'qualified module location differs')
    reader = admission.BoundReader()
    bind = lambda p: renderer.existing_binding(p, admission)
    spec_binding = bind(args.spec)
    require(spec_binding['sha256'] == args.spec_sha256, 'authoring spec differs')
    spec = reader.document(spec_binding)
    destination = Path(spec['output_directory'])
    require(destination == renderer.E25/'formal-q16a-continuation-authoring-1',
            'exact existing E25 authoring destination required')
    targets = [destination/n for n in ('action-inputs.json', 'preparation-provenance.json')]
    require(not any(p.exists() for p in targets), 'exclusive preparation outputs required')
    validation = renderer.qualify(spec, root, admission, controller)
    plan_binding = bind(destination/'plan.json')
    plan = reader.document(plan_binding)
    require(plan['source_revision'] == validation.resolutions['S17-EXT-006'].semantic_context['source_revision'],
            'plan source is not currently qualified')
    require(plan['continuation']['parent_plan'] == spec['parent_plan']
            and plan['continuation']['accepted_prefix_manifest'] == spec['accepted_prefix_manifest'],
            'authored plan and spec differ')
    parent = reader.document(spec['parent_plan'])
    prefix = reader.document(spec['accepted_prefix_manifest'])
    process_binding = bind(Path(spec['accepted_prefix_manifest']['path']).parent/'analysis-process-result.json')
    process = load_analysis_completion(reader, process_binding)
    require(process['status'] == 'ANALYSIS_EXITED' and process['exit_code'] == 0
            and process['all_own_children_reaped'] is True and process['raw_mutation'] is False,
            'prefix analysis has not exited successfully')
    original_request = reader.document(prefix['original_authority']['REQUEST'])
    discovery = original_request['action_inputs']['prerequisite_bindings']['discovery_validation']
    reader.read(discovery)
    ns_binding = bind(destination/'namespace_registry.json')
    identities = reader.document(ns_binding)
    audit_bindings = []
    reports = []
    for path, digest in args.audit:
        binding = bind(path)
        require(binding['sha256'] == digest, 'namespace audit bytes differ')
        audit_bindings.append(binding)
        report = reader.document(binding)
        require(report['helper_sha256'] == hashlib.sha256(Path(audit.__file__).read_bytes()).hexdigest(),
                'namespace audit helper differs')
        reports.append(report)
    check_audits(reports, plan_binding, identities, spec['parent_plan'])
    inputs = dict(plan=plan, hardware_control=hardware(validation, original_request['action_inputs']['hardware_control']),
                  prerequisite_bindings=dict(discovery_validation=discovery, q16a_validation=None,
                    q16b_validation=None, schedule_sources=[], namespace_registry=ns_binding))
    request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6', action_id='Q16a',
                   stand_id=plan['stand_id'], action_inputs=inputs)
    # This is the full production input gate; no synthetic context or weaker validator.
    controller.validate_action_inputs(request, validation)
    proof = dict(status='PREPARATION_ONLY_LIVE_ADMISSION_REQUIRED', execution_authority=False,
                 source_revision=plan['source_revision'], plan_sha256=plan_binding['sha256'],
                 source_spec=spec_binding, namespace_audits=audit_bindings,
                 prefix_analysis_process=process_binding, continuation=plan['continuation'],
                 helper_binding=bind(Path(__file__).resolve()), **resources(plan, parent))
    reader.finish()
    result = {}
    for path, document in zip(targets, (inputs, proof), strict=True):
        raw = admission.canonical(document)
        with path.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        result[path.name] = renderer.data_binding(path, raw)
    fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps(dict(status='AUTHORED_NOT_REGISTERED', outputs=result, execution_authority=False)))


if __name__ == '__main__':
    main()
