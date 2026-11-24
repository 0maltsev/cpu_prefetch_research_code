"""D247 reuse of the exact completed D246 composition, without raw reanalysis.

This incident-bound gate accepts only previously authenticated, reviewed bytes.
It is not a general attestation verifier and cannot accept a replacement family.
"""
from __future__ import annotations

import stage17_q16a_continuation_admission_v1 as admission
import stage17_formal_calibration_v1 as math

SCHEMA = 'cpu-prefetch-stage17-q16a-composition-handoff/1'
SOURCE = '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
INVENTORY = '8e657978d848ae8c633036536357741fff02388788b0f6a18f2e13e5dc6d5397'
# Independent signed-lifecycle/producer/geometry verification completed in D246.
# These are identities of the audited originals, not hashes supplied by a plan.
ACCEPTED = {
    'completion': (1030, '954c13f435573b33ddb9ec144e0111c4a29a7e0da62e2df622f5ad2fe419f906'),
    'composition': (629535, '3c84e5436cedf2e513b28be3f7dc44fa6f44afc3632a728eb3b82d66be89192f'),
    'geometry': (4329, '9076992ec8d993a314fd7d8b8134b7642e1127b1bfe730001bf1c663e7d76e87'),
}
Error = admission.AdmissionError
require, same = admission.require, admission.same


def consume(document, *, validation, plan, selected_duration_ns):
    """Return the original two-source calibration for later ring reuse only.

    A signed prospective request must bind this handoff. Original authentication
    is reused only for the three exact D246 artifacts; no caller flags, changed
    byte bindings or generic composite packet can establish that provenance.
    """
    try:
        admission.fields(document, 'schema_version completion composition geometry execution_authority phase18_authority', 'Q16a handoff')
        same(document['schema_version'], SCHEMA, 'handoff version')
        for flag in ('execution_authority', 'phase18_authority'):
            same(document[flag], False, 'handoff authority')
        reader = admission.BoundReader()
        evidence = {}
        for key, (size, digest) in ACCEPTED.items():
            binding = document[key]
            same([binding['size_bytes'], binding['sha256']], [size, digest], 'audited D246 ' + key)
            evidence[key] = reader.document(binding)
        complete, packet, geometry = (evidence[k] for k in ('completion', 'composition', 'geometry'))
        for key in ('composition', 'geometry'):
            same([complete[key]['size_bytes'], complete[key]['sha256']], list(ACCEPTED[key]), 'completed artifact identity')
        same(complete['status'], 'AUTHENTICATED_COMPOSITION_COMPLETE', 'actual completion')
        same(geometry['status'], 'VERIFIED_SHARED_NATIVE_QUEUE_GEOMETRY', 'actual geometry verification')
        result = packet['calibration']
        context = validation.resolutions['S17-EXT-006'].semantic_context
        same(context['source_revision'], SOURCE, 'qualified continuation source')
        same(context['inventory_sha256'], INVENTORY, 'qualified continuation inventory')
        same(plan['source_revision'], SOURCE, 'prospective continuation source')
        same(geometry['continuation_source_revision'], SOURCE, 'native geometry source')
        same(geometry['shared_queue_libraries']['continuation']['path'],
             context['archive_bundle_root'] + '/release/lib/libcpu_prefetch_queue.a', 'qualified native bundle')
        platform = validation.resolutions['S17-EXT-004'].semantic_context['pilot_platform_measurements']
        same(geometry['platform_manifest']['sha256'], platform['platform_manifest_sha256'], 'qualified actual platform')
        same(result['stand_id'], plan['stand_id'], 'calibration stand')
        same(result['prospective']['measurement_ns'], selected_duration_ns, 'discovery duration')
        same(result['prospective']['minimum_observations_per_series'], 100000, 'accepted observation minimum')
        same(result['ring_geometry'], geometry['records'], 'actual native geometry')
        same(result['status'], 'VALIDATED', 'complete calibration')
        require(len(result['run_sources']) == 708, 'complete original source product')
        ids = set()
        for ordinal, row in enumerate(result['run_sources']):
            same(row['original_slot'], ordinal, 'original analysis slot')
            same(row['validity'], 'VALID', 'retained report validity')
            math._check_summary('Q16a', row['summary'], result['prospective'])
            for role in ('warmup_run_id', 'measurement_run_id'):
                require(row[role] not in ids, 'unique original run identity')
                ids.add(row[role])
        status, derived = math._derive('Q16a', result['prospective'], result['run_sources'], result['ring_geometry'])
        same(status, result['status'], 'recomputed calibration status')
        same(derived, result['derived_result'], 'exact retained-summary arithmetic')
        reader.finish()
        # Retain original schema, histories, FULL outcomes and conservative flags.
        return result
    except Error:
        raise
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as error:
        raise Error('Q16a handoff rejected: ' + str(error)) from error
