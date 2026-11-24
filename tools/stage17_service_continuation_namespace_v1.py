"""D260 finite public-history audit with one exact prospective-seed exception.

Fresh textual identities must have no historical match. Numeric seeds may occur
only inside the exact authenticated120-entry parent declaration or its exact
complete prospective identity registries. Matching an executed capture, a bare
seed, a partial registry or a modified parent remains a collision. Never enter
raw payload trees. This grants no namespace registration or experiment authority.
"""
import hashlib
import json
import re
import types

import stage17_public_namespace_audit_v1 as base
import stage17_formal_service_continuation_v2 as contract
import stage17_archive_metadata_fast_v1 as metadata

SCHEMA = 'cpu-prefetch-stage17-d260-planned-identities/1'


def planned_identities(plan):
    contract.validate_plan(plan)
    phases = [item['capture'][phase] for item in plan['captures'] for phase in ('warmup','measurement')]
    linked = [item['capture']['linked_order'] for item in plan['captures'] if item['capture']['linked_order'] is not None]
    return dict(schema_version=SCHEMA,plan_sha256=hashlib.sha256(contract.plan_bytes(plan)).hexdigest(),
        stand_id=plan['stand_id'],phase_identities=phases,linked_order_identities=linked,
        schedule_namespaces=[],execution_authority=False)


class Matcher:
    text = base.Matcher.text

    def __init__(self, plan, parent_bytes):
        contract.validate_parent(plan,parent_bytes)
        self.plan=plan
        parent=base.parse(parent_bytes)
        self.document=planned_identities(plan)
        phase=self.document['phase_identities'];linked=self.document['linked_order_identities']
        rows=phase+linked
        base.require(len(phase)==206 and len(linked)==48,'exact103 phase and48 linked identities required')
        for key in ('seed_id','seed_hex'):
            base.require(len({r[key] for r in rows})==len(rows),'unique phase and linked '+key)
        base.require(len({r['run_id'] for r in phase})==206,'unique phase run IDs required')
        self.namespaces={r['namespace_id'] for r in rows}
        base.require(len(self.namespaces)==3,'two phase and one node-order namespaces required')
        self.wanted={r[k] for r in phase for k in ('run_id','seed_id','namespace_id')}
        self.wanted.update(r[k] for r in linked for k in ('seed_id','namespace_id'))
        self.numeric={int(r['seed_hex'],16):r['seed_hex'] for r in rows}
        prefixes={r['run_id'][:-8] for r in phase};seed_prefixes={r['seed_id'][:-4] for r in rows}
        self.identity_namespace={r['seed_id']:r['namespace_id'] for r in rows}
        self.identity_namespace.update({r['run_id']:r['namespace_id'] for r in phase})
        self.tokens=re.compile('(?=('+'|'.join([re.escape(n)+r'(?:-SEED-[0-9]{4})?' for n in sorted(self.namespaces)]
            +[re.escape(p)+r'[0-9]{8}' for p in sorted(prefixes)]
            +[re.escape(p)+r'[0-9]{4}' for p in sorted(seed_prefixes)])+'))')
        self.numbers=re.compile(r'(?<![A-Za-z0-9_])(?:0[xX][0-9a-fA-F]{1,64}|[0-9a-fA-F]{64}|[0-9]{1,78})(?![A-Za-z0-9_])')
        original=base.planned_identities(parent,parent_bytes)
        ordinary=dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1',
            plan_sha256=contract.PARENT_SHA256,stand_id=parent['stand_id'],
            phase_identities=original['phase_identities'],schedule_namespaces=[],execution_authority=False)
        # A lookup authenticates the whole prospective object, never a filename,
        # caller-supplied exclusion, boolean "unused" claim or loose seed value.
        self.prospective={hashlib.sha256(base.canonical(v)).hexdigest() for v in (parent,original,ordinary)}
        self.authorized_documents={}

    def inspect(self, raw, lines=False, limits=base.Limits()):
        records=[line for line in raw.decode('utf-8',errors='strict').splitlines() if line.strip()] if lines else [raw.decode('utf-8',errors='strict')]
        base.require(bool(records),'empty JSONL')
        found=set();plans=set();nodes=0;permitted=set()
        for record in records:
            pending=[(base.parse(record),0,False)]
            while pending:
                value,depth,allowed=pending.pop();nodes+=1
                base.require(nodes<=limits.max_json_nodes and depth<=limits.max_depth,'JSON node/depth bound')
                if isinstance(value,dict):
                    # Hash only small candidate shapes, not every nested mapping.
                    if value.get('schema_version') in ('cpu-prefetch-stage17-formal-service-plan/3',base.REGISTRY_SCHEMA,'cpu-prefetch-stage17-formal-namespace-registration/1'):
                        digest=hashlib.sha256(base.canonical(value)).hexdigest()
                        if digest in self.prospective:
                            allowed=True;permitted.add(digest)
                    if value.get('action_id') in ('Q16a','Q16b','Q17') and isinstance(value.get('captures'),list) and str(value.get('schema_version','')).startswith('cpu-prefetch-stage17-formal-'):
                        plans.add(hashlib.sha256(base.canonical(value)).hexdigest())
                    pending.extend((v,depth+1,allowed) for v in value.values())
                    pending.extend((k,depth+1,allowed) for k in value)
                elif isinstance(value,list):
                    pending.extend((v,depth+1,allowed) for v in value)
                elif isinstance(value,str):
                    matches=self.text(value)
                    # Serialized copies of the exact old prospective object are
                    # handled as strictly as object-valued copies.
                    if not allowed and value.lstrip().startswith('{'):
                        try:
                            embedded=base.parse(value);digest=hashlib.sha256(base.canonical(embedded)).hexdigest()
                            if digest in self.prospective:allowed=True;permitted.add(digest)
                        except (ValueError,RecursionError):pass
                    found.update(m for m in matches if not (allowed and m.startswith('numeric_seed:')))
                elif type(value) is int and value in self.numeric and not allowed:
                    found.add('numeric_seed:'+self.numeric[value])
        if permitted:self.authorized_documents[hashlib.sha256(raw).hexdigest()]=sorted(permitted)
        return sorted(found),sorted(plans)


def audit(mode, base_path, matcher, limits=base.Limits()):
    # Original traversal, permissions, byte/inode/symlink, deadline and raw-tree
    # gates run in a private scope with the fifth original family included.
    scope={**vars(base),'FAMILIES':(*base.FAMILIES,contract.PARENT_SHA256),
        'STAND_EXCLUSIONS':('local-authoring-cpuprefetchv5-27/d260-collection-preparation-1',),
        'LOCAL_EXCLUSIONS':('build/stage17-d260-release',),
        'PREPARATION_PREFIXES':(*base.PREPARATION_PREFIXES,'d260-collection-preparation')}
    for name,function in vars(base).items():
        if isinstance(function,types.FunctionType) and function.__module__==base.__name__:
            scope[name]=metadata._clone(function,scope)
    result=scope['audit'](mode,base_path,matcher,limits)
    result.update(schema_version='cpu-prefetch-stage17-d260-namespace-audit/1',
        plan_sha256=matcher.document['plan_sha256'],planned_phase_identities=206,
        planned_linked_order_identities=48,planned_numeric_seeds=254,
        seed_reuse_policy=contract.SEED_POLICY,original_plan_sha256=contract.PARENT_SHA256,
        authorized_prospective_seed_reuse=[dict(path=row['path'],sha256=row['sha256'],objects=matcher.authorized_documents[row['sha256']])
            for row in result['checked_inventory'] if row['sha256'] in matcher.authorized_documents])
    return result
