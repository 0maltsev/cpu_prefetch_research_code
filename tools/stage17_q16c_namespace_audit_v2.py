"""D282 fresh432-seed audit; original360-source bank is separately authenticated."""
import re
from pathlib import Path

import stage17_public_namespace_audit_v1 as old
import stage17_archive_metadata_fast_v1 as metadata
import stage17_q16c_empty_reuse_v1 as reuse


class Matcher:
    text = old.Matcher.text

    def inspect(self, raw, lines=False, limits=old.Limits()):
        text = raw.decode('utf-8', errors='strict')
        records = (line for line in text.splitlines() if line.strip()) if lines else (text,)
        found, plans, nodes, count = set(), set(), 0, 0
        for record in records:
            count += 1
            pending = [(old.parse(record), 0)]
            while pending:
                value, depth = pending.pop(); nodes += 1
                old.require(nodes <= limits.max_json_nodes and depth <= limits.max_depth,
                    'JSON node/depth bound')
                if isinstance(value, str): found.update(self.text(value))
                elif type(value) is int and value in self.numeric:
                    found.add('numeric_seed:'+self.numeric[value])
                elif isinstance(value, dict):
                    if (value.get('action_id') in ('Q16a','Q16b','Q16c','Q17')
                        and isinstance(value.get('captures'), list)
                        and str(value.get('schema_version','')).startswith('cpu-prefetch-stage17-formal-')):
                        plans.add(old.sha(old.canonical(value)))
                    pending.extend((v, depth+1) for v in value.values())
                    pending.extend((k, depth+1) for k in value.keys())
                elif isinstance(value, list): pending.extend((v, depth+1) for v in value)
        old.require(count > 0, 'empty JSONL')
        return sorted(found), sorted(plans)

    def __init__(self, identities):
        old.require(identities['schema_version']=='cpu-prefetch-stage17-q16c-restart-identities/1', 'D282 identities')
        phase = identities['phase_identities']; linked = identities['linked_order_identities']; rows = phase+linked
        old.require(len(phase)==360 and len(linked)==72, 'complete360+72 fresh identities')
        old.require(len({r['run_id'] for r in phase})==360, 'fresh unique phase run IDs')
        for key in ('seed_id','seed_hex'):
            old.require(len({r[key] for r in rows})==432, 'unique432 '+key)
        self.namespaces = {r['namespace_id'] for r in rows}
        self.wanted = {r[k] for r in rows for k in ('seed_id','namespace_id')}
        self.wanted.update(r['run_id'] for r in phase)
        self.numeric = {int(r['seed_hex'],16):r['seed_hex'] for r in rows}
        self.identity_namespace = {r['seed_id']:r['namespace_id'] for r in rows}
        self.identity_namespace.update({r['run_id']:r['namespace_id'] for r in phase})
        self.tokens = re.compile(r'(?=(CPU-PREFETCH-V5-V29-Q16C[A-Za-z0-9_.:-]*|C29[WM][0-9]{8}))')
        self.numbers = re.compile(r'(?<![A-Za-z0-9_])(?:0[xX][0-9a-fA-F]{1,64}|[0-9a-fA-F]{64}|[0-9]{1,78})(?![A-Za-z0-9_])')


def audit(mode, base, identities, *, limits=old.Limits()):
    local = tuple('build/stage17-q16c-d282/'+s for s in (
        'prospective-plan.json','prospective-identities.json','prospective-master.json',
        'software-sizing-packet-1','software-sizing-packet-2',
        'collection-packet-1','collection-packet-2','collection-packet-3'))
    stand = tuple('local-authoring-cpuprefetchv5-29/'+s for s in (
        'software-preparation-1','software-sizing-1','software-preparation-2','software-sizing-2','software-preparation-3','software-sizing-3','q16c-configuration-1'))
    scope = {**old.audit.__globals__, 'LOCAL_EXCLUSIONS':local,'STAND_EXCLUSIONS':stand,
        'FAMILIES':tuple(dict.fromkeys((*old.FAMILIES,reuse.OLD_PLAN)))}
    def roots(selected_mode, selected_base, selected_limits):
        result = old.selected_roots(selected_mode,selected_base,selected_limits)
        if selected_mode == 'local':
            retained = Path(selected_base)/'build/stage17-q16c-d282/original_plan.json'
            raw = old.read_metadata(retained,selected_limits.max_file_bytes)
            old.require(old.sha(old.canonical(old.parse(raw)))==reuse.OLD_PLAN,
                'exact exported original Q16c plan required')
            result.append(retained)
        return result
    scope['selected_roots'] = roots
    scope['exclusions'] = metadata._clone(old.exclusions,scope)
    result = metadata._clone(old.audit,scope)(mode,Path(base),Matcher(identities),limits)
    result.update(schema_version='cpu-prefetch-stage17-q16c-restart-namespace-audit/1',
        planned_phase_identities=360,planned_linked_order_identities=72,planned_numeric_seeds=432,
        reused_source_identities=360,original_source_setup_sha256=old.sha(old.canonical(identities['original_source_setup'])),
        phase18_authority=False)
    return result
