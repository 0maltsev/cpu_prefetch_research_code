"""D273 fresh792-seed Q16c audit using the retained finite public-history scan.

No historical seed exception, registration, signing or execution authority.
The caller authenticates the prospective identities and the audit source.
"""
import re
from pathlib import Path
import stage17_public_namespace_audit_v1 as old
import stage17_archive_metadata_fast_v1 as metadata
import stage17_q16c_plan_builder_v1 as builder


class Matcher:
    inspect=old.Matcher.inspect
    text=old.Matcher.text

    def __init__(self, identities):
        old.require(identities['schema_version']=='cpu-prefetch-stage17-q16c-prospective-identities/1', 'explicit Q16c identities')
        phase=identities['phase_identities'];sources=identities['source_setup']['sources']
        linked=[row for row,cell in zip(identities['linked_order_identities'],builder.contract.cells('Q16c'),strict=True)
                if cell[2] in ('L0','L1')]
        old.require(len(phase)==360 and len(sources)==360 and len(linked)==72,'complete360+360+72 prospective seeds')
        rows=phase+sources+linked
        for key in ('seed_id','seed_hex'):
            old.require(len({r[key] for r in rows})==792,'unique792 '+key)
        self.namespaces={r['namespace_id'] for r in rows}|{r['parent_namespace_id'] for r in sources}
        self.wanted={r[k] for r in rows for k in ('seed_id','namespace_id')}
        self.wanted.update(r['run_id'] for r in phase)
        self.wanted.update(r[k] for r in sources for k in ('parent_namespace_id','schedule_id','artifact_id','derivation_record_id'))
        self.numeric={int(r['seed_hex'],16):r['seed_hex'] for r in rows}
        self.identity_namespace={r['seed_id']:r['namespace_id'] for r in rows}
        self.identity_namespace.update({r['run_id']:r['namespace_id'] for r in phase})
        self.tokens=re.compile(r'(?=(CPU-PREFETCH-V5-V28-Q16C[A-Za-z0-9_.:-]*|C28[WM][0-9]{8}))')
        self.numbers=re.compile(r'(?<![A-Za-z0-9_])(?:0[xX][0-9a-fA-F]{1,64}|[0-9a-fA-F]{64}|[0-9]{1,78})(?![A-Za-z0-9_])')


def audit(mode, base, identities, *, limits=old.Limits()):
    # These are exact prospective-only directories. Never exclude a whole
    # historical context or a prior registered/failed family's evidence.
    local=('build/stage17-q16c-prep/prospective-1',)
    stand=('local-authoring-cpuprefetchv5-28/q16c-sources-1',
           'local-authoring-cpuprefetchv5-28/q16c-source-operator-1',
           'local-authoring-cpuprefetchv5-28/q16c-configuration-1')
    scope={**old.audit.__globals__,'LOCAL_EXCLUSIONS':local,'STAND_EXCLUSIONS':stand}
    scope['exclusions']=metadata._clone(old.exclusions,scope)
    result=metadata._clone(old.audit,scope)(mode,Path(base),Matcher(identities),limits)
    result.update(schema_version='cpu-prefetch-stage17-q16c-namespace-audit/1',planned_phase_identities=360,
        planned_linked_order_identities=72,planned_source_identities=360,planned_numeric_seeds=792,
        source_setup_sha256=old.sha(old.canonical(identities['source_setup'])),plan_sha256=None,
        phase18_authority=False)
    return result
