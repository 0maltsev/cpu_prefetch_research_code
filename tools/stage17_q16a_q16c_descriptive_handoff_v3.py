"""D288 metadata-only Q16a reuse across the five reviewed cold transport files.

Both qualification contexts and the compatibility binding are authenticated by
the caller. Every historical source, result, geometry and physical-platform
check remains mandatory. Current cold-source hashes are incident-specific;
this is not a general exception for future native edits or recalibration.
"""
import hashlib
from pathlib import Path
import re
import types
from jsonschema import Draft202012Validator, ValidationError
import stage17_q16a_daycap_handoff_v1 as previous
import stage17_formal_scheduled_continuation_v1 as daycap

SCHEMA = 'cpu-prefetch-stage17-q16a-q16c-descriptive-compatibility/2'
PURPOSE = 'RETAINED-Q16A-FOR-D288-DESCRIPTIVE-Q16C'
original, admission, historical, codegen = previous.original, previous.admission, previous.historical, previous.codegen
OLD_WORKER = previous.OLD_WORKER
COLD_SOURCE = previous.COLD_SOURCE
QUEUE, HEADERS = previous.QUEUE, previous.HEADERS
Error, require, same, fields = previous.Error, previous.require, previous.same, previous.fields
_release, _platforms, _native, _reuse = previous._release, previous._platforms, previous._native, previous._reuse
REVIEWED_COLD_SOURCES = {'include/cpu_prefetch/runner/stage17_fixed_action.hpp': 'b438925c897188e909879877ddff77e98e690bd756e0637e4d9fd72a78a9c2e9', 'include/cpu_prefetch/runner/stage17_formal_scheduled_action.hpp': '342fb7e4fc9ecfe5b3faf27a85b0b6fd0d1d603d609dc97652db5c72bd739ff6', 'src/runner/stage17_fixed_action.cpp': '03130e61fcd1b61b4cb7b2d1bfc564f1420e87eebcbff428a2b3f7ff4eec764e', 'src/runner/stage17_formal_family.cpp': '773b3e80fdf1eda96f22778884b2057fe34a06ae52593c85ea4c78e8d91e93bc', 'src/runner/stage17_formal_scheduled_action.cpp': '80cb085cbfe0900956d97e7d2104afd4e9766d4b479b56492cedd021033dd8de'}


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
            same(row[side], dict(index[name], path=admission._member(root, name)), 'actual '+side+' member')
            contents.append(reader.read(row[side]))
        if identical or name not in REVIEWED_COLD_SOURCES:
            require(contents[0] == contents[1], 'byte-identical '+name+' differs')
        else:
            same(row['current']['sha256'], REVIEWED_COLD_SOURCES[name], 'reviewed D288 cold source '+name)


_reuse = previous._reuse


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
        same(proof['scope'], dict(decision='D288', purpose=PURPOSE, stand_id=result['stand_id'], boot_id=boot_id),
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
        require(set(REVIEWED_COLD_SOURCES) <= names and set(HEADERS) <= names, 'complete reviewed cold/native dependency closure')
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
        raise Error('D288 Q16a handoff rejected: ' + str(error)) from error
