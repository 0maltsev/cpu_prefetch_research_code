"""D282 exact empty-attempt and unobserved-bank reuse; no execution on import."""
import copy
from pathlib import Path
import types

import stage17_q16c_source_receipts_v1 as original
import stage17_q16c_admission_limits_v1 as limits

admission = limits.ADMISSION
require, same = admission.require, admission.same
SOURCE = '7fb894425c82fa7d7f1891f52b3bcdacc2c83585'
WORKER = '7455fa2802ca5f655c41faddd070da51b0cf98ac9c8b2360152dc1a480f85f2a'
OLD_SOURCE = '919c48637cbdba9e466a3104f5cbb39f7184e39b'
OLD_WORKER = '1baa213a137679460348ff6b861839044022957a4de0e5fc79929f7b49bed883'
OLD_PLAN = '4a0eb6531c93141b1215a5aa5c18bae0831a0d6f4d6e80f949856c77d9b9fda8'
OLD_REQUEST = 'b9ad4de048bfc239bb9574cfacfd10e70bb9d145e284a8e71ae9ba5e3c7f699f'
OLD_AUTHORIZATION = '93400332a0ae6952efbdff39253489bc3a79972d285df4660aa3e175c65e30ae'
FIXED = dict(failure='bebd1f5bf5d634ff7dc6c91ef43590c3942d89fc6652ac184b770393a74124a5',
    checkpoint='fa80857188d0636876291404593645920f531e60b194a4cf343bdfb024a5fc47',
    restoration='092ef7431502a83f712f913cded70770d305b8ba95b88f6b0c34c626046660c5')
SCHEMA = 'cpu-prefetch-stage17-q16c-empty-attempt-reuse/1'


def empty(checkpoint, failure, restoration):
    same(checkpoint['plan_sha256'], OLD_PLAN, 'exact failed family')
    same(checkpoint['capture_ordinal'], 0, 'only first capture attempted')
    require(checkpoint['native_complete'] is False and checkpoint['artifacts'] == []
        and checkpoint['scientific_validity'] == 'NOT_ASSESSED', 'zero successful/raw observations required')
    n = checkpoint['native_result_after_cleanup']
    require(type(n['stop']) is int and n['stop'] == 13 and n['session'] is None
        and n['clock_origin'] is None and n['publication_attempted'] is False
        and n['publication_succeeded'] is False and n['worker_mappings'] is None
        and n['worker_stacks'] is None, 'capture must stop before session/publication')
    for key in ('core_mapping', 'monitor_mapping', 'controller_stack'):
        row = n[key]
        require(type(row['requested']['bytes']) is int and row['requested']['bytes'] == 0
            and type(row['stop']) is int and row['stop'] == 0 and row['mapping'] is None
            and row['cleanup_attempted'] is False, 'no native mappings may have started')
    require(failure['leader_reaped'] is True and failure['process_group_gone'] is True
        and failure['restoration_verified'] is True and failure['quarantine_operation']['performed'] is False,
        'actual failed-worker cleanup/restoration required')
    same(failure['request_sha256'], OLD_REQUEST, 'original request')
    same(failure['authorization_sha256'], OLD_AUTHORIZATION, 'original authority')
    same(failure['runtime_sha256'], OLD_WORKER, 'original failed executable')
    rows = failure['recovery_readback']
    require(len(rows) == 3 and {r['cpu'] for r in rows} == {0, 1, 8}
        and all(r['matches'] is True and r['observed_hex'] == r['requested_hex'] for r in rows),
        'complete exact original hardware restoration')
    require(restoration['verified'] is True and restoration['errors'] == [], 'actual isolation restoration')


def comparable(item):
    """Remove only approved fresh identities and complete cpuset relocation."""
    item = copy.deepcopy(item)
    c = item['capture']
    for name in ('warmup', 'measurement', 'arena_seed'):
        c.pop(name)
    if c['linked_order'] is not None:
        for name in ('seed_id', 'seed_hex', 'namespace_id'):
            c['linked_order'].pop(name)
    changed = 0
    for row in item['monitoring']['environment_sources']:
        if '/reserved/cpuset.' in row['path']:
            row['path'] = row['path'].rsplit('/', 1)[1]
            changed += 1
    require(changed == 5, 'complete five-file cpuset relocation')
    return item


def compare_plan(plan, old):
    same(plan['source_revision'], SOURCE, 'corrected consumer source')
    same(old['source_revision'], OLD_SOURCE, 'original source producer')
    require(len(plan['captures']) == len(old['captures']) == 180, 'full180 required')
    phase_ids, seeds = set(), set()
    old_rows = [c['capture'][p] for c in old['captures'] for p in ('warmup', 'measurement')]
    old_rows += [s for c in old['captures'] for s in c['capture']['schedules']]
    old_rows += [c['capture']['linked_order'] for c in old['captures'] if c['capture']['linked_order'] is not None]
    old_seeds = {r['seed_hex'] for r in old_rows}
    old_ids = {r[k] for r in old_rows for k in ('seed_id', 'namespace_id')}
    fresh_ids = set()
    for a, b in zip(plan['captures'], old['captures'], strict=True):
        same(comparable(a), comparable(b), 'unchanged scientific/native capture and limits')
        for p in ('warmup', 'measurement'):
            row = a['capture'][p]
            require(len(row['run_id']) == 12 and row['run_id'].startswith('C29')
                and row['run_id'] not in phase_ids and row['seed_hex'] not in old_seeds
                and row['seed_hex'] not in seeds, 'fresh prospective phase/run/seed')
            require(row['seed_id'] not in old_ids | fresh_ids and row['namespace_id'] not in old_ids,
                'fresh phase seed/namespace identity')
            fresh_ids.add(row['seed_id'])
            phase_ids.add(row['run_id']); seeds.add(row['seed_hex'])
        same(a['capture']['arena_seed'], a['capture']['measurement'], 'measurement arena seed')
        if a['capture']['linked_order'] is not None:
            seed = a['capture']['linked_order']['seed_hex']
            require(seed not in seeds and seed not in old_seeds, 'fresh linked order seed')
            node = a['capture']['linked_order']
            require(node['seed_id'] not in old_ids | fresh_ids and node['namespace_id'] not in old_ids,
                'fresh linked order identities')
            fresh_ids.add(node['seed_id'])
            seeds.add(seed)
    a, b = copy.deepcopy(plan), copy.deepcopy(old)
    for v in (a, b):
        for name in ('captures', 'plan_id', 'source_revision', 'warmup_namespace', 'measurement_namespace'):
            v.pop(name)
    same(a, b, 'unchanged family methods, transport/storage/quota and finite budgets')


