"""Exact completed D268 descriptive Q16b reuse; no legacy statistical relabel.

This incident-bound consumer verifies previously audited artifact identities.
Its publishing caller must independently verify signed lifecycle, custody and
current qualification. Returned original evidence retains all authority and
provenance boundary flags, FULL outcomes and both actual source populations.
"""
from fractions import Fraction
import hashlib

import stage17_q16a_continuation_admission_v1 as admission
import stage17_formal_service_continuation_v2 as contract
import stage17_formal_calibration_v1 as mathematics

SCHEMA='cpu-prefetch-stage17-q16b-composition-handoff/1'
BASIS_SCHEMA='cpu-prefetch-stage17-descriptive-service-load-basis/1'
SOURCE='07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8'
WORKER='5497678d637578843abaf5e9d708cecaebe3b26acd4f5b1da48c8fbf91835cb8'
INVENTORY='70cfe2ea2f771b9c7bc93440a8ca57713c2da65a6651516bcaf71e05374e0782'
PLATFORM='d99d043aa0dd2b77f2d64b96249a19dad03cc2706c2e00778f587c50d034d48c'
ACCEPTED={
 'completion':(2699,'e392c586ded899dec9c753a8ddfd6f29b6728c06866a0354d9979ba33b9d0151'),
 'analysis':(562,'129eb45545bb1e47b064901380cb17a4e773cce19dd1db7d266ad34b0cda9e6c'),
 'composition':(103724,'3894bf7d0d5223b50326d718815b8a7d106fe395dde2868fe3e06a271d754393'),
 'plan':(1784078,'1ccafebafafea4b8491b4daf5b70f1065d1ea2c0b854d662bae388bfb031b2ba'),
 'parent_plan':(2072840,'53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486'),
 'geometry':(785,'dd20f72656eb55f5e10a0621f6c8c5056fea3d969b293e92679b1727bf380d4b'),
}
Error=admission.AdmissionError
require,same,fields=admission.require,admission.same,admission.fields


