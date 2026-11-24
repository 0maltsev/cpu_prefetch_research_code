"""D254 metadata-only reuse of the actual D246/D247 retained Q16a result.

consume(document, *, validation, plan, selected_duration_ns,
        original_validation, original_plan, compatibility,
        original_boot_id, boot_id)

The caller authenticates both qualification contexts and both boot identities
from its verified packet/qualification, as in the original handoff API. It also
authenticates the compatibility binding in that packet. This module verifies
bound bytes; an arbitrary self-authored manifest is not provenance or authority.

compatibility is a {path, size_bytes, sha256} binding to this closed JSON shape:
  schema_version: SCHEMA
  scope: {decision: D254, purpose: PURPOSE, stand_id, boot_id}
  original/current: {source_revision, bundle_root, worker, bundle_inventory,
                     formal_codegen}
  original_plan/plan/handoff: bindings to the actual supplied documents
  source_comparisons: [{relative_path, original: binding, current: binding}]
  queue_libraries: {original: binding, current: binding}
  project_headers: [{relative_path, original: binding, current: binding}]
  native_geometry: binding to current software-native-ring-slot-geometry/1
  platform_manifests: {original: binding, current: binding}
  execution_authority: false
  phase18_authority: false

All file references are exact BoundReader bindings. Source comparisons cover
the complete qualified include/src and strict codegen dependency closure, with
only the reviewed cold parser change. Library and all three headers must be
byte identical. Native output has exactly source_revision, source_dirty, api,
hardware_observation, execution_authority, schema_version and six records;
each record has context_ordinal, capacity, cache_line_bytes, slot_storage_bytes.
The caller supplies authenticated query provenance tying that output to these
actual current library/header bytes. No query, disassembly or raw validation
is executed here. No calibration fields or original module globals are changed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from jsonschema import Draft202012Validator, ValidationError

import stage17_q16a_handoff_v1 as original
import stage17_q16a_continuation_admission_v1 as admission
import stage17_formal_service_daycap_v1 as daycap
import stage17_formal_plan_v2 as historical
import check_formal_codegen as codegen

SCHEMA = 'cpu-prefetch-stage17-q16a-daycap-compatibility/1'
PURPOSE = 'RETAINED-Q16A-FOR-D254-DAYCAP-Q16B'
OLD_WORKER = '7abf4cfac0051103f98b3f63f37efd1bde757d954c973460be6fe4d245f6a275'
COLD_SOURCE = 'src/runner/stage17_formal_family.cpp'
COLD_SHA256 = '6d18ae41bd0a51d173ea98a53b9e88f13a245efd296f8d4e0a6a4558915d2951'
QUEUE = 'release/lib/libcpu_prefetch_queue.a'
HEADERS = (
    'include/cpu_prefetch/foundation/repository_info.hpp',
    'include/cpu_prefetch/queue/common.hpp',
    'include/cpu_prefetch/queue/ring_spsc.hpp',
)
Error = original.Error
require, same, fields = admission.require, admission.same, admission.fields


def _release(side, context, reader, expected_source):
    fields(side, 'source_revision bundle_root worker bundle_inventory formal_codegen', 'release')
    same(side['source_revision'], expected_source, 'actual release source')
    same(context['source_revision'], expected_source, 'qualified release source')
    root = side['bundle_root']
    admission.contract._path(root)
    require(Path(root).resolve(strict=True) == Path(root), 'bundle root symlink')
    same(root, context['archive_bundle_root'], 'qualified bundle root')
    same(side['worker'], dict(path=context['release_artifact_path'],
        size_bytes=context['release_artifact_size_bytes'], sha256=context['release_artifact_sha256']),
        'actual qualified worker')
    same(side['bundle_inventory']['sha256'], context['inventory_sha256'], 'qualified inventory')
    for key, name in (('worker', 'release/bin/cpu_prefetch_runner'),
                      ('bundle_inventory', 'BUNDLE_INVENTORY.json'),
                      ('formal_codegen', 'build-provenance/formal_codegen_report.json')):
        same(side[key]['path'], admission._member(root, name), 'qualified ' + key + ' path')
    index = admission._inventory(reader.document(side['bundle_inventory']))
    # Validate every inventory locator, including entries outside the source set.
    for name in index:
        admission._member(root, name)
    for key, name in (('worker', 'release/bin/cpu_prefetch_runner'),
                      ('formal_codegen', 'build-provenance/formal_codegen_report.json')):
        same(side[key], dict(index[name], path=admission._member(root, name)), 'inventory ' + key)
    reader.read(side['worker'])
    report = reader.document(side['formal_codegen'])
    return root, index, report


def _comparison(rows, names, releases, reader, *, identical):
    require(type(rows) is list and len(rows) == len(names), 'exact comparison coverage')
    seen = set()
    for row in rows:
        fields(row, 'relative_path original current', 'comparison')
        name = row['relative_path']
        require(type(name) is str and name in names and name not in seen, 'omitted/duplicate/foreign source')
        seen.add(name)
        contents = []
        for side in ('original', 'current'):
            root, index, _ = releases[side]
            same(row[side], dict(index[name], path=admission._member(root, name)), 'actual ' + side + ' member')
            contents.append(reader.read(row[side]))
        if identical or name != COLD_SOURCE:
            require(contents[0] == contents[1], 'byte-identical ' + name + ' differs')
        else:
            same(row['current']['sha256'], COLD_SHA256, 'reviewed cold family admission')


def _native(binding, retained, reader, source_revision):
    native = reader.document(binding)
    fields(native, 'schema_version source_revision source_dirty api hardware_observation execution_authority records',
           'current native geometry')
    for key, expected in dict(schema_version='software-native-ring-slot-geometry/1', source_revision=source_revision,
                              source_dirty=False, api='RingSpscQueue::storage_requirements',
                              hardware_observation=False, execution_authority=False).items():
        same(native[key], expected, 'current native ' + key)
    require(type(native['records']) is list and len(native['records']) == 6, 'six current native contexts')
    for row, prior in zip(native['records'], retained, strict=True):
        fields(row, 'context_ordinal capacity cache_line_bytes slot_storage_bytes', 'native context')
        same(row, {key: prior[key] for key in row}, 'current actual queue API layout')


def _platforms(bindings, old_validation, validation, reader):
    fields(bindings, 'original current', 'actual platform manifests')
    schema = admission._json((daycap.native.ROOT /
        'protocol/2.0.0-pre.3/handoff/schemas/platform.schema.json').read_bytes())
    manifests = []
    for side, verified in (('original', old_validation), ('current', validation)):
        context = verified.resolutions['S17-EXT-004'].semantic_context
        manifest = reader.document(bindings[side])
        Draft202012Validator(schema).validate(manifest)
        measurements = context['pilot_platform_measurements']
        same(bindings[side]['sha256'], measurements['platform_manifest_sha256'], side + ' qualified platform bytes')
        same(manifest['platform_id'], context['stand_id'], side + ' platform stand')
        same(manifest['record_sha256'], measurements['q15_r_result_sha256'], side + ' actual Q15-R platform lineage')
        same(manifest['record_sha256'], context['q15_r']['result_sha256'], side + ' verified Q15-R result')
        clock_id = manifest['clock']['acceptance_record_id']
        clocks = [row for row in context['qualification_evidence'] if row['kind'] == 'SELECTED_PAIR_CLOCK'
                  and row['artifact_id'] == clock_id and row['eligible'] is True and row['stand_id'] == context['stand_id']]
        require(len(clocks) == 1 and clock_id in context['artifact_index'], side + ' verified clock acceptance')
        outputs = {row['sha256'] for row in context['q15_r']['result']['artifacts']}
        for state in manifest['hardware_prefetch_states']:
            for key in ('readback_artifact_id', 'behavioral_probe_artifact_id'):
                ref = state[key]
                require(ref in context['artifact_index'] and context['artifact_index'][ref]['sha256'] in outputs,
                        side + ' verified current Q15-R ' + key)
            authority = state['privileged_authority_id']
            require(authority == 'NONE' or authority == context['q15_r']['authorization']['authorization_id'],
                    side + ' verified Q15-R authority reference')
        manifests.append(manifest)
    old, current = manifests
    for key in ('schema_version', 'protocol_version', 'platform_id', 'cpu', 'topology', 'memory', 'software'):
        same(current[key], old[key], 'same actual platform ' + key)
    same({k: v for k, v in current['clock'].items() if k != 'acceptance_record_id'},
         {k: v for k, v in old['clock'].items() if k != 'acceptance_record_id'}, 'same actual platform clock')
    same([{k: row[k] for k in ('requested', 'verified')} for row in current['hardware_prefetch_states']],
         [{k: row[k] for k in ('requested', 'verified')} for row in old['hardware_prefetch_states']],
         'same actual requested/verified prefetch states')


def _reuse(plan, original_plan, result, handoff_binding):
    # Compare actual placement/working-set geometry, not context_ordinal modulo
    # on the service plan (which has package-major cell identities).
    prior_geometries = {}
    service_parent = original_plan['action_id'] == 'Q16b'

    def geometry_key(capture):
        context = capture['placement'], capture['working_set_class']
        return (capture['hardware_state'], capture['package'], *context) if service_parent else context

    for item in original_plan['captures']:
        capture = item['capture']
        key = geometry_key(capture)
        prior = prior_geometries.setdefault(key, capture['geometry'])
        same(capture['geometry'], prior, 'retained paired geometry')
    require(len(prior_geometries) == (60 if service_parent else 6), 'complete retained setting geometry')
    evidence_id = 'q16a-sha256-' + handoff_binding['sha256']
    for item in plan['captures']:
        capture = item['capture']
        context = (0 if capture['placement'] == 'NEAR' else 3) + daycap.native.WORKING_SETS.index(
            capture['working_set_class'])
        same(capture['geometry'], prior_geometries[geometry_key(capture)],
             'all service settings retain qualified geometry')
        for key in ('capacity', 'cache_line_bytes'):
            same(capture['geometry'][key], result['ring_geometry'][context][key], 'retained native ' + key)
        if capture['package'] == 'R2':
            same(capture['ring_distance'], dict(
                cache_lines=result['derived_result']['contexts'][context]['distance']['d2_cache_lines'],
                calibration_evidence_id=evidence_id), 'exact retained R2 distance/evidence')


def consume(document, *, validation, plan, selected_duration_ns, original_validation,
            original_plan, compatibility, original_boot_id, boot_id):
    """Return original.consume's unchanged result, or reject with Error.

    original_plan is the actual completed source42 Q16a continuation plan or
    actual signed historical Q16b plan. Its authenticated binding is supplied
    by the caller; a Q16a plan must also match the retained population identity.
    Boot arguments are verified packet values, never live reads.
    No default current worker hash is supplied: qualification binds its bytes.
    """
    try:
        # Preserve every original audited-artifact, qualification, summary and
        # exact arithmetic check using the actual old source and actual old plan.
        result = original.consume(document, validation=original_validation, plan=original_plan,
                                  selected_duration_ns=selected_duration_ns)
        reader = admission.BoundReader()
        proof = reader.document(compatibility)
        fields(proof, 'schema_version scope original current original_plan plan handoff source_comparisons '
               'queue_libraries project_headers native_geometry platform_manifests execution_authority phase18_authority',
               'daycap compatibility')
        same(proof['schema_version'], SCHEMA, 'daycap compatibility version')
        for flag in ('execution_authority', 'phase18_authority'):
            same(proof[flag], False, 'compatibility authority')
        require(type(boot_id) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot_id),
                'verified boot identity required')
        same(original_boot_id, boot_id, 'same verified boot')
        fields(proof['scope'], 'decision purpose stand_id boot_id', 'compatibility scope')
        same(proof['scope'], dict(decision='D254', purpose=PURPOSE, stand_id=result['stand_id'], boot_id=boot_id),
             'compatibility reuse scope')
        for key, value in (('handoff', document), ('original_plan', original_plan), ('plan', plan)):
            same(reader.document(proof[key]), value, 'bound actual ' + key)
        require(original_plan['action_id'] in ('Q16a', 'Q16b'), 'actual retained action')
        if original_plan['action_id'] == 'Q16a':
            population = [row for row in result['source_populations'] if row['source_revision'] == original.SOURCE]
            require(len(population) == 1, 'one retained source42 population')
            same(hashlib.sha256(admission.canonical(original_plan)).hexdigest(), population[0]['plan_sha256'],
                 'actual completed source42 plan identity')
        else:
            require(original_plan['schema_version'] in (daycap.native.VERSION['Q16b'], historical.VERSION['Q16b']),
                    'actual signed historical service plan version')
        old = original_validation.resolutions['S17-EXT-006'].semantic_context
        current = validation.resolutions['S17-EXT-006'].semantic_context
        source = current['source_revision']
        require(type(source) is str and re.fullmatch(r'[0-9a-f]{40}', source) and source != original.SOURCE,
                'actual new qualified source revision required')
        same(old['inventory_sha256'], original.INVENTORY, 'actual old inventory')
        same(old['release_artifact_sha256'], OLD_WORKER, 'actual old worker')
        for key in ('archive_bundle_root', 'release_artifact_sha256', 'inventory_sha256'):
            require(current[key] != old[key], 'new qualification must not relabel old ' + key)
        same(plan['source_revision'], source, 'actual daycap source')
        same(plan['stand_id'], result['stand_id'], 'same plan stand')
        for verified in (original_validation, validation):
            for key in ('S17-EXT-004', 'S17-EXT-006'):
                same(verified.resolutions[key].semantic_context['stand_id'], result['stand_id'], 'qualified stand')
        _platforms(proof['platform_manifests'], original_validation, validation, reader)
        # Validate the complete /3 schema AND semantic body; the legacy capture
        # method is checked by validate_plan, not substituted with family method.
        schema = admission._json((daycap.native.ROOT / daycap.SCHEMA).read_bytes())
        Draft202012Validator(schema).validate(plan)
        daycap.validate_plan(plan)
        releases = {side: _release(proof[side], context, reader, source)
                    for side, context, source in (('original', old, original.SOURCE), ('current', current, source))}
        fields(proof['queue_libraries'], 'original current', 'queue libraries')
        queue_row = dict(relative_path=QUEUE, **proof['queue_libraries'])
        _comparison([queue_row], {QUEUE}, releases, reader, identical=True)
        _comparison(proof['project_headers'], set(HEADERS), releases, reader, identical=True)
        names = admission._source_names(releases['original'][1])
        same(sorted(names), sorted(admission._source_names(releases['current'][1])), 'strict qualified source closure')
        require(COLD_SOURCE in names and set(HEADERS) <= names, 'required native dependency closure')
        _comparison(proof['source_comparisons'], names, releases, reader, identical=False)
        for side, (root, _, report) in releases.items():
            codegen.validate_report_bindings(report, binary=Path(proof[side]['worker']['path']), source_root=Path(root))
        geometry = reader.document(document['geometry'])
        same(proof['queue_libraries']['original'], geometry['shared_queue_libraries']['continuation'],
             'actual retained source42 queue library')
        same(sorted(geometry['verified_headers']), sorted(HEADERS), 'actual retained project headers')
        _native(proof['native_geometry'], result['ring_geometry'], reader, source)
        _reuse(plan, original_plan, result, proof['handoff'])
        reader.finish()
        return result
    except Error:
        raise
    except (OSError, KeyError, TypeError, ValueError, OverflowError, AttributeError,
            admission.contract.ContractError, daycap.ContractError, ValidationError, codegen.AuditError) as error:
        raise Error('D254 Q16a handoff rejected: ' + str(error)) from error
