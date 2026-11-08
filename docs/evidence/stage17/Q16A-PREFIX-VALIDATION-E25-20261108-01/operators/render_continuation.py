"""Author D240 E25 inputs only. No signing, registration, collection or retries.

Run on the host containing the original evidence/program and both bundles.
All final inputs must exist; no synthetic/preview switch is offered by the CLI.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import sys

SPEC_VERSION = 'software-q16a-continuation-authoring/1'
E25 = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
PLAN_ID = 'CPU-PREFETCH-V5-V25-Q16A-PLAN-1'
NAMESPACES = {phase: 'CPU-PREFETCH-V5-V25-Q16A-'+phase.upper()+'-1'
              for phase in ('warmup', 'measurement')}
PROFILE_MEMBER = 'config/stage17/formal-archive-implementation-profile-v1.json'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def data_binding(path, raw):
    return dict(path=str(path), size_bytes=len(raw), sha256=digest(raw))


def existing_binding(path, a, *, maximum=32*1024**2):
    """Hash actual regular bytes once, verify descriptor/path identity; no retries."""
    p=Path(str(a.contract._path(str(path))))
    a.require(p.resolve(strict=True)==p, 'input path contains symlink')
    fd=os.open(p,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        a.require(stat.S_ISREG(before.st_mode) and before.st_size<=maximum, 'input file bound')
        h=hashlib.sha256();count=0
        while count<before.st_size:
            block=os.read(fd,min(1024**2,before.st_size-count))
            a.require(bool(block),'truncated input')
            count+=len(block);h.update(block)
        a.require(not os.read(fd,1) and a._stamp(before)==a._stamp(os.fstat(fd))==a._stamp(p.lstat()),
                  'input changed while hashing')
    finally:
        os.close(fd)
    return dict(path=str(p),size_bytes=count,sha256=h.hexdigest())


def qualify(spec, root, a, controller):
    """Live read-only qualification; no author-request/signature/worker invocation."""
    q=a.fields(spec['qualification'], 'evidence_root journal journal_directory pilot_archive pilot_sidecar', 'qualification inputs')
    for field in ('pilot_archive','pilot_sidecar'):
        a.same(existing_binding(q[field]['path'],a,maximum=128*1024**2),q[field],field)
    controller.activate()
    validation=controller.previous.journal_runtime.validate_operational_journal(
        repository_root=root,evidence_root=Path(q['evidence_root']),latest_journal=Path(q['journal']),
        journal_directory=Path(q['journal_directory']),pilot_archive=Path(q['pilot_archive']['path']),
        pilot_sidecar=Path(q['pilot_sidecar']['path']),as_of_utc=controller.support._now(),
        allow_synthetic_test_evidence=False)
    registry=importlib.import_module('stage17_output_registry_v12').pin_registry(root)
    action=registry.action('Q16a')
    a.same(validation.current_state,action['required_state'],'current qualification state')
    a.require(all(k in validation.resolutions for k in action['required_resolution_ids']), 'six qualified dependencies required')
    controller.runtime_from_context(validation)
    return validation


def compatibility(spec, context, a, reader):
    """Construct exact exhaustive source comparisons; admission checks their meaning."""
    doc=dict(schema_version=a.COMPATIBILITY_SCHEMA,measured_sources=[],cold_source_changes=[],
             monitor_path_replacements=copy.deepcopy(spec['monitor_path_replacements']),execution_authority=False)
    indices={}
    for side,root,revision in (
            ('original',spec['original_bundle_root'],a.contract.PARENT_SOURCE),
            ('continuation',context['archive_bundle_root'],context['source_revision'])):
        root=Path(str(a.contract._path(root)))
        d=dict(source_revision=revision,bundle_root=str(root))
        for key,member in (('worker','release/bin/cpu_prefetch_runner'),
                           ('formal_codegen','build-provenance/formal_codegen_report.json'),
                           ('bundle_inventory','BUNDLE_INVENTORY.json')):
            d[key]=existing_binding(root/member,a)
        indices[side]=a._inventory(reader.document(d['bundle_inventory']))
        doc[side]=d
    names=a._source_names(indices['original'])
    a.same(sorted(names),sorted(a._source_names(indices['continuation'])),'bundled measurement closure')
    for name in sorted(names):
        row=dict(relative_path=name)
        for side in ('original','continuation'):
            row[side]=dict(indices[side][name],path=a._member(doc[side]['bundle_root'],name))
        doc['cold_source_changes' if name==a.COLD_SOURCE else 'measured_sources'].append(row)
    return doc


def assemble(parent, spec, revision, profile_sha, compat_binding, a):
    """Pure transformation, also exercised against exact original plan bytes."""
    c=a.contract
    a.require(len(spec['monitor_path_replacements'])==5, 'all five explicit monitor replacements required')
    replacements=c._path_replacements(spec['monitor_path_replacements'])
    p=copy.deepcopy(parent)
    p.update(schema_version=c.VERSION,plan_id=PLAN_ID,source_revision=revision,
             warmup_namespace=NAMESPACES['warmup'],measurement_namespace=NAMESPACES['measurement'])
    p['storage']['implementation_profile_sha256']=profile_sha
    p['captures']=p['captures'][c.FIRST_ORDINAL:]
    for ordinal,item in enumerate(p['captures']):
        original_ordinal=c.FIRST_ORDINAL+ordinal
        for section in ('capture','resources','monitoring'):
            item[section]['ordinal']=ordinal
        for phase,letter in (('warmup','W'),('measurement','M')):
            identity=item['capture'][phase]
            identity.update(run_id=f'F25{letter}{original_ordinal:08d}',
                            seed_id=NAMESPACES[phase]+f'-SEED-{original_ordinal:04d}',
                            namespace_id=NAMESPACES[phase])
        item['capture']['arena_seed']=copy.deepcopy(item['capture']['measurement'])
        for source in item['monitoring']['environment_sources']:
            source['path']=replacements.get(source['path'],source['path'])
    p['continuation']=dict(policy_id=c.POLICY,parent_plan=copy.deepcopy(spec['parent_plan']),
        failed_family_receipt=copy.deepcopy(spec['failed_family_receipt']),
        accepted_prefix_manifest=copy.deepcopy(spec['accepted_prefix_manifest']),compatibility_manifest=compat_binding,
        reused_contexts=[0,1,2],remaining_contexts=list(range(3,12)),original_first_ordinal=177,
        failed_original_ordinal=177,seed_policy=c.SEED_POLICY,
        monitor_path_replacements=copy.deepcopy(spec['monitor_path_replacements']),future_retries=0)
    return p


def exclusive_outputs(destination, documents, a):
    """No existing output replacement. A write failure leaves its partial evidence."""
    a.require(not destination.exists() and destination.parent.resolve(strict=True)==destination.parent,
              'fresh output directory under an existing nonsymlink parent required')
    destination.mkdir(mode=0o700)
    result={}
    for name,raw in documents.items():
        p=destination/name
        with p.open('xb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        result[name]=data_binding(p,raw)
    fd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return result


def render(spec, root, a, controller):
    a.fields(spec,'schema_version qualification parent_plan failed_family_receipt accepted_prefix_manifest original_bundle_root continuation_bundle_root monitor_path_replacements output_directory','authoring specification')
    a.same(spec['schema_version'],SPEC_VERSION,'authoring version')
    destination=Path(str(a.contract._path(spec['output_directory'])))
    a.require(destination.parent==E25 and not destination.exists(), 'fresh E25 output required')
    a.require(Path(spec['qualification']['evidence_root'])==E25,'current E25 qualification required')
    reader=a.BoundReader()
    parent_bytes=reader.read(spec['parent_plan']);parent=a._json(parent_bytes)
    failure=reader.document(spec['failed_family_receipt'])
    prefix=reader.document(spec['accepted_prefix_manifest'])
    a.require(prefix.get('status')=='VALIDATED','actual completed prefix validation required')
    validation=qualify(spec,root,a,controller)
    context=validation.resolutions['S17-EXT-006'].semantic_context
    a.same(context['archive_bundle_root'],spec['continuation_bundle_root'],'actual supplied successor bundle')
    profile=context['archive_profile_binding']
    a.same(profile['path'],PROFILE_MEMBER,'qualified profile member')
    reader.read(dict(profile,path=str(Path(context['archive_bundle_root'])/PROFILE_MEMBER)))
    compat=compatibility(spec,context,a,reader);compat_bytes=a.canonical(compat)
    plan=assemble(parent,spec,context['source_revision'],profile['sha256'],
                  data_binding(destination/'compatibility.json',compat_bytes),a)
    a.contract.validate_parent(plan,parent_bytes)
    old_root,old_index=a._compatibility(compat,plan,context,reader)
    a._prefix(prefix,parent,failure,plan,reader,old_root,old_index)
    # Load actual qualified Python/codec closure as the controller does, without executing it.
    import time
    controller.qualified_archive_profile({'action_inputs':{'plan':plan}},validation,
        deadline_ns=time.monotonic_ns()+120*10**9)
    reader.finish()
    plan_bytes=a.canonical(plan)
    namespace=dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1',
        plan_sha256=digest(plan_bytes),stand_id=plan['stand_id'],
        phase_identities=[copy.deepcopy(item['capture'][phase]) for item in plan['captures']
                          for phase in ('warmup','measurement')],schedule_namespaces=[],execution_authority=False)
    outputs=exclusive_outputs(destination,{'compatibility.json':compat_bytes,
        'namespace_registry.json':a.canonical(namespace),'plan.json':plan_bytes},a)
    return dict(status='AUTHORED_NOT_REGISTERED',captures=531,reused_prefix=177,
                namespace_collision_audit_performed=False,execution_authority=False,outputs=outputs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository-root',type=Path,required=True)
    p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--spec-sha256',required=True)
    args=p.parse_args()
    root=args.repository_root.resolve(strict=True)
    sys.path.insert(0,str(root/'tools'))
    a=importlib.import_module('stage17_q16a_continuation_admission_v1')
    controller=importlib.import_module('stage17_phase_controller_v26')
    for module in (a,controller):
        a.require(Path(module.__file__).resolve().is_relative_to(root/'tools'),'module outside supplied repository')
    binding=existing_binding(args.spec.absolute(),a)
    a.same(binding['sha256'],args.spec_sha256,'authoring spec digest')
    reader=a.BoundReader();spec=reader.document(binding);reader.finish()
    print(json.dumps(render(spec,root,a,controller),sort_keys=True))


if __name__=='__main__':
    main()