def consume(document, *, validation, selected_duration_ns):
    """Reuse only the exact completed17+103 result on its actual qualified source."""
    try:
        fields(document,'schema_version completion analysis composition plan parent_plan geometry '
                        'execution_authority phase18_authority','Q16b handoff')
        same(document['schema_version'],SCHEMA,'handoff schema')
        for flag in ('execution_authority','phase18_authority'):same(document[flag],False,'handoff authority')
        reader=admission.BoundReader();evidence={}
        for name,(size,digest) in ACCEPTED.items():
            bound=document[name];same([bound['size_bytes'],bound['sha256']],[size,digest],'audited D268 '+name)
            evidence[name]=reader.document(bound)
        completion,analysis,result,plan,parent,geometry=(evidence[k] for k in ACCEPTED)
        current=validation.resolutions['S17-EXT-006'].semantic_context
        platform=validation.resolutions['S17-EXT-004'].semantic_context
        for key,value in dict(source_revision=SOURCE,inventory_sha256=INVENTORY,release_artifact_sha256=WORKER).items():
            same(current[key],value,'actual qualified '+key)
        same(platform['pilot_platform_measurements']['platform_manifest_sha256'],PLATFORM,'actual qualified platform')
        same(platform['stand_id'],plan['stand_id'],'qualified stand')
        same(current['release_artifact_path'],current['archive_bundle_root']+'/release/bin/cpu_prefetch_runner','qualified worker location')
        same(plan['source_revision'],SOURCE,'actual completed source')
        same(result['stand_id'],plan['stand_id'],'actual result stand')
        same(completion['source_revision'],SOURCE,'completed source')
        same(completion['success'],True,'actual successful producer')
        same(completion['errors'],[],'no producer errors')
        same([completion['retained_captures'],completion['new_captures']],[17,103],'actual source counts')
        same(completion['analysis_complete']['sha256'],ACCEPTED['analysis'][1],'producer analysis binding')
        require(completion['completed_monotonic_ns']<completion['global_deadline_ns'],'original global deadline')
        for phase in completion['phases']:
            same([phase['exit_code'],phase['leader_reaped']],[0,True],'owned phase completion')
        same(completion['partition_restoration']['verified'],True,'actual restoration')
        same(analysis['status'],'ALL_103_ANALYZED','complete independent raw validation')
        same(analysis['all_raw_reconstructed_and_hash_checked'],True,'actual raw inverse')
        same([analysis['report']['size_bytes'],analysis['report']['sha256']],list(ACCEPTED['composition']),'completed report binding')
        same([analysis['captures'],analysis['retained_prefix_captures'],analysis['combined_capture_count']],[103,17,120],'analysis source counts')
        contract.validate_parent(plan,reader.read(document['parent_plan']))
        same(result['schema_version'],'cpu-prefetch-stage17-formal-service-continuation-descriptive/1','actual descriptive schema')
        same(result['method_id'],contract.METHOD,'actual descriptive method')
        same(result['status'],'DESCRIPTIVE','no legacy inferential relabel')
        same(result['tolerance_guarantee'],False,'no59-run tolerance guarantee')
        same(result['prospective'],dict(repetitions=2,measurement_ns=selected_duration_ns),'exact prospective calibration')
        require(type(selected_duration_ns) is int and selected_duration_ns==1_000_000_000,'accepted duration')
        expected=[dict(population_id='RETAINED_PREFIX',source_revision=contract.PARENT_SOURCE,
                       plan_sha256=ACCEPTED['parent_plan'][1],planned_captures=17,original_first_ordinal=0),
                  dict(population_id='CONTINUATION',source_revision=SOURCE,
                       plan_sha256=ACCEPTED['plan'][1],planned_captures=103,original_first_ordinal=17)]
        same(result['source_populations'],expected,'both original histories')
        same(geometry['source_revision'],SOURCE,'qualified native geometry source')
        same([geometry['schema_version'],geometry['api'],geometry['source_dirty'],geometry['hardware_observation'],geometry['execution_authority']],
             ['software-native-ring-slot-geometry/1','RingSpscQueue::storage_requirements',False,False,False],'native geometry query identity')
        require(len(geometry['records'])==6,'all six actual native contexts')
        require(len(result['run_sources'])==120,'all120 reports required')
        groups={};identities=set()
        for ordinal,row in enumerate(result['run_sources']):
            local=ordinal if ordinal<17 else ordinal-17
            capture=(parent['captures'][ordinal] if ordinal<17 else plan['captures'][local])['capture']
            same([row['original_capture_ordinal'],row['capture_ordinal'],row['source_population']],
                 [ordinal,local,'RETAINED_PREFIX' if ordinal<17 else 'CONTINUATION'],'original and local ordinals')
            same(row['validity'],'VALID','actual raw report validity')
            for phase in ('warmup','measurement'):
                value=row[phase+'_run_id'];same(value,capture[phase]['run_id'],'actual source run identity')
                require(value not in identities,'unique original run identity');identities.add(value)
            mathematics._check_summary('Q16b',row['summary'],result['prospective'])
            cell=capture['cell_ordinal'];groups.setdefault(cell,[]).append(mathematics._fraction(row['summary']['throughput']))
            context=(0 if capture['placement']=='NEAR' else 3)+contract.native.WORKING_SETS.index(capture['working_set_class'])
            record=geometry['records'][context]
            same(record['context_ordinal'],context,'actual geometry context order')
            for key in ('capacity','cache_line_bytes'):same(capture['geometry'][key],record[key],'actual native '+key)
        require(len(groups)==60 and all(len(rows)==2 for rows in groups.values()),'complete two-repetition matrix')
        require(len(result['derived_result']['cells'])==60,'all cell minima')
        for cell in result['derived_result']['cells']:
            same([cell['valid_runs'],cell['missing_runs'],cell['invalid_runs']],[2,0,0],'complete cell')
            same(cell['min_mu_cell'],mathematics._rational(min(groups[cell['cell_ordinal']])),'independent exact cell minimum')
        same(result['derived_result']['min_mu_ref'],mathematics._rational(min(min(v) for v in groups.values())),'exact global minimum')
        for name,index in (('measurement_zero_loss_gate',1),('warmup_zero_loss_gate',0)):
            same(result['derived_result'][name],mathematics._gate(result['run_sources'],index),'retained separate '+name)
        for flag in ('report_provenance_authenticated','independent_runs_authenticated','family_validity_established','execution_authority','phase18_authority'):
            same(result[flag],False,'original mathematical boundary '+flag)
        reader.finish();return result
    except Error:raise
    except (OSError,KeyError,TypeError,ValueError,OverflowError) as error:
        raise Error('Q16b handoff rejected: '+str(error)) from error


def load_basis(result):
    """Exact descriptive planning rates, explicitly without execution authority."""
    require(hashlib.sha256(mathematics.canonical(result)).hexdigest()==ACCEPTED['composition'][1],
            'exact audited composition required for planning rates')
    same(result['schema_version'],'cpu-prefetch-stage17-formal-service-continuation-descriptive/1','descriptive result')
    same(result['status'],'DESCRIPTIVE','descriptive status')
    same(result['method_id'],contract.METHOD,'descriptive method')
    same(result['tolerance_guarantee'],False,'no statistical guarantee')
    mu=mathematics._fraction(result['derived_result']['min_mu_ref'])
    require(mu>0,'genuine zero retained; positive offered rates cannot be selected')
    return dict(schema_version=BASIS_SCHEMA,source_method_id=result['method_id'],
        source_composition_sha256=ACCEPTED['composition'][1],stand_id=result['stand_id'],
        mu_ref_observed_min=mathematics._rational(mu),
        base_rates={name:mathematics._rational(mu*factor) for name,factor in
                    (('L025',Fraction(1,4)),('L050',Fraction(1,2)),('L075',Fraction(3,4)))},
        rate_unit='EVENTS_PER_SECOND',evidence_strength='DESCRIPTIVE_OBSERVED_MINIMUM',
        confidence_claim=None,execution_authority=False,phase18_authority=False)
