"""Approved D310 prospective design, before schedule generation or admission."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import stage17_descriptive_freeze_v1 as freeze
import stage17_formal_plan_v1 as factors
from stage17_pilot_plan_v4 import _permutation

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'cpu-prefetch-stage17-s180-pilot-blueprint/1'
METHOD = 'STAGE17-PILOT-S180-DESCRIPTIVE-v1'
SCHEMA = 'config/schemas/stage17-s180-pilot-blueprint-v1.schema.json'
ACCEPTANCE = 'docs/evidence/stage17/PILOT-D310-ACCEPTED-20261120-01/owner-acceptance.json'
LAYOUTS = 'docs/evidence/stage17/PILOT-D310-ACCEPTED-20261120-01/observed-layout-metadata.json'
FREEZE = 'docs/evidence/stage17/EXT007-D307-FREEZE-PUBLISHED-20261120-01/descriptive-calibration-freeze-1/calibration-freeze.json'
RESOLUTION = 'docs/evidence/stage17/EXT007-D309-ADMITTED-20261120-01/post-recovery/records/resolution-007-s17-ext-007.json'
ADMISSION = 'docs/evidence/stage17/EXT007-D309-ADMITTED-20261120-01/post-recovery/d309-ext007-final-replay-1/complete.json'
PINS = {ACCEPTANCE:'3673f215a10cac54577acb5fa85b5adabc4262eb63bcf260c6ec15143e822ab7',
        ADMISSION:'119f1c7978ec75a30fdab16acd1be267355784c40cf7e248b1976e0fba6bfdd2',
        LAYOUTS:'572b80a67814af71f1a87365e195238609493ea1e682e68e29e638e374678391',
        FREEZE:'cdf85bf585c997e079f432f904d93849fa5f69757440c7cefcf61ca7e06d742c',
        RESOLUTION:'fd4a2b1a1c0c9cf0ab6ecf47fa838de81e67746c67caebad8b15779f4c70f104'}
BLOCKERS = ['CURRENT_STAND_GEOMETRY_AND_QUALIFICATION_ADMISSION',
    'PROSPECTIVE_NAMESPACE_AUDIT_AND_RESERVATION','EXACT_SCHEDULE_SOURCE_GENERATION_AND_PROVENANCE',
    'PERSISTENT_PILOT_RUNTIME_AND_COMPLETE_WARMUP_RETENTION',
    'NATIVE_RESOURCE_AND_ARCHIVE_CUSTODY_PROOF','WHOLE_PLOT_RECOVERY_ENVELOPE',
    'COMPLETE_MEASURED_TIME_ESTIMATE','SCOPED_EXT008_EXT009_ADMISSION',
    'FINITE_EXT010_REQUEST_SIGNATURE_AND_AUTHORIZATION']


def require(value,message):
    if not value: raise ValueError('S180 blueprint: '+message)


def binding(path,raw):
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def original(relative):
    path = ROOT/relative
    require(not path.is_symlink() and path.stat().st_size < 2*1024**2,'regular bounded source')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PINS[relative],'exact approved source '+relative)
    # Public repository evidence is installed under a different absolute root
    # on the stand. Retained historical stand locators inside it stay unchanged.
    return json.loads(raw),binding(Path(relative),raw)


def build(*,blueprint_id,master_seed_hex):
    require(isinstance(blueprint_id,str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}',blueprint_id),
            'explicit canonical prospective identity')
    require(isinstance(master_seed_hex,str) and re.fullmatch('[0-9a-f]{64}',master_seed_hex),'explicit prospective master seed')
    approval,approved = original(ACCEPTANCE)
    require(approval['selected_profile'] == 'S180' and approval['measurement_captures'] == 180 and
            approval['repetitions_per_setting'] == 1 and approval['stand_only_lossless_pilot_storage_approved'] is True,
            'actual S180 and storage approval')
    proposal = ROOT/approval['proposal']['path']; raw = proposal.read_bytes()
    require(len(raw) == approval['proposal']['size_bytes'] and hashlib.sha256(raw).hexdigest() == approval['proposal']['sha256'],
            'exact approved proposal bytes')
    # Consume the already admitted exact public snapshot. Its original source
    # locators are on the stand; reopening them here would repeat preparation
    # and make a metadata-only local blueprint depend on remote filesystem paths.
    value,frozen = original(FREEZE)
    admitted,admission = original(ADMISSION)
    resolution,resolved = original(RESOLUTION)
    require(resolution['input_id'] == 'S17-EXT-007' and value['scope'] == freeze.SCOPE,'actual descriptive predecessor')
    require(admitted['status'] == 'SCOPED_EXT007_OPERATIONALLY_ADMITTED' and
            admitted['calibration_scope'] == freeze.SCOPE and
            admitted['freeze']['sha256'] == frozen['sha256'] and
            admitted['resolution']['sha256'] == resolved['sha256'] and
            admitted['pilot_ready'] is False,'actual prior admitted freeze and resolution')
    layouts,observed = original(LAYOUTS)
    require(layouts['stand_id'] == value['stand_id'] and layouts['original_capture_count'] == 180,
            'original geometry declaration stand and population')
    contexts = value['outputs']['q16a']['derived_result']['contexts']
    distances = {(c['placement'],c['working_set_class']):c['distance'] for c in contexts}
    require(len(distances) == 6,'six accepted distance contexts')
    namespace = blueprint_id+'/PILOT'
    hardware = ['H0','H1']
    order = [hardware[i] for i in _permutation(2,master_seed_hex,namespace+'/repetition-0/hardware-order')]
    rows,execution = [],{}
    for block,state in enumerate(order):
        cells = sorted(c for c in factors.cells('Q16c') if c[1] == state)
        for i,position in enumerate(_permutation(90,master_seed_hex,namespace+'/repetition-0/'+state+'/cell-order')):
            execution[cells[position][0]] = block*90+i
    for cell,state,package,placement,working,load in sorted(factors.cells('Q16c')):
        key = placement+'/'+working
        geometry = layouts['layouts'][key]['geometry']
        # These are source-declared/requested values, not new verified hardware observations.
        require(geometry['capacity'] >= 8 and geometry['producer_cpu'] != geometry['consumer_cpu'],'source geometry')
        distance = distances[placement,working]
        run = blueprint_id+':C'+str(cell).zfill(3)+':R000'
        arena = namespace+'/ARENA/'+key
        schedule = namespace+'/SCHEDULE/'+key+'/'+load
        rate = {'L025':(1670571,4),'L050':(1670571,2),'L075':(5011713,4)}[load]
        rows.append(dict(cell_ordinal=cell,repetition_ordinal=0,execution_ordinal=execution[cell],
            temporal_block_ordinal=0,hardware_whole_plot_ordinal=execution[cell]//90,
            package=package,requested_hardware_state=state,verified_hardware_state=None,
            placement=placement,working_set_class=working,load_level=load,
            run_id=run,warmup_run_id=run+':WARMUP',warmup_regime='PRE_FREEZE_BOOTSTRAP',
            warmup_ns=5_000_000_000,measurement_ns=1_000_000_000,
            arena_namespace=arena,node_order_namespace=namespace+'/NODE_ORDER/'+key,
            warmup_schedule_namespace=schedule+'/WARMUP',measurement_schedule_namespace=schedule+'/MEASUREMENT',
            requested_geometry=geometry,distance=distance,
            nominal_rate=dict(numerator=rate[0],denominator=rate[1],unit='EVENTS_PER_SECOND')))
    document = dict(schema_version=VERSION,blueprint_id=blueprint_id,protocol_version='2.0.0-pre.3',
        method_id=METHOD,selected_profile='S180',stand_id=value['stand_id'],master_seed_hex=master_seed_hex,
        approval=approved,calibration_freeze=frozen,calibration_admission=admission,
        ext007_resolution=resolved,observed_geometry_metadata=observed,
        source_geometry_plan=layouts['source_plan'],geometry_evidence_status='SOURCE_DECLARATION_PENDING_CURRENT_ADMISSION',
        requested_whole_plot_order=order,repetitions_per_setting=1,settings=180,captures=rows,
        physical_schedule_sources_generated=False,namespace_reservation_verified=False,
        storage=dict(policy_id='D310-S180-LOSSLESS-STAND-PRIMARY-v1',independent_raw_backup=False,
                     archive_quota_bytes=6_000_000_000_000,workspace_bytes=512*1024**3,
                     analysis_scratch_bytes=256*1024**3,reserve_bytes=16*1024**3),
        operational_cap_ns=86_400_000_000_000,operational_window_started=False,
        repeated_temporal_block_covariance_claim=False,legacy_statistical_freeze_satisfied=False,
        final_matrix_feasibility='NOT_EVALUATED',final_scale_selection=None,
        launch_ready=False,execution_authority=False,phase18_authority=False,blockers=BLOCKERS)
    from jsonschema import Draft202012Validator
    Draft202012Validator(json.loads((ROOT/SCHEMA).read_bytes())).validate(document)
    return document


def verify(document):
    require(type(document) is dict,'document object')
    expected = build(blueprint_id=document.get('blueprint_id'),master_seed_hex=document.get('master_seed_hex'))
    require(freeze.canonical(document) == freeze.canonical(expected),'complete prospective design, source, or authority drift')
    return document


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blueprint-id',required=True); p.add_argument('--master-seed-hex',required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args(); value = build(blueprint_id=a.blueprint_id,master_seed_hex=a.master_seed_hex)
    with a.output.open('xb') as f:f.write(freeze.canonical(value))


if __name__ == '__main__': main()
