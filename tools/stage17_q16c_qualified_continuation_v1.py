"""D298 same-window administrative continuation of the frozen7b7c263 release.

No new window, qualification, constructor or completed raw validation is exposed.
Cold orchestration is derived from exact previously verified sources; only
administrative paths and the explicitly approved rearm sequence change.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time

NATIVE_SOURCE = '7b7c263cb850690cf333df0d196b18c875b4a53c'
PROPOSAL_SHA = '016c459cce17ce7be881fb62a9079e01913ef13f9cc61dad531d609dcb002888'
DEADLINE = 1589604784571258
ENVELOPE = 31460 * 10**9
E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
FROZEN = {
    'stage17_q16c_continuation_study_v1.py': '508d0e21d5df07e34ab38f2b5a7d9ad29df278c4bd90bcd293ca39df53880953',
    'stage17_q16c_continuation_operator_v1.py': '0a49bc2abdfcfb351588dfd8091e521dd94473761dc09e8d57c86e8ba2766cad',
    'stage17_q16c_continuation_recovery_v1.py': '87015225a0a00a26b2537c33322ec284a260bdc0deac83b15e90fdfc4e2acc81',
}


def require(value, message):
    if not value:
        raise ValueError('D298 continuation: ' + message)


def check_time(now):
    require(type(now) is int and 0 < now < DEADLINE - ENVELOPE,
            'complete31460s envelope must fit before the original deadline; no late start')


def replace_once(text, old, new):
    require(text.count(old) == 1, 'exact administrative source seam differs')
    return text.replace(old, new, 1)


def render(name, raw):
    require(name in FROZEN and hashlib.sha256(raw).hexdigest() == FROZEN[name], 'exact frozen operator source')
    text = raw.decode()
    if name == 'stage17_q16c_continuation_operator_v1.py':
        for old, new in [('platform-guard-1/witness.json', 'platform-guard-d298-1/witness.json'),
                         ("evidence/'platform-observations-1'", "evidence/'platform-observations-d298-1'"),
                         ('q16c-study-1/partition-restoration.json', 'q16c-study-d298-1/partition-restoration.json')]:
            text = replace_once(text, old, new)
    else:
        text = text.replace('d295-study-1', 'd298-study-1').replace('q16c-study-1', 'q16c-study-d298-1')
        text = text.replace('platform-guard-1', 'platform-guard-d298-1')
        text = text.replace('cpu-prefetch-d295-v32-1.service', 'cpu-prefetch-d298-v32-1.service')
        if name.endswith('recovery_v1.py'):
            text = replace_once(text, 'd295-independent-recovery-1.json', 'd298-independent-recovery-1.json')
            text = replace_once(text, 'isolation-preparation-v32-1/prospective-prestate.json',
                                'isolation-preparation-v32-d298-1/prospective-prestate.json')
        else:
            text = replace_once(text, 'import stage17_q16c_continuation_operator_v1 as io',
                                'import stage17_q16c_continuation_operator_v1 as io\nimport stage17_q16c_qualified_continuation_v1 as resume')
            text = replace_once(text, "for role,key in (('operator_sources','operator_inventory'),('prefix_validation_packet','prefix_packet'),",
                                "for role,key in (('prefix_validation_packet','prefix_packet'),")
            a = text.index('def sign_window(c):')
            b = text.index('\ndef run(args,c,h):', a)
            text = text[:a] + "def sign_window(c):\n    raise ValueError('D298 forbids a new window')\n\n" + text[b:]
            text = replace_once(text, "    io.require(not (E/'d295-execution-window-1').exists(),'unconsumed one-window namespace')",
                                "    resume.check_time(time.monotonic_ns())")
            text = replace_once(text, "record=sign_window(c);start=record['started_monotonic_ns'];complete=start+39380*NS",
                                "start=time.monotonic_ns();record=resume.admit(args,c);complete=resume.DEADLINE")
            a = text.index("        command('prefix',start+120*NS)")
            b = text.index("        guard.verify();command('sign-collect'", a)
            rearm = '''        import stage17_locked_compaction_guard_v1 as controls
        import stage17_q16c_compaction_integration_v2 as guarded
        guard=controls.Guard(E/'platform-guard-d298-1',deadline_ns=min(complete-6000*NS,start+25460*NS));guard.__enter__()
        os.chmod(guard.root,0o711)
        description,fd=guarded.export_witness(guard)
        try:io.save(E/'platform-guard-d298-1/witness.json',description)
        finally:os.close(fd)
        clock=module('d298_rearm_isolation',c['clock_adapter'])
        clock.Q.mkdir(mode=0o700);os.chown(clock.Q,1000,1000)
        pre=clock.ISO.prepare(clock.BINDINGS['isolation_config'])
        pp=Path(clock.BINDINGS['isolation_config']['evidence_root'])/'prospective-prestate.json'
        clock.retain(clock.Q/'prospective-plan.json',dict(isolation_prestate_binding=io.binding(pp),
            original_qualification=c['prior_qualification'],execution_window=c['window_proof']['manifest'],
            clocks_repeated=False,q15_repeated=False,global_deadline_ns=record['global_deadline_ns']))
        clock.ISO.verify_remaining_lifetime(pre['prestate'],24860*NS,120*NS)
        io.require(clock.isolated_state()['partition']['cgroup.procs']=='','fresh empty isolated partition')
        guard.verify();hardware.verify(prestate)
        io.require(time.monotonic_ns()<start+600*NS,'original600s rearm ceiling')
'''
            text = text[:a] + rearm + text[b:]
            text = replace_once(text, "choices=('prefix','construct','sign-collect','suffix')", "choices=('sign-collect','suffix')")
            text = text.replace('D295 stopped incomplete', 'D298 stopped incomplete')
    ast.parse(text, filename=name)
    return text.encode()


def render_isolation():
    return b'''"""D298 fresh isolation receipts; passed clocks/Q15 remain untouched."""
import copy
import hashlib
from pathlib import Path
import types
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
BASE=E/'operator-preparation-v32-1/run_clock_qualification_v32.py'
BASE_SHA='bc3880139caa1ac1a0880babfee52335749c870c5f6df402b1a1cdcfc2218018'
_BASE=None
def load_base():
    global _BASE
    if _BASE is None:
        raw=BASE.read_bytes()
        if any(p.is_symlink() for p in (BASE,*BASE.parents)) or hashlib.sha256(raw).hexdigest()!=BASE_SHA:
            raise ValueError('D298 exact qualified isolation adapter required')
        module=types.ModuleType('d298_original_qualified_isolation');module.__file__=str(BASE)
        exec(compile(raw,str(BASE),'exec'),module.__dict__)
        config=copy.deepcopy(module.BINDINGS)
        config['isolation_config']['evidence_root']=str(E/'isolation-preparation-v32-d298-1')
        module.configure(config);module.Q=E/'clock-rearm-d298-1';_BASE=module
    return _BASE
def __getattr__(name):
    if name in ('main','capture'):raise AttributeError(name)
    return getattr(load_base(),name)
'''


def validate_acceptance(acceptance):
    expected = dict(decision_id='D298', owner_message='continue', exact_decision_text_approved=True,
                    recorded_decision_sha256=PROPOSAL_SHA, new_execution_windows=0, manual_continuations=1,
                    automatic_retry=False, repeat_qualification=False, repeat_completed_measurements=False,
                    repeat_completed_raw_validations=False, reused_capture_count=86, remaining_capture_count=94,
                    maximum_remaining_seconds=31460, original_deadline_monotonic_ns=DEADLINE,
                    latest_start_monotonic_ns=DEADLINE-ENVELOPE, phase18_authority=False)
    for key, value in expected.items():
        require(type(acceptance.get(key)) is type(value) and acceptance[key] == value, 'actual owner approval ' + key)


def admit(args, c, *, software_check=False):
    """Authenticate actual approval, historical qualification and fixed inputs."""
    import stage17_q16c_continuation_operator_v1 as io
    check_time(time.monotonic_ns())
    require(c['source_revision'] == NATIVE_SOURCE and c['administrative_source_revision'] != NATIVE_SOURCE,
            'distinct actual native and administrative identities')
    require(c['evidence_root'] == str(E) and c['continuation_decision'] == 'D298', 'one original stand scope')
    operators = io.document(c['operator_inventory'])
    require(operators['administrative_source_revision'] == c['administrative_source_revision']
            and operators['qualified_native_source_revision'] == NATIVE_SOURCE, 'actual separate source bindings')
    require(c['operator_sources'][Path(__file__).name] == io.binding(Path(__file__).resolve()), 'actual D298 admission source')
    require(c['original_total_deadline_ns'] == DEADLINE, 'unchanged original total deadline')
    proposal = io.read(c['continuation_authority']['proposal'])
    require(hashlib.sha256(proposal).hexdigest() == PROPOSAL_SHA, 'exact approved D298 proposal')
    acceptance_raw = io.read(c['continuation_authority']['acceptance'])
    validate_acceptance(json.loads(acceptance_raw))
    cli = io.cli_for(c, configured=True)
    validation = cli._validation(Path(c['repository_root']), E,
        pilot_archive=Path(c['archive']['path']), pilot_sidecar=Path(c['sidecar']['path']))
    require(validation.current_state == 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
            and set(validation.resolutions) == {f'S17-EXT-{i:03d}' for i in range(1,7)}, 'six passed actual qualifications')
    current = validation.resolutions['S17-EXT-006'].semantic_context
    require(current['source_revision'] == NATIVE_SOURCE and current['release_artifact_sha256'] == c['worker']['sha256']
            and current['inventory_sha256'] == c['candidate_inventory']['sha256'], 'unchanged actual qualified release')
    from stage17_phase_controller_v2 import _verify_signature
    trust = validation.resolutions['S17-EXT-003'].semantic_context['trust']
    io.read(c['continuation_authority']['signature'])
    _verify_signature(acceptance_raw, Path(c['continuation_authority']['signature']['path']), trust)
    import stage17_q16c_execution_window_v5 as window
    record = io.document(c['window_proof']['manifest'])
    require(c['window_proof']['manifest']['sha256'] == '690615df0cdc257670cfa792e42813aa38b20970bddfe65a7d27abc79e9c3c16',
            'original signed window bytes')
    window.validate_record(record, now=time.monotonic_ns(), expected_source=NATIVE_SOURCE,
        expected_worker=c['worker']['sha256'], expected_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    io.read(c['window_proof']['signature'])
    _verify_signature(window.read(c['window_proof']['manifest']), Path(c['window_proof']['signature']['path']), trust)
    window.verify_bindings(record)
    require(record['started_monotonic_ns']+39380*10**9 == DEADLINE, 'no total deadline reset')
    old = io.document(c['prior_result']); recovery = io.document(c['prior_recovery'])
    require(old['success'] is False and [p['role'] for p in old['phases']] == ['prefix','construct']
            and old['phases'][0]['exit_code'] == 0 and old['phases'][1]['exit_code'] == 1
            and all(p['leader_reaped'] for p in old['phases'])
            and old['partition_restoration']['verified'] is True
            and recovery['verified'] is True and recovery['errors'] == [], 'exact stopped/reaped/restored incident')
    require(io.document(c['prior_qualification'])['success'] is True, 'passed original qualification')
    require(len(c['qualification_receipts']) == 7, 'all seven qualification receipts')
    for b in c['qualification_receipts']:
        receipt = io.document(b)
        require(receipt['exit_code'] == 0 and receipt['leader_reaped'] is True, 'passed/reaped qualification prerequisite')
    import stage17_q16c_completed_prefix_v1 as cached
    packet = io.document(c['prefix_packet'])
    cached.verify_reports(packet['completion'],packet['accepted_prefix'],packet['process_receipts'])
    require(io.binding(Path(c['worker']['path'])) == c['worker'], 'actual unchanged worker bytes')
    io.read(c['candidate_inventory'])
    import stage17_q16c_prefix_compatibility_v1 as compatibility
    original = Path(io.document(c['original_context'])['resolutions']['S17-EXT-006']['semantic_context']['archive_bundle_root'])
    candidate = Path(c['candidate_inventory']['path']).parent
    for member in compatibility.LIBRARIES:
        require((original/member).read_bytes() == (candidate/member).read_bytes(), 'unchanged measured library ' + member)
    constructed = io.document(c['preconstruction'])
    require(c['preconstruction']['sha256'] == '5867405f24bb920ef684c9fbff296375d48f338f814137f0cb6ba2aa41719838'
            and constructed['status'] == 'UNSIGNED_INPUTS_VALIDATED', 'actual completed unsigned construction')
    plan = io.document(constructed['plan']); inputs = io.document(constructed['action_inputs'])
    require(constructed['plan']['sha256'] == '1212db59b9c12dd50837ca4b79897ddcd76a06fc4c3ea99b1fabd9b2b23b36a6'
            and constructed['action_inputs']['sha256'] == '3d48b21c6b4204006a4975965d8ac64585577e64d9569484685fbd5a102c6fcb',
            'exact prospectively prepared94 inputs')
    require(io.binding(Path(c['output_root'])/'constructed.json') == c['preconstruction'], 'unchanged constructor output path')
    require(len(plan['captures']) == 94 and inputs['plan'] == plan, 'complete prepared94 matrix')
    require(not (Path(c['program_root'])/'working'/constructed['plan']['sha256']).exists()
            and not (Path(c['repository_root'])/'evidence/formal-q16c-d295-1').exists()
            and not (Path(c['output_root'])/'prepared.json').exists(), 'unused formal family and identities')
    import stage17_hardware_recovery_v1 as hardware
    rows = inputs['hardware_control']['prestate']
    require([r['cpu'] for r in rows] == [0,1,8], 'actual three-CPU qualified prestate')
    hardware.verify(tuple((r['cpu'],int(r['complete_value_hex'],16)) for r in rows))
    # Inventory/source ownership admission is executed as UID1000, never root.
    import subprocess
    guard = c['operator_sources']['check_stage17_execution_owner_v1.py']
    subprocess.run(['/usr/bin/setpriv','--reuid=1000','--regid=1000','--clear-groups','/usr/bin/python3','-B',guard['path'],
        '--bundle-root',str(Path(c['candidate_inventory']['path']).parent),'--uid','1000',
        '--inventory-sha256',c['candidate_inventory']['sha256'],'--source-revision',NATIVE_SOURCE,
        '--worker-sha256',c['worker']['sha256'],'--output',str(E/('d298-execution-owner-preflight-1.json' if software_check
                                                              else 'd298-execution-owner-admission-1.json'))],
        check=True,timeout=120)
    check_time(time.monotonic_ns())
    return record
