"""Read-only D240 composition operator for the completed E25 suffix."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import sys

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
CONFIG_SHA='5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93'
SOURCE_FILES={
    'stage17_q16a_composite_v1.py':'e73804f858ef0ee2d276e2c963d7b9c4e9de8e82cdc079f13637a5428849ce2d',
    'stage17_q16a_suffix_admission_v1.py':'6e2d143571d083e2429e4aee7240aeadf3b11ef334d8f324e10b6cb188ed5e2c',
    'finalize_stage17_q16a_suffix_v1.py':'2efbac4f4b7e320db1c0694822fadaf41ffa3424cda5bd9f671b417a946c2d95',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args()
    if os.getuid()!=1000 or os.geteuid()!=1000:raise ValueError('owner-only offline operator')
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
    original=E/'offline-suffix-operators-1'
    if hashlib.sha256((original/'validate_suffix.py').read_bytes()).hexdigest()!='b1feb13f9cbcfa9ec6c41d11662c64f1b8f11d591f311f75a2d166f6fe94be23':
        raise ValueError('original offline operator source differs')
    sys.path.insert(0,str(original));import validate_suffix as v
    c=v.config(E/'offline-suffix-preparation-1/inputs/analysis-config.json',CONFIG_SHA)
    root=v.base.safe(args.output_root)
    phase=Path(v.parse(v.read(c['files']['REQUEST']))['evidence_root_binding']['absolute_path'])
    v.require(not root.exists(),'fresh composition output required')
    v.require(not root.is_relative_to(phase.parent.parent) and not root.is_relative_to(Path(c['repository_root'])),'composition/raw repository overlap')
    root.mkdir(mode=0o700)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    v.save(root/'intent.json',dict(status='READ_ONLY_COMPOSITION_STARTED',started_at_utc=started,
        configuration_sha256=CONFIG_SHA,raw_redecode_performed=False,raw_mutation=False,execution_authority=False),65536)
    try:
        m,pinned=v.modules(c);prepared=v.prepare(c,m)
        v.lifecycle(c,m,prepared,pinned)
        v.save(root/'signed-collection-preparation.json',dict(status='PASS',configuration_sha256=CONFIG_SHA,
            completion=c['files']['COMPLETION'],execution_authority=False),65536)
        library=E/'offline-suffix-finalization-operators-1'
        for name,digest in SOURCE_FILES.items():v.require(hashlib.sha256((library/name).read_bytes()).hexdigest()==digest,'reviewed producer source differs: '+name)
        sys.path.insert(0,str(library));import stage17_q16a_composite_v1 as composite
        import stage17_q16a_suffix_admission_v1 as suffix
        here=Path(__file__).resolve().parent
        manifest=v.parse((here/'manifest.json').read_bytes())
        for row in manifest['files']:
            v.require(Path(row['name']).name==row['name'],'flat operator binding')
            v.read(dict(path=str(here/row['name']),size_bytes=row['size_bytes'],sha256=row['sha256']))
        sys.path.insert(0,str(here));import stage17_q16a_geometry_v1 as geometry
        plan=prepared.request['action_inputs']['plan']
        transport=manifest['geometry_transport']
        v.require(transport['name']=='geometry-inputs/transport.json','fixed geometry transport locator')
        transport_binding=dict(path=str(here/transport['name']),size_bytes=transport['size_bytes'],sha256=transport['sha256'])
        v.read(transport_binding)
        geom=geometry.verify(prepared=prepared,suffix_plan=plan,
            transport_binding=transport_binding,
            platform_binding=v.base.binding(E/'ext004-authoring-records-1/platform-manifest.json'),reader=suffix.EvidenceReader())
        geometry_binding=v.save(root/'native-geometry-verification.json',geom,1024**2)
        print('GEOMETRY_VERIFIED',flush=True)
        packet=composite.evaluate_authenticated(prepared=prepared,
            configuration_binding=v.base.binding(E/'offline-suffix-preparation-1/inputs/analysis-config.json'),
            ring_geometry=geom['records'],suffix_finalization_binding=v.base.binding(E/'offline-suffix-finalization-1/finalization-result.json'))
        binding=v.save(root/'authenticated-composition.json',packet,64*1024**2)
        calibration=packet['calibration']
        v.require(len(calibration['run_sources'])==708,'all708 composition slots required')
        validity={k:sum(r['validity']==k for r in calibration['run_sources']) for k in ('VALID','INVALID','MISSING')}
        v.save(root/'complete.json',dict(status='AUTHENTICATED_COMPOSITION_COMPLETE',started_at_utc=started,
            completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),composition=binding,geometry=geometry_binding,
            geometry_provenance_verified=True,calibration_status=calibration['status'],validity_counts=validity,
            measurement_zero_loss_gate=calibration['derived_result']['measurement_zero_loss_gate'],
            warmup_zero_loss_gate=calibration['derived_result']['warmup_zero_loss_gate'],
            original_prefix_reports=177,suffix_reports=531,source_histories_preserved=True,
            raw_redecode_performed=False,raw_mutation=False,ext007_admitted=False,phase18_authority=False),65536)
        print('COMPOSITION_COMPLETE',calibration['status'],json.dumps(validity),flush=True)
    except BaseException as error:
        v.save(root/'failure.json',dict(type=type(error).__name__,message=str(error),raw_mutation=False,raw_redecode_performed=False,execution_authority=False),65536)
        raise


if __name__=='__main__':main()
