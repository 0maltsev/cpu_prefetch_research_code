"""D282 pure full180 continuation from the exact unobserved original bank."""
import copy
import hashlib

import stage17_q16c_empty_reuse_v1 as reuse


def digest(master, domain):
    return hashlib.sha256(bytes.fromhex(master) + b'\0' + domain.encode('ascii')).hexdigest()


def prepare(old, setup, *, master_hex):
    reuse.require(type(master_hex) is str and len(master_hex) == 64
        and all(c in '0123456789abcdef' for c in master_hex), 'prospective256-bit master required')
    reuse.require(len(setup['sources']) == 360, 'complete original source bank')
    plan = copy.deepcopy(old)
    plan.update(source_revision=reuse.SOURCE, plan_id='CPU-PREFETCH-V5-V29-Q16C-D282-PLAN-1')
    phase = []; nodes = []
    for ordinal, item in enumerate(plan['captures']):
        c = item['capture']
        for name, letter in (('warmup', 'W'), ('measurement', 'M')):
            namespace = 'CPU-PREFETCH-V5-V29-Q16C-ARENA-'+name.upper()+'-1'
            run = 'C29'+letter+f'{ordinal:08d}'
            row = dict(namespace_id=namespace, seed_id=namespace+f'-SEED-{ordinal:04d}',
                run_id=run, seed_hex=digest(master_hex, namespace+'\0'+run))
            c[name] = row; phase.append(copy.deepcopy(row))
        c['arena_seed'] = copy.deepcopy(c['measurement'])
        if c['linked_order'] is not None:
            node = dict(seed_id=f'CPU-PREFETCH-V5-V29-Q16C-NODES-SEED-{ordinal:04d}',
                namespace_id='CPU-PREFETCH-V5-V29-Q16C-NODES-1',
                seed_hex=digest(master_hex, 'Q16C-NODES\0'+str(ordinal)))
            c['linked_order'].update(node); nodes.append(node)
        for row in item['monitoring']['environment_sources']:
            if '/reserved/cpuset.' in row['path']:
                row['path']='/sys/fs/cgroup/cpu-prefetch-recovery-v29-qualified-1.service/reserved/'+row['path'].rsplit('/',1)[1]
    plan.update(warmup_namespace=phase[0]['namespace_id'], measurement_namespace=phase[1]['namespace_id'])
    reuse.compare_plan(plan, old)
    identities = dict(schema_version='cpu-prefetch-stage17-q16c-restart-identities/1',
        phase_identities=phase, linked_order_identities=nodes, original_source_setup=copy.deepcopy(setup),
        consumer_source_revision=reuse.SOURCE, execution_authority=False, phase18_authority=False)
    return plan, identities
