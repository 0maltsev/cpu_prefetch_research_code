"""Read-only D254 stopped-prefix inspection; never grants collection credit."""
import dataclasses, datetime, hashlib, importlib.util, json, os, pathlib, time

E = pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26')
OP = E/'daycap-resume-operators-2'
spec = importlib.util.spec_from_file_location('bound_d254_analysis', OP/'analyze_daycap.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
c = json.loads((E/'daycap-collection-preparation-1/analysis-configuration.json').read_bytes())
cli = a.configure(c)
prepared = cli.prepare_formal_retention(repository_root=pathlib.Path(c['repository_root']),
    operational_evidence_root=E, journal=pathlib.Path(c['files']['journal']['path']),
    journal_directory=E/'journal', authorization_path=pathlib.Path(c['files']['authorization']['path']),
    signature_path=pathlib.Path(c['files']['signature']['path']),
    pilot_archive=pathlib.Path(c['archive']), pilot_sidecar=pathlib.Path(c['sidecar']))
a.require(prepared.request_bytes == a.read(c['files']['request']), 'original signed request differs')
plan = prepared.request['action_inputs']['plan']
deadline = min(1286361844786205, time.monotonic_ns()+2400*10**9)
extent = cli.controller.contract.validate_plan('Q16b', plan)
decode = cli.registry._metadata_decode_limits(plan, extent, prepared.archive_runtime_profile, deadline)
executor = cli.controller.make_executor()
root = E/'q16b-prefix-inspection-1'
root.mkdir(mode=0o700)
phase = pathlib.Path(prepared.request['evidence_root_binding']['absolute_path'])
import stage17_formal_archive_registry_v1 as registry
with executor.open_store(prepared.request, deadline) as store:
    ledger = dataclasses.asdict(store.ledger_binding())
    pending = sorted(store._capture_pending)
    states = {k:v for k,v in store._states.items() if k.startswith(store.family_id+':q16b-c16-')}
    inventory = dict(utc=str(datetime.datetime.now(datetime.timezone.utc)),
        signed_request=c['files']['request'], family_id=store.family_id,
        ledger=ledger, pending_captures=pending, capture16_states=states,
        final_checkpoint=json.loads((phase/'formal-capture-16-final-checkpoint.json').read_bytes()),
        raw_control_stat=dict(size_bytes=(phase/'q16b-c16-control.json').stat().st_size,
                              links=(phase/'q16b-c16-control.json').stat().st_nlink),
        archive_candidates=[dict(name=p.name,size_bytes=p.stat().st_size)
            for p in (store.root/'archives').iterdir()
            if any(p.name == row['payload'].get('staging_name') for row in states.values())],
        execution_authority=False, scientific_validity='NOT_ASSESSED')
    a.save(root/'inventory.json', inventory)
    print(json.dumps(dict(stage='inventory',root=str(root),ledger=ledger,pending=pending,
        capture16_states={k:v['kind'] for k,v in states.items()},
        archive_candidates=inventory['archive_candidates'])),flush=True)
    verified=[]
    for ordinal in range(16):
        def bound(name):
            raw=(phase/name).read_bytes()
            a.require(len(raw)<=128*1024,'small metadata bound')
            return dict(file_name=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        row=registry.verify_capture_metadata(store=store,action='Q16b',
            capture=plan['captures'][ordinal]['capture'],
            checkpoint_binding=bound(f'formal-capture-{ordinal}-final-checkpoint.json'),
            receipt_binding=bound(f'formal-capture-{ordinal}-archive-custody.json'),
            decoder_profile=prepared.archive_runtime_profile.decoder,decoder_limits=decode)
        verified.append(row)
        a.save(root/f'capture-{ordinal}-metadata.json',row)
        print(json.dumps(dict(stage='metadata',completed=len(verified),total=16)),flush=True)
    a.require(dataclasses.asdict(store.ledger_binding())==ledger,'read-only ledger changed')
    a.save(root/'metadata-complete.json',dict(captures=16,ledger_unchanged=True,
        inverse_readback_performed=False,scientific_validity='NOT_ASSESSED',execution_authority=False))
