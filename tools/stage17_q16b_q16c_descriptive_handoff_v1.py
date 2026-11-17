"""D270 exact completed17+103 Q16b reuse across reviewed original-source transport.

Caller independently authenticates both qualification contexts, boot identities,
compatibility binding and actual current geometry query provenance. No original
calibration, producer identity, low/FULL result or authority flag is changed.
"""
import re
from pathlib import Path

import stage17_q16b_handoff_v1 as original
import stage17_q16a_q16c_descriptive_handoff_v1 as compatibility
import stage17_formal_scheduled_descriptive_v1 as contract

SCHEMA = 'cpu-prefetch-stage17-q16b-q16c-descriptive-compatibility/1'
PURPOSE = 'RETAINED-D268-Q16B-FOR-D270-DESCRIPTIVE-Q16C'
Error, require, same, fields = original.Error, original.require, original.same, original.fields
admission = original.admission


def consume(document, *, validation, original_validation, plan, selected_duration_ns,
            compatibility_binding, original_boot_id, boot_id):
    try:
        # This authenticates every exact D268 report/plan/completion identity and
        # recomputes descriptive minima in its actual old qualification context.
        result = original.consume(document, validation=original_validation,
                                  selected_duration_ns=selected_duration_ns)
        reader = admission.BoundReader()
        proof = reader.document(compatibility_binding)
        fields(proof, 'schema_version scope original current parent_plan plan handoff source_comparisons '
            'queue_libraries project_headers native_geometry platform_manifests execution_authority phase18_authority',
            'Q16b descriptive compatibility')
        same(proof['schema_version'], SCHEMA, 'Q16b compatibility version')
        for flag in ('execution_authority', 'phase18_authority'): same(proof[flag], False, 'compatibility authority')
        require(type(boot_id) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot_id),
                'verified boot identity required')
        same(original_boot_id, boot_id, 'same actual boot')
        same(proof['scope'], dict(decision='D270', purpose=PURPOSE, stand_id=plan['stand_id'], boot_id=boot_id),
             'incident-scoped compatibility')
        same(reader.document(proof['plan']), plan, 'actual prospective Q16c plan')
        same(reader.document(proof['handoff']), document, 'actual completed Q16b handoff')
        parent = reader.document(proof['parent_plan'])
        same([proof['parent_plan']['size_bytes'], proof['parent_plan']['sha256']],
             list(original.ACCEPTED['parent_plan']), 'original complete120 setting plan')
        contract.validate_plan(plan)
        same(plan['stand_id'], result['stand_id'], 'same actual stand')
        old = original_validation.resolutions['S17-EXT-006'].semantic_context
        current = validation.resolutions['S17-EXT-006'].semantic_context
        source = current['source_revision']
        require(type(source) is str and re.fullmatch('[0-9a-f]{40}', source) and source != original.SOURCE,
                'new actual qualified release required')
        same(plan['source_revision'], source, 'current qualified plan source')
        for verified in (original_validation, validation):
            same(verified.resolutions['S17-EXT-004'].semantic_context['stand_id'], plan['stand_id'], 'actual platform stand')
        for key in ('archive_bundle_root', 'release_artifact_sha256', 'inventory_sha256'):
            require(current[key] != old[key], 'old qualification must not be relabelled '+key)
        compatibility._platforms(proof['platform_manifests'], original_validation, validation, reader)
        releases = {side: compatibility._release(proof[side], context, reader, revision)
            for side, context, revision in (('original', old, original.SOURCE), ('current', current, source))}
        fields(proof['queue_libraries'], 'original current', 'qualified queue libraries')
        compatibility._comparison([dict(relative_path=compatibility.QUEUE, **proof['queue_libraries'])],
            {compatibility.QUEUE}, releases, reader, identical=True)
        compatibility._comparison(proof['project_headers'], set(compatibility.HEADERS), releases, reader, identical=True)
        names = admission._source_names(releases['original'][1])
        same(sorted(names), sorted(admission._source_names(releases['current'][1])), 'complete dependency closure')
        require(set(compatibility.REVIEWED_COLD_SOURCES) <= names, 'complete reviewed cold-source closure')
        compatibility._comparison(proof['source_comparisons'], names, releases, reader, identical=False)
        for side, (root, _, report) in releases.items():
            compatibility.codegen.validate_report_bindings(report, binary=Path(proof[side]['worker']['path']), source_root=Path(root))
        geometry = reader.document(document['geometry'])
        compatibility._native(proof['native_geometry'], geometry['records'], reader, source)
        settings = {}
        def key(c): return c['hardware_state'], c['package'], c['placement'], c['working_set_class']
        for item in parent['captures']:
            c = item['capture']; expected = settings.setdefault(key(c), c)
            same(c['geometry'], expected['geometry'], 'paired original geometry')
        require(len(settings) == 60, 'complete original setting geometry')
        for item in plan['captures']:
            capture = item['capture']; prior = settings[key(capture)]
            for name in ('geometry', 'software_prefetch_mapping_id', 'ring_distance'):
                same(capture[name], prior[name], 'retained actual setting '+name)
            if capture['linked_order'] is not None:
                same(capture['linked_order']['arena_alignment_bytes'], prior['linked_order']['arena_alignment_bytes'],
                     'retained linked arena alignment')
        reader.finish()
        return result
    except Error: raise
    except (OSError, KeyError, TypeError, ValueError, OverflowError, AttributeError,
            compatibility.codegen.AuditError) as error:
        raise Error('D270 Q16b compatibility rejected: '+str(error)) from error
