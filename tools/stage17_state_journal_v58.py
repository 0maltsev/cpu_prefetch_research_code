"""D278 E28-only administrative recovery, independent of the qualified919c486 release.

The installed policy61 source and qualified worker are never rewritten. The
adapter retains policy61 semantic admission and v12 lineage checks, replacing only
the explicitly approved third transition with a signed version2 contract.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import types

EVIDENCE = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28')
REPOSITORY = EVIDENCE/'admission-root'
ADMIN = EVIDENCE/'d278-admin-1'
TRANSACTION = EVIDENCE/'d278-transition-1'
if Path(__file__).resolve().parent == ADMIN:
    sys.path.insert(0, str(REPOSITORY/'tools'))

import stage17_state_journal_v57 as predecessor
import stage17_state_journal_v12 as core
import stage17_phase_controller_v2 as support

ORIGINAL_VALIDATE = predecessor.validate_operational_journal
JournalError = predecessor.JournalError
SOURCE = '919c48637cbdba9e466a3104f5cbb39f7184e39b'
WORKER = '1baa213a137679460348ff6b861839044022957a4de0e5fc79929f7b49bed883'
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
POLICY = 'E28-D278-TRANSITION-ONLY-v1'
AUTH_SCHEMA = 'cpu-prefetch-stage17-transition-recovery-authorization/1'
TRANSITION_SCHEMA = 'cpu-prefetch-stage17-state-transition/2'
AUTH_ID = 'CPU-PREFETCH-V5-V28-D278-TRANSITION-AUTH-1'
TRANSITION_NAME = 'records/transition-003-d278-1.json'
BASE_NAME = 'journal/stage17-state-journal-000008.json'
NEXT_NAME = 'journal/stage17-state-journal-000009.json'
BASE_SHA = None
FIXED = None
CONFIGURATION = None
SELF_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def configure_verified_incident(configuration,expected_sha256):
    global BASE_SHA,FIXED,CONFIGURATION
    raw=read(configuration)
    require(sha(raw)==expected_sha256,'explicit incident configuration SHA256')
    value=parse(raw)
    require(set(value)=={'schema_version','source_revision','worker_sha256','boot_id','files','execution_authority','phase18_authority'},'closed incident configuration')
    require(value['schema_version']=='cpu-prefetch-stage17-d278-transition-incident/1'
        and value['source_revision']==SOURCE and value['worker_sha256']==WORKER and value['boot_id']==BOOT
        and value['execution_authority'] is False and value['phase18_authority'] is False,'actual incident identity/scope')
    required={'journal','failed_transition','failed_candidate','q15r_result','q15w_result','q15w_completion','clocks','session','isolation_handoff'}
    require(set(value['files'])==required,'complete exact incident closure')
    fixed={}
    for role,b in value['files'].items():
        path=Path(b['path']);require(path.is_relative_to(EVIDENCE),'incident outside E28')
        bound(b);fixed[role]=(str(path.relative_to(EVIDENCE)),b['sha256'])
    require(fixed['journal'][0]==BASE_NAME and fixed['failed_transition'][0]=='records/transition-003.json'
        and fixed['failed_candidate'][0]=='journal/stage17-state-journal-000009.json.candidate','exact original prefix/failed draft names')
    require(Path(configuration)==ADMIN/'incident.json','verified administrative packet incident')
    require(CONFIGURATION is None or CONFIGURATION==raw,'incident already pinned')
    CONFIGURATION=raw;FIXED=fixed;BASE_SHA=fixed['journal'][1]


def validate_failed_edge(failed,baseline,resolutions):
    graph=parse(read(REPOSITORY/'config/stage17/stage17-operational-graph-definition-v1.json'));edge=graph['transitions'][2]
    previous=baseline['transition_records'][-1]['sha256']
    timestamp=failed['timestamp_utc']
    actor=resolutions['S17-EXT-003'].semantic_context['trust']['measurements']['principal']
    authorizations=[]
    for key in edge['authorization_input_ids']:
        r=resolutions[key];summary=r.document['authorization']
        authorizations.append(dict(input_id=key,resolution_id=r.resolution_id,
            authorization_id=summary['authorization_id'],authority_scope=summary['authority_scope']))
        sampled=support._parse_utc(timestamp)
        if key=='S17-EXT-001':
            require(support._parse_utc(summary['expires_at_utc'])<=sampled,'only expired EXT001 renewal')
        else:
            require(support._parse_utc(summary['issued_at_utc'])<=sampled<support._parse_utc(summary['expires_at_utc']),
                'other original transition authority expired/future')
    wanted=dict(schema_version='cpu-prefetch-stage17-state-transition/1',transition_id='STAGE17-TRANSITION-003',
        sequence_number=3,from_state=edge['from_state'],to_state=edge['to_state'],previous_transition_sha256=previous,
        actor=actor,timestamp_utc=timestamp,evidence_resolutions=[dict(input_id=k,resolution_id=resolutions[k].resolution_id,
            sha256=resolutions[k].sha256) for k in edge['required_input_ids']],authorizations=authorizations,
        graph_sha256=baseline['graph']['sha256'],catalog_sha256=baseline['catalog']['sha256'],
        version_hashes=baseline['version_hashes'],authority_scope=edge['authority_scope'],automatic_transition=False,
        retry_allowed=False,stage18_authority=False)
    require(failed==wanted,'original transition full edge/authority fields differ')


def require(ok, message):
    if not ok:
        raise JournalError('D278: '+message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(document):
    return (json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=False)+'\n').encode()


def parse(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(JournalError('nonfinite JSON')))


def read(path):
    path = Path(path)
    require(path.is_absolute(), 'absolute input path required')
    return core._external_bytes(Path('/'), str(path)[1:], 'D278 input')[1]


def binding(path, payload=None):
    raw = read(path) if payload is None else payload
    return dict(path=str(path), size_bytes=len(raw), sha256=sha(raw))


def bound(value):
    require(type(value) is dict and set(value) == {'path', 'size_bytes', 'sha256'}, 'binding field set')
    raw = read(value['path'])
    require(type(value['size_bytes']) is int and len(raw) == value['size_bytes']
            and sha(raw) == value['sha256'], 'bound bytes differ: '+value['path'])
    return raw


def admin_binding():
    path = ADMIN/'manifest.json'
    raw = read(path); document = parse(raw)
    require(set(document) == {'schema_version', 'administrative_source_revision', 'qualified_source_revision', 'files', 'execution_authority'}, 'admin manifest fields')
    require(document['schema_version'] == 'cpu-prefetch-stage17-d278-admin-manifest/1'
            and document['qualified_source_revision'] == SOURCE
            and re.fullmatch('[0-9a-f]{40}', document['administrative_source_revision']) is not None
            and document['execution_authority'] is False, 'admin manifest identity')
    names = set()
    for item in document['files']:
        name = item['name']
        require(set(item) == {'name', 'size_bytes', 'sha256'} and Path(name).name == name
                and name not in names, 'admin member name/fields')
        names.add(name)
        bound(dict(path=str(ADMIN/name), size_bytes=item['size_bytes'], sha256=item['sha256']))
        if name == Path(__file__).name:
            require(item['sha256'] == SELF_SHA and Path(__file__).resolve() == ADMIN/name,
                    'loaded administrative verifier differs')
    require({'stage17_state_journal_v58.py', 'incident.json',
             'decision.md', 'owner-acceptance.json'} == names,
            'administrative closure is incomplete')
    require({p.name for p in ADMIN.iterdir()} == names | {'manifest.json'}, 'expanded admin directory')
    decision = sha(read(ADMIN/'decision.md'))
    approval = parse(read(ADMIN/'owner-acceptance.json'))
    require(approval['decision_id'] == 'D278' and approval['owner_message'] == 'continue'
            and approval['recorded_decision_sha256'] == decision
            and approval['exact_decision_text_approved'] is False,
            'recorded owner instruction differs')
    return binding(path, raw)


def incident():
    require(FIXED is not None, 'verified incident is not configured')
    bindings={}; documents={}
    for role,(name,digest) in FIXED.items():
        raw=read(EVIDENCE/name);require(sha(raw)==digest,'different incident: '+role)
        bindings[role]=binding(EVIDENCE/name,raw);documents[role]=parse(raw)
    r=documents['q15r_result'];w=documents['q15w_result'];c=documents['q15w_completion']
    require(r['terminal_state']=='Q15_R_READ_ONLY_COMPLETE' and r['quarantined'] is False,'Q15-R failed')
    require(w['terminal_state']=='Q15_W_RESTORED_COMPLETE' and w['restoration_verified'] is True
        and w['quarantined'] is False,'Q15-W failed or restoration unverified')
    require(all(c[k] is True for k in ('leader_reaped','process_group_gone','restoration_verified'))
        and c['quarantined'] is False,'native Q15 cleanup incomplete')
    session=documents['session']
    require(session['exit_code']==0 and session['leader_reaped'] is True,'Q15 controller not reaped')
    require(documents['clocks']['both_pairs_passed'] is True,'retained clocks failed')
    handoff=documents['isolation_handoff']
    require(handoff['isolation_retained'] is True and handoff['source_revision']==SOURCE
        and handoff['q15w_result_sha256']==bindings['q15w_result']['sha256']
        and handoff['q15w_completion_sha256']==bindings['q15w_completion']['sha256']
        and handoff['observation']['partition']['cgroup.procs']=='','qualified empty isolation handoff')
    require(documents['journal']['journal_sequence_number']==8
        and len(documents['journal']['resolution_records'])==6
        and len(documents['journal']['transition_records'])==2,'complete original six-resolution prefix')
    return bindings,documents



def resolution_bindings(resolutions, baseline):
    require(len(baseline['resolution_records']) == 6, 'six original resolutions required')
    expected = {}
    for reference in baseline['resolution_records']:
        raw = read(EVIDENCE/reference['path'])
        require(sha(raw) == reference['sha256'], 'original resolution changed')
        row = parse(raw); resolution = resolutions.get(row['input_id'])
        require(resolution is not None and resolution.sha256 == reference['sha256']
                and resolution.resolution_id == row['resolution_id'], 'qualified resolution lineage changed')
        expected[row['input_id']] = dict(input_id=row['input_id'], resolution_id=row['resolution_id'], sha256=reference['sha256'])
    require(set(expected) == {f'S17-EXT-{i:03d}' for i in range(1, 7)}, 'original resolution population')
    context = resolutions['S17-EXT-006'].semantic_context
    require(context['source_revision'] == SOURCE and context['release_artifact_sha256'] == WORKER,
            'qualified measured source/runtime changed')
    return [expected[key] for key in sorted(expected)]


def template(resolutions):
    inputs, documents = incident()
    refs = resolution_bindings(resolutions, documents['journal'])
    failed = documents['failed_transition']
    require(failed['sequence_number'] == 3 and failed['from_state'] == 'PREFLIGHT_ACCEPTED'
            and failed['to_state'] == 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
            and failed['evidence_resolutions'] == refs, 'failed transition edge differs')
    validate_failed_edge(failed,documents['journal'],resolutions)
    trust = resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role'] == 'OWNER', 'owner trust required')
    return dict(schema_version=AUTH_SCHEMA, authorization_id=AUTH_ID, policy_id=POLICY,
        actor=trust['measurements']['principal'], reviewer='OWNER', stand_id=trust['subject_id'],
        boot_id=BOOT, qualified_source_revision=SOURCE, qualified_worker_sha256=WORKER,
        administrative_manifest=admin_binding(), decision=binding(ADMIN/'decision.md'),
        owner_acceptance=binding(ADMIN/'owner-acceptance.json'), evidence_bindings=inputs,
        predecessor_resolutions=refs, target=dict(sequence_number=3, from_state=failed['from_state'],
            to_state=failed['to_state'], previous_transition_sha256=failed['previous_transition_sha256']),
        authority_scope='E28_D278_ADMINISTRATIVE_TRANSITION_ONLY', one_use=True,
        automatic_retries=0, execution_authority=False, phase18_authority=False)


def validate_authority(document, expected, at):
    require(set(document) == set(expected) | {'issued_at_utc', 'expires_at_utc'}, 'authority fields expanded/missing')
    require(canonical({k: document[k] for k in expected}) == canonical(expected), 'authority scope or bound evidence changed')
    issued = support._parse_utc(document['issued_at_utc']); expires = support._parse_utc(document['expires_at_utc'])
    sampled = support._parse_utc(at)
    require(expires-issued == dt.timedelta(seconds=1800) and issued <= sampled < expires,
            'fresh transition authority is future/expired or not1800seconds')


def validate_current_q15w(resolutions,timestamp):
    auth=resolutions['S17-EXT-005'].document['authorization'];sampled=support._parse_utc(timestamp)
    require(support._parse_utc(auth['issued_at_utc'])<=sampled<support._parse_utc(auth['expires_at_utc']),
        'original Q15-W authority must remain live for recovery')


def make_transition(failed, authority, signature, timestamp):
    result = copy.deepcopy(failed)
    result.update(schema_version=TRANSITION_SCHEMA, transition_id='STAGE17-TRANSITION-003-D278-1',
                  timestamp_utc=timestamp, recovery=dict(policy_id=POLICY, authorization=authority, signature=signature))
    return result


def make_journal(baseline, reference):
    require(baseline['journal_sequence_number'] == 8 and len(baseline['transition_records']) == 2,
            'exact committed predecessor required')
    result = copy.deepcopy(baseline)
    result.update(journal_sequence_number=9, previous_journal=dict(path=BASE_NAME, sha256=BASE_SHA))
    result['transition_records'].append(reference)
    return result


def transaction_receipt(authority, signature, transition, journal, timestamp):
    return dict(schema_version='cpu-prefetch-stage17-d278-consumption/1', policy_id=POLICY,
        consumed_at_utc=timestamp, authorization=authority, signature=signature,
        transition=transition, committed_journal=journal, automatic_retries=0, execution_authority=False)


def transitions(**arguments):
    refs = arguments['references']
    if len(refs) < 3 or refs[2]['path'] != TRANSITION_NAME:
        return core._transitions(**arguments)
    require(len(refs) == 3 and arguments['evidence_root'] == EVIDENCE
            and arguments['repository_root'] == REPOSITORY, 'recovery outside fixed E28 edge')
    prior = dict(arguments, references=refs[:2])
    state, previous = core._transitions(**prior)
    require(state == 'PREFLIGHT_ACCEPTED', 'historical transition prefix changed')
    path, document, digest = core._record(EVIDENCE, refs[2], 'D278 transition')
    expected = template(arguments['resolutions'])
    inputs, documents = incident()
    failed = documents['failed_transition']
    edge = arguments['graph']['transitions'][2]
    require(failed['previous_transition_sha256'] == previous[-1].sha256
            and failed['graph_sha256'] == arguments['graph_sha256']
            and failed['catalog_sha256'] == arguments['catalog_sha256']
            and failed['version_hashes'] == arguments['versions']
            and failed['from_state'] == edge['from_state']
            and failed['to_state'] == edge['to_state']
            and failed['authority_scope'] == edge['authority_scope'], 'original graph edge differs')
    recovery = document.get('recovery', {})
    require(set(recovery) == {'policy_id', 'authorization', 'signature'} and recovery['policy_id'] == POLICY,
            'transition recovery fields')
    ab = recovery['authorization']; sb = recovery['signature']
    require(ab['path'] == str(TRANSACTION/'authorization.json')
            and sb['path'] == str(TRANSACTION/'authorization.json.sig'), 'one recovery authority namespace required')
    auth_raw = bound(ab); auth = parse(auth_raw); bound(sb)
    require(auth_raw == canonical(auth), 'noncanonical recovery authorization')
    validate_authority(auth, expected, document['timestamp_utc'])
    trust = arguments['resolutions']['S17-EXT-003'].semantic_context['trust']
    support._verify_signature(auth_raw, Path(sb['path']), trust)
    validate_current_q15w(arguments['resolutions'],document['timestamp_utc'])
    wanted = make_transition(documents['failed_transition'], ab, sb, document['timestamp_utc'])
    require(document == wanted and read(path) == canonical(wanted), 'transition differs from approved edge')
    require(support._parse_utc(document['timestamp_utc']) >= max(r.recorded_at_utc for key, r in arguments['resolutions'].items() if key in {f'S17-EXT-{i:03d}' for i in range(1,7)}), 'transition predates qualification')
    journal_raw = canonical(make_journal(documents['journal'], refs[2]))
    wanted_receipt = transaction_receipt(ab, sb, binding(path, canonical(document)),
        binding(EVIDENCE/NEXT_NAME, journal_raw), document['timestamp_utc'])
    require(read(TRANSACTION/'consumption.json') == canonical(wanted_receipt), 'one-use consumption receipt differs')
    previous.append(core.StateTransition(document['transition_id'], 3, state, document['to_state'],
        support._parse_utc(document['timestamp_utc']), path, digest, document))
    return document['to_state'], previous


def validate_operational_journal(**arguments):
    predecessor.activate()
    if Path(arguments['evidence_root']).resolve() != EVIDENCE:
        return ORIGINAL_VALIDATE(**arguments)
    require(Path(arguments['repository_root']).resolve() == REPOSITORY
            and arguments.get('allow_synthetic_test_evidence', False) is False,
            'fixed original repository and genuine qualification required')
    # Full policy61 semantic admission, immutable-prefix/fork checks and output
    # construction are retained. Historical transition code is never modified.
    function = types.FunctionType(core.validate_operational_journal.__code__,
        {**vars(predecessor.activate()), '_transitions': transitions},
        argdefs=core.validate_operational_journal.__defaults__)
    function.__kwdefaults__ = core.validate_operational_journal.__kwdefaults__
    return function(**arguments)


def activate():
    return predecessor.activate()


def write_exclusive(path, raw):
    require(path.parent.resolve(strict=True) == path.parent, 'output ancestor symlink')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def original_validation(archive, sidecar):
    require(os.geteuid() == 1000, 'trusted owner UID1000 required')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'live boot changed')
    require(not any(os.path.lexists(path) for path in (EVIDENCE/NEXT_NAME, EVIDENCE/TRANSITION_NAME,
            EVIDENCE/'journal/stage17-state-journal-000009.d278-candidate', TRANSACTION/'consumption.json')),
            'recovery already consumed or partial; no retry')
    predecessor.activate()
    result = ORIGINAL_VALIDATE(repository_root=REPOSITORY, evidence_root=EVIDENCE,
        latest_journal=EVIDENCE/BASE_NAME, journal_directory=EVIDENCE/'journal',
        pilot_archive=archive, pilot_sidecar=sidecar, as_of_utc=support._now(), allow_synthetic_test_evidence=False)
    require(result.latest_journal_sha256 == BASE_SHA and result.current_state == 'PREFLIGHT_ACCEPTED'
            and result.resolution_count == 6 and result.transition_count == 2, 'original committed readiness differs')
    return result


def author(archive, sidecar):
    result = original_validation(archive, sidecar)
    document = template(result.resolutions)
    now = support._now(); end = support._parse_utc(now)+dt.timedelta(seconds=1800)
    document.update(issued_at_utc=now, expires_at_utc=end.isoformat().replace('+00:00', 'Z'))
    TRANSACTION.mkdir(mode=0o700)
    path = TRANSACTION/'authorization.json'; raw = canonical(document)
    write_exclusive(path, raw)
    return binding(path, raw)


def commit(archive, sidecar):
    result = original_validation(archive, sidecar)
    expected = template(result.resolutions)
    ab = binding(TRANSACTION/'authorization.json'); sb = binding(TRANSACTION/'authorization.json.sig')
    raw = bound(ab); document = parse(raw)
    require(raw == canonical(document), 'noncanonical recovery authority')
    timestamp = support._now(); validate_authority(document, expected, timestamp)
    validate_current_q15w(result.resolutions,timestamp)
    support._verify_signature(raw, Path(sb['path']), result.resolutions['S17-EXT-003'].semantic_context['trust'])
    _, inputs = incident()
    transition = make_transition(inputs['failed_transition'], ab, sb, timestamp)
    transition_raw = canonical(transition)
    reference = dict(path=TRANSITION_NAME, sha256=sha(transition_raw))
    journal = make_journal(inputs['journal'], reference); journal_raw = canonical(journal)
    receipt = transaction_receipt(ab, sb, binding(EVIDENCE/TRANSITION_NAME, transition_raw),
        binding(EVIDENCE/NEXT_NAME, journal_raw), timestamp)
    # The exclusive durable marker consumes the authorization before any state
    # publication. Partial failure is retained; no retry/adoption path exists.
    write_exclusive(TRANSACTION/'consumption.json', canonical(receipt))
    write_exclusive(EVIDENCE/TRANSITION_NAME, transition_raw)
    candidate = EVIDENCE/'journal/stage17-state-journal-000009.d278-candidate'
    write_exclusive(candidate, journal_raw)
    validation = validate_operational_journal(repository_root=REPOSITORY, evidence_root=EVIDENCE,
        latest_journal=candidate, journal_directory=EVIDENCE/'journal', pilot_archive=archive,
        pilot_sidecar=sidecar, as_of_utc=support._now(), allow_synthetic_test_evidence=False)
    require(validation.current_state == 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
            and validation.transition_count == 3 and not validation.pilot_ready, 'recovered transition did not validate')
    validate_authority(document, expected, support._now())
    write_exclusive(EVIDENCE/NEXT_NAME, journal_raw)
    return receipt


def __getattr__(name):
    return getattr(predecessor,name)
