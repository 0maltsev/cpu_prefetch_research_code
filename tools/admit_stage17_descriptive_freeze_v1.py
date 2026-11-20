"""D307 admit the exact signed descriptive data freeze; never execute a pilot."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import signal

import stage17_state_journal_v61 as journal
import stage17_semantic_verifier_v64 as semantic
import stage17_operational_semantics_v18 as scoped
import stage17_operational_cli_v11 as original_cli
import stage17_phase_controller_daycap_v1 as cloning
from prepare_stage17_descriptive_freeze_v1 import E,load_io


def utc(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository-root',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    a = p.parse_args()
    scoped.require(os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups(), 'actual evidence owner')
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2); os.sched_setaffinity(0,{3}); signal.alarm(900)
    io,c = load_io(); root = a.repository_root
    scoped.require(root == Path(c['repository_root']) and a.output_root.parent == E and not a.output_root.exists(), 'exact administrative scope')
    a.output_root.mkdir(mode=0o700)
    try:
        # The private CLI view retains the ordinary append/candidate-validation
        # implementation while selecting the separately versioned journal.
        cli = cloning._clone_module(original_cli,dict(journal_runtime=journal))
        arguments = dict(repository_root=root,evidence_root=E,pilot_archive=Path(c['archive']['path']),pilot_sidecar=Path(c['sidecar']['path']))
        before = cli.validate_journal(**arguments)
        scoped.require(len(before.resolutions) == 6 and len(before.transitions) == 3, 'exact six-input baseline')
        previous_path = cli.latest_journal(E); initial,initial_raw = cli.load_json(previous_path)
        policy = io.document(io.binding(root/semantic.POLICY_PATH))
        pinned = {}
        for group in ('bindings','runtime_closure'):
            for key,b in policy[group].items():
                _,raw = semantic.pinned_binding_bytes(root,b,group+' '+key); pinned[b['path']] = raw
        original_binding = io.binding(root/'tools/admit_stage17_descriptive_freeze_v1.py')
        scoped.require(original_binding == io.binding(Path(__file__).resolve()), 'actual source-bound admission entry')
        data = E/'descriptive-calibration-freeze-1'; record = io.binding(data/'calibration-freeze.json')
        signature = io.binding(data/'calibration-freeze.json.sig')
        predecessors = scoped.reader._resolution_bindings(before.resolutions,tuple(f'S17-EXT-{i:03d}' for i in range(1,7)))
        schema = io.binding(root/scoped.freeze.SCHEMA_PATH); schema['path'] = scoped.freeze.SCHEMA_PATH
        manifest = dict(schema_version='cpu-prefetch-stage17-operational-input-manifest/5',
            manifest_id='CPU-PREFETCH-V5-D307-DESCRIPTIVE-EXT007-1',input_id='S17-EXT-007',
            stand_id=io.document(record)['stand_id'],predecessor_resolutions=predecessors,
            synthetic_test_only=False,phase18_authority=False,artifacts=[
                dict(artifact_id='D307-DESCRIPTIVE-CALIBRATION-FREEZE-1',role='CALIBRATION_FREEZE',media_type='application/json',
                    locator='calibration-freeze.json',size_bytes=record['size_bytes'],sha256=record['sha256'],
                    schema_identity=scoped.freeze.SCHEMA,schema_binding=schema,lineage=[]),
                dict(artifact_id='D307-DESCRIPTIVE-CALIBRATION-SIGNATURE-1',role=scoped.SIGNATURE_ROLE,media_type='application/sshsig',
                    locator='calibration-freeze.json.sig',size_bytes=signature['size_bytes'],sha256=signature['sha256'],
                    schema_identity=None,schema_binding=None,lineage=[dict(id='D307-DESCRIPTIVE-CALIBRATION-FREEZE-1',sha256=record['sha256'])])])
        manifest_binding = io.save(data/'ext007-manifest-v5.json',manifest)
        checked = scoped.verify_manifest_v18(repository_root=root,manifest_path=Path(manifest_binding['path']),
            admitted_resolutions=before.resolutions,expected_input_id='S17-EXT-007',allow_synthetic=False,pinned_repository_bytes=pinned)
        scoped.require(checked['calibration_scope'] == scoped.freeze.SCOPE and checked['data_provenance_accepted'] is True,
                       'actual standalone scoped admission')
        # Reuse the domain actually recorded by the admitted current release;
        # do not invent a new physical custody domain or second-copy claim.
        prior_receipts = [r for r in before.resolutions['S17-EXT-006'].document['evidence'] if r['kind'] == 'EXTERNAL_CUSTODY_RECEIPT']
        scoped.require(len(prior_receipts) == 1,'actual admitted release custody domain')
        domain = io.document(io.binding(E/prior_receipts[0]['receipt_path']))['custody_domain_id']
        receipt = dict(schema_version='cpu-prefetch-stage17-external-custody-receipt/2',
            receipt_id='S17-EXT-007-D307-DESCRIPTIVE-CUSTODY-1',artifact_locator=manifest_binding['path'],
            artifact_size_bytes=manifest_binding['size_bytes'],artifact_sha256=manifest_binding['sha256'],
            sidecars=[dict(locator=b['path'],size_bytes=b['size_bytes'],sha256=b['sha256']) for b in
                      (record,signature,io.binding(data/'provenance.json'))],custody_domain_id=domain,
            verifier_id='STAGE17-OPERATIONAL-MANIFEST-VERIFIER',verifier_version='5',verification_result='PASS',verified_at_utc=utc(),
            contract=dict(locator=str(Path(manifest_binding['path']).relative_to(E)),size_bytes=manifest_binding['size_bytes'],
                          sha256=manifest_binding['sha256'],scope='OPERATIONAL_EVIDENCE_ROOT'),phase18_authority=False)
        receipt_binding = io.save(E/'receipts/d307-ext007-descriptive-freeze-1.json',receipt)
        actor = before.resolutions['S17-EXT-003'].semantic_context['trust']['measurements']['principal']
        recorded = utc()
        # Validate a separate preview before writing the canonical resolution.
        # Its locator does not match latest_journal's canonical filename glob.
        preview_record = dict(schema_version='cpu-prefetch-stage17-external-input-resolution/1',
            resolution_id='S17-EXT-007-RESOLUTION-007',sequence_number=7,input_id='S17-EXT-007',actor=actor,
            recorded_at_utc=recorded,graph_sha256=initial['graph']['sha256'],catalog_sha256=initial['catalog']['sha256'],
            version_hashes=initial['version_hashes'],evidence=[dict(kind='EXTERNAL_CUSTODY_RECEIPT',
                receipt_path=str(Path(receipt_binding['path']).relative_to(E)),receipt_size_bytes=receipt_binding['size_bytes'],
                receipt_sha256=receipt_binding['sha256'])],authorization=None,verification_result='PASS',
            automatic_resolution=False,retry_authority=False,stage18_authority=False)
        preview_binding = io.save(E/'records/d307-preview-resolution-007.json',preview_record)
        snapshot = copy.deepcopy(initial); snapshot['journal_sequence_number'] += 1
        snapshot['previous_journal'] = dict(path=str(previous_path.relative_to(E)),sha256=hashlib.sha256(initial_raw).hexdigest())
        snapshot['resolution_records'].append(dict(path=str(Path(preview_binding['path']).relative_to(E)),sha256=preview_binding['sha256']))
        preview = io.save(E/'journal/d307-scoped-admission-preview.json',snapshot)
        preview_validation = journal.validate_operational_journal(repository_root=root,evidence_root=E,
            latest_journal=Path(preview['path']),journal_directory=E/'journal',pilot_archive=arguments['pilot_archive'],
            pilot_sidecar=arguments['pilot_sidecar'],as_of_utc=recorded,allow_synthetic_test_evidence=False)
        scoped.require(len(preview_validation.resolutions) == 7 and preview_validation.pilot_ready is False,'actual complete preview replay')
        io.save(a.output_root/'preview-verified.json',dict(status='SCOPED_EXT007_PREVIEW_VERIFIED',preview=preview,
            preserved_predecessors=predecessors,pilot_ready=False,phase18_authority=False))
        published = cli.append_resolution(**arguments,input_id='S17-EXT-007',actor=actor,recorded_at_utc=utc(),
            repository_evidence=[],receipt_evidence=[Path(receipt_binding['path'])],authorization_file=None)
        after = cli.validate_journal(**arguments)
        scoped.require(len(after.resolutions) == 7 and len(after.transitions) == 3 and after.pilot_ready is False,'actual completed scoped resolution')
        scoped.require(all(after.resolutions[k].sha256 == v.sha256 for k,v in before.resolutions.items()),'six immutable predecessors preserved')
        resolution = after.resolutions['S17-EXT-007']
        scoped.require(resolution.semantic_context['calibration_scope'] == scoped.freeze.SCOPE,'scoped accepted result')
        result = dict(status='SCOPED_EXT007_OPERATIONALLY_ADMITTED',completed_at_utc=utc(),journal=io.binding(published),
            resolution=io.binding(resolution.path),policy=io.binding(root/semantic.POLICY_PATH),
            manifest=manifest_binding,custody_receipt=receipt_binding,freeze=record,
            resolved_inputs=list(after.resolutions),unresolved_inputs=[f'S17-EXT-{i:03d}' for i in (8,9,10)],
            current_state=after.current_state,preserved_predecessor_count=6,transition_count=3,
            calibration_scope=scoped.freeze.SCOPE,legacy_statistical_freeze_satisfied=False,pilot_ready=False,
            stage17_complete=False,new_measurements=0,raw_decoding_repeated=False,new_qualification=False,phase18_authority=False)
        io.save(a.output_root/'complete.json',result); print(json.dumps(result),flush=True)
    except BaseException as error:
        io.save(a.output_root/'failure.json',dict(type=type(error).__name__,message=str(error),new_measurements=0,
            raw_decoding_repeated=False,execution_authority=False,phase18_authority=False))
        raise


if __name__ == '__main__': main()