def inspect(proof, plan, *, validation=None):
    admission.fields(proof, 'schema_version decision original_plan original_context original_request original_authorization '
        'original_signature checkpoint failure restoration custody', 'D282 empty-attempt reuse')
    same(proof['schema_version'], SCHEMA, 'explicit incident version')
    same(proof['decision'], 'D282', 'approved incident only')
    reader = admission.BoundReader()
    for key, digest in {**FIXED, 'original_plan': OLD_PLAN, 'original_request': OLD_REQUEST,
                        'original_authorization': OLD_AUTHORIZATION}.items():
        same(proof[key]['sha256'], digest, 'original immutable '+key)
    docs = {k: reader.document(proof[k]) for k in ('original_plan', 'original_context', 'original_request',
        'original_authorization', 'checkpoint', 'failure', 'restoration', 'custody')}
    reader.read(proof['original_signature'])
    empty(docs['checkpoint'], docs['failure'], docs['restoration'])
    same(docs['original_request']['action_inputs']['plan'], docs['original_plan'], 'actual signed original plan')
    require(docs['custody']['artifacts'] == [] and docs['custody']['status'] == 'ARCHIVED_AND_RELEASED',
        'only empty checkpoint custody may exist')
    folder = Path(proof['checkpoint']['path']).parent
    same(sorted(p.name for p in folder.glob('formal-capture-*-final-checkpoint.json')),
        ['formal-capture-0-final-checkpoint.json'], 'no later original observation')
    compare_plan(plan, docs['original_plan'])
    exported = docs['original_context']
    admission.fields(exported, 'schema_version boot_id resolutions execution_authority phase18_authority', 'actual original qualification export')
    same(exported['schema_version'], 'cpu-prefetch-stage17-original-source-qualification-export/1',
        'actual original producer-context version')
    same(exported['boot_id'], '4c08cd05-b362-49dd-b37f-629e9c7ad79a', 'same original stand boot')
    admission.fields(exported['resolutions'], 'S17-EXT-003 S17-EXT-006', 'exact producer trust/release export')
    require(exported['execution_authority'] is False and exported['phase18_authority'] is False, 'export grants no action')
    old = types.SimpleNamespace(resolutions={k: types.SimpleNamespace(semantic_context=v['semantic_context'])
        for k, v in exported['resolutions'].items()})
    release = old.resolutions['S17-EXT-006'].semantic_context
    same(release['source_revision'], OLD_SOURCE, 'actual original qualified source')
    same(release['release_artifact_sha256'], OLD_WORKER, 'actual original qualified worker')
    trust = old.resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and trust['subject_id']==plan['stand_id'],
        'actual original stand owner')
    original.controller.support._verify_signature(reader.read(proof['original_authorization']),
        Path(proof['original_signature']['path']), trust)
    if validation is not None:
        current = validation.resolutions['S17-EXT-006'].semantic_context
        same(current['source_revision'], SOURCE, 'actual corrected qualification')
        same(current['release_artifact_sha256'], WORKER, 'actual corrected worker')
        for key in ('archive_bundle_root', 'inventory_sha256', 'release_artifact_sha256'):
            require(current[key] != release[key], 'do not relabel original '+key)
        roots = {side: Path(v['archive_bundle_root']) for side, v in [('original', release), ('current', current)]}
        closure = original.semantic.discover_python_closure(roots['original'], ('generate_schedule', 'stage17_q16c_schedule_provenance_v2'))
        same(closure, original.semantic.discover_python_closure(roots['current'], ('generate_schedule', 'stage17_q16c_schedule_provenance_v2')),
            'complete identical generator closure')
        closure |= {'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json',
            'config/schemas/schedule-derivation-v2.schema.json', 'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'}
        for name in sorted(closure):
            same((roots['original']/name).read_bytes(), (roots['current']/name).read_bytes(), 'unchanged original generator '+name)
    reader.finish()
    return old, docs['original_plan']


def validate(plan, sources, registrations, proof, *, validation, boot_id, deadline_ns, reuse):
    old, original_plan = inspect(reuse, plan, validation=validation)
    # Authenticate the producer using its own original plan/context. Neither its
    # source revision nor its signed generation timestamps are rewritten.
    return original.validate(original_plan, sources, registrations, proof,
        validation=old, boot_id=boot_id, deadline_ns=deadline_ns)
