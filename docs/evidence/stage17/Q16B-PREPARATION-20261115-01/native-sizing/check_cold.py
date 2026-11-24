#!/usr/bin/env python3
"""Exercise only cold sizing/parser calls locally, using retained metadata.

The 30M caps below are retained-Q16a test inputs, NOT a prospective Q16b cap
decision. No seeds/identities in these fixtures are reserved for collection.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REQUEST = ROOT / 'build/stage17-step6-q16b-prep/inputs/q16a-request.json'
REQUEST_SHA = 'aa780db91ceaaedca11fe3b4036c3506e9de80b5a25c6189c69c7a065ed8026a'


def bind(path):
    raw = path.read_bytes()
    return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitizers', action='store_true')
    args = parser.parse_args()
    build = HERE / ('asan-ubsan' if args.sanitizers else 'release')
    binary = build / 'service-layout'
    out = build / 'cold-checks'
    out.mkdir()
    assert bind(REQUEST)['sha256'] == REQUEST_SHA
    request = json.loads(REQUEST.read_bytes())
    controls = request['action_inputs']['hardware_control']
    prestate = [dict(cpu=row['cpu'], value=int(row['complete_value_hex'], 16))
                for row in controls['prestate']]
    items = request['action_inputs']['plan']['captures']
    env = dict(os.environ)
    env.pop('LD_PRELOAD', None)
    env['LD_LIBRARY_PATH'] = str(ROOT / 'build/ext007-runtime-20261101/root/usr/lib')
    env['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    records = []

    def invoke(document, name, mode='--describe', good=True, raw=None):
        path = out / (name + '.input.json')
        path.write_bytes(raw if raw is not None else json.dumps(document).encode())
        command = [str(binary), mode, str(path)]
        run = subprocess.run(command, env=env, capture_output=True, timeout=35)
        stdout, stderr = out / (name + '.stdout.json'), out / (name + '.stderr.txt')
        stdout.write_bytes(run.stdout)
        stderr.write_bytes(run.stderr)
        records.append(dict(command=command, exit_code=run.returncode, expected_success=good,
                            input=bind(path), stdout=bind(stdout), stderr=bind(stderr)))
        assert (run.returncode == 0) == good, (name, run.stderr.decode())
        assert b'AddressSanitizer' not in run.stderr and b'runtime error:' not in run.stderr
        return json.loads(run.stdout) if good else None

    cases = []
    # All capacities from the retained suffix, H0 FAR and H1 NEAR/FAR; every
    # registered service package. Paths remain strings and are never opened.
    for context in (3, 4, 5, 6, 9):
        original = next(item for item in items if item['capture']['context_ordinal'] == context)
        for package_index, package in enumerate(('R0', 'R1', 'R2', 'L0', 'L1')):
            document = {k: copy.deepcopy(original[k]) for k in ('capture', 'resources', 'monitoring')}
            document['hardware_prestate'] = copy.deepcopy(prestate)
            c, r = document['capture'], document['resources']
            c.pop('context_ordinal')
            c.pop('minimum_observations_per_series')
            c.update(schema_version='cpu-prefetch-stage17-formal-service-capture/1',
                     method_id='SERVICE-RATE-NP-LTL95C95-MIN-v1', package=package,
                     cell_ordinal=package_index * 12 + context,
                     software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1',
                     linked_order=None, ring_distance=None)
            for rows in r['phase_capacity']:
                rows.pop('producer_demand_rows')
                rows.pop('consumer_demand_rows')
            if package in ('R1', 'R2'):
                c['ring_distance'] = dict(cache_lines=1 if package == 'R1' else 2,
                    calibration_evidence_id='' if package == 'R1' else 'COLD-TEST-ONLY-D246')
            if package in ('L0', 'L1'):
                c['linked_order'] = dict(seed_id='COLD-TEST-ONLY-LINKED-ORDER', seed_hex='c' * 64,
                    namespace_id='COLD-TEST-ONLY-NODE-ORDER',
                    arena_alignment_bytes=c['geometry']['base_page_bytes'])
            label = f'{package}-context-{context}'
            result = invoke(document, label)
            assert result['source_revision'] == '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
            assert result['source_dirty'] is False and result['execution_authority'] is False
            assert result['hardware_observation'] is False and result['performance_measurement'] is False
            layout = result['layout']
            assert len(layout['region_bytes']) == 7
            # Qualified ServiceEnvelope::make_layout adds three stack guard pages.
            assert layout['total_mapping_bytes'] == (sum(layout['region_bytes']) +
                layout['monitor_bytes'] + 3 * c['geometry']['base_page_bytes'])
            assert layout['region_bytes'][5] == layout['core_bytes']
            assert layout['region_bytes'][:3] == [result['workers'][k] for k in
                                                ('records_bytes', 'producer_bytes', 'consumer_bytes')]
            assert (result['workers']['ring'] is not None) == package.startswith('R')
            assert (result['workers']['linked'] is not None) == package.startswith('L')
            document['resources'].update(layout)
            assert invoke(document, label + '-recheck', '--verify-declared') == result
            cases.append((document, result))

    document, expected = cases[0]
    stale = copy.deepcopy(document)
    stale['resources']['core_bytes'] += 4096
    invoke(stale, 'stale-declared', '--verify-declared', good=False)
    assert invoke(stale, 'stale-describe') == expected
    mutations = [
        ('missing-prestate', lambda d: d.pop('hardware_prestate')),
        ('unknown-top-field', lambda d: d.update(unapproved=True)),
        ('prestate-cpu-overflow', lambda d: d['hardware_prestate'][0].update(cpu=2**32)),
        ('prestate-duplicate-cpu', lambda d: d['hardware_prestate'][1].update(cpu=prestate[0]['cpu'])),
        ('prestate-float', lambda d: d['hardware_prestate'][0].update(value=0.0)),
        ('budget-too-small', lambda d: d['capture']['budget'].update(memory_bytes=1)),
        ('invalid-capacity', lambda d: d['capture']['geometry'].update(capacity=0)),
        ('wrong-software-mapping', lambda d: d['capture'].update(software_prefetch_mapping_id='wrong')),
        ('wrong-cell', lambda d: d['capture'].update(cell_ordinal=60)),
    ]
    for name, mutate in mutations:
        changed = copy.deepcopy(document)
        mutate(changed)
        invoke(changed, name, good=False)
    invoke(None, 'duplicate-key', raw=b'{"capture":{},"capture":{}}', good=False)
    invoke(None, 'non-json', raw=b'not JSON', good=False)
    # Changing only cold declarations may be sized but not silently accepted
    # as an empirically qualified or signed future family.
    smaller = copy.deepcopy(document)
    for phase in range(2):
        smaller['capture']['budget']['phases'][phase].update(producer_attempt_limit=10,
                                                            consumer_poll_limit=10)
        smaller['resources']['phase_capacity'][phase].update(producer_primary_rows=10,
                                                            consumer_primary_rows=10)
    small = invoke(smaller, 'explicit-software-test-cap-10')
    assert small['layout']['total_mapping_bytes'] < expected['layout']['total_mapping_bytes']
    output = dict(status='PASS', checks=len(records), request=bind(REQUEST),
                  checker=bind(Path(__file__)), binary=bind(binary), cases=records,
                  execution_authority=False, hardware_observation=False, performance_measurement=False,
                  prospective_q16b_caps_frozen=False, native_libraries_instrumented=False,
                  caller_sanitizers=args.sanitizers)
    (out / 'verification.json').write_text(json.dumps(output, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: v for k, v in output.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
