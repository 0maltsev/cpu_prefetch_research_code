"""D242 E25-only administrative recovery, independent of measured release42.

The installed v52 source/policy and qualified worker are never rewritten. The
adapter retains v52 semantic admission and v12 lineage checks, replacing only
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

EVIDENCE = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
REPOSITORY = EVIDENCE/'admission-root'
ADMIN = EVIDENCE/'d242-admin-1'
TRANSACTION = EVIDENCE/'d242-transition-1'
if Path(__file__).resolve().parent == ADMIN:
    sys.path.insert(0, str(REPOSITORY/'tools'))

import stage17_state_journal_v52 as predecessor
import stage17_state_journal_v12 as core
import stage17_phase_controller_v2 as support

ORIGINAL_VALIDATE = predecessor.validate_operational_journal
JournalError = predecessor.JournalError
SOURCE = '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
WORKER = '7abf4cfac0051103f98b3f63f37efd1bde757d954c973460be6fe4d245f6a275'
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
PROPOSAL = 'dc77f7c59cfa7e2b1225b159c9dc7a452b9f5d60c9c0243d8fc6731ddaffaaed'
POLICY = 'E25-D242-TRANSITION-ONLY-v1'
AUTH_SCHEMA = 'cpu-prefetch-stage17-transition-recovery-authorization/1'
TRANSITION_SCHEMA = 'cpu-prefetch-stage17-state-transition/2'
AUTH_ID = 'CPU-PREFETCH-V5-V25-D242-TRANSITION-AUTH-1'
TRANSITION_NAME = 'records/transition-003-d242-1.json'
BASE_NAME = 'journal/stage17-state-journal-000008.json'
NEXT_NAME = 'journal/stage17-state-journal-000009.json'
BASE_SHA = 'c014861b826c4d66c1707570a8b61dfacaaab6976d4eafe7629bca90fe3219c5'
FIXED = {
    'journal': (BASE_NAME, BASE_SHA),
    'failed_transition': ('records/transition-003.json', '4a173f1a14a2ee94911dabb0c78482052948688100722497be889d77e2864d0b'),
    'failed_candidate': ('journal/stage17-state-journal-000009.json.candidate', 'ebbe3e802c69c094a16f50d35f77e1187de76f94535e1a17d6368885c194062d'),
    'q15w_result': ('stage17-q15-w-result-v4.json', '9cb1632bc8a500879a987dc3603f256518b77f2d57adc6cebc1f940b3419ff67'),
    'q15w_completion': ('stage17-q15_w-completion-v4.json', 'afc31d56ef8e92ef53c70ffff68c4d21a9eebdb4c6af5f05943117de37447077'),
    'restoration': ('clock-qualification-v25-1/restoration.json', '4d7a5261523d24a3f7ce8429ad63f5d1d1b596770af5d642c2ab27ca9abadd0a'),
}
PREFIX_PATH = EVIDENCE.parent/'local-authoring-cpuprefetchv5-23/continuation-prefix-1/analysis4/accepted-prefix-manifest.json'
PREFIX_SHA = 'dc0580e84f4bfde9cc7287bd624013c76ba533a500c6e3de3ace49f1d3e3dded'
SELF_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise JournalError('D242: '+message)


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
    return core._external_bytes(Path('/'), str(path)[1:], 'D242 input')[1]


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
    require(document['schema_version'] == 'cpu-prefetch-stage17-d242-admin-manifest/1'
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
    require({'stage17_state_journal_v53.py', 'stage17_operational_cli_v19.py',
             'decision.md', 'approved-proposal.md', 'owner-acceptance.json'} <= names,
            'administrative closure is incomplete')
    require({p.name for p in ADMIN.iterdir()} == names | {'manifest.json'}, 'expanded admin directory')
    require(sha(read(ADMIN/'approved-proposal.md')) == PROPOSAL, 'approved proposal differs')
    approval = parse(read(ADMIN/'owner-acceptance.json'))
    require(approval['decision_id'] == 'D242' and approval['owner_message'] == 'approve'
            and approval['approved_proposal_sha256'] == PROPOSAL, 'recorded owner approval differs')
    return binding(path, raw)


def incident():
    bindings = {}
    documents = {}
    for role, (name, digest) in FIXED.items():
        raw = read(EVIDENCE/name)
        require(sha(raw) == digest, 'different incident: '+role)
        bindings[role] = binding(EVIDENCE/name, raw); documents[role] = parse(raw)
    raw = read(PREFIX_PATH); require(sha(raw) == PREFIX_SHA, 'accepted prefix differs')
    prefix = parse(raw)
    require(prefix['status'] == 'VALIDATED' and prefix['required_count'] == 177
            and [r['original_ordinal'] for r in prefix['records']] == list(range(177)), 'prefix incomplete')
    bindings['prefix'] = binding(PREFIX_PATH, raw)
    q = documents['q15w_result']; c = documents['q15w_completion']; r = documents['restoration']
    require(q['terminal_state'] == 'Q15_W_RESTORED_COMPLETE' and q['restoration_verified'] is True
            and q['quarantined'] is False, 'Q15-W was not successful')
    require(all(c[k] is True for k in ('leader_reaped', 'process_group_gone', 'restoration_verified'))
            and c['quarantined'] is False, 'Q15 cleanup incomplete')
    require(all(r[k] is True for k in ('verified', 'partition_absent', 'root_restoration_verified',
                                      'maintenance_restoration_verified')) and r['errors'] == [], 'infrastructure cleanup incomplete')
    return bindings, documents


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
    trust = resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role'] == 'OWNER', 'owner trust required')
    return dict(schema_version=AUTH_SCHEMA, authorization_id=AUTH_ID, policy_id=POLICY,
        actor=trust['measurements']['principal'], reviewer='OWNER', stand_id=trust['subject_id'],
        boot_id=BOOT, qualified_source_revision=SOURCE, qualified_worker_sha256=WORKER,
        administrative_manifest=admin_binding(), decision=binding(ADMIN/'decision.md'),
        owner_acceptance=binding(ADMIN/'owner-acceptance.json'), evidence_bindings=inputs,
        predecessor_resolutions=refs, target=dict(sequence_number=3, from_state=failed['from_state'],
            to_state=failed['to_state'], previous_transition_sha256=failed['previous_transition_sha256']),
        authority_scope='E25_D242_ADMINISTRATIVE_TRANSITION_ONLY', one_use=True,
        automatic_retries=0, execution_authority=False, phase18_authority=False)


def validate_authority(document, expected, at):
    require(set(document) == set(expected) | {'issued_at_utc', 'expires_at_utc'}, 'authority fields expanded/missing')
    require(canonical({k: document[k] for k in expected}) == canonical(expected), 'authority scope or bound evidence changed')
    issued = support._parse_utc(document['issued_at_utc']); expires = support._parse_utc(document['expires_at_utc'])
    sampled = support._parse_utc(at)
    require(expires-issued == dt.timedelta(seconds=1800) and issued <= sampled < expires,
            'fresh transition authority is future/expired or not1800seconds')


def make_transition(failed, authority, signature, timestamp):
    result = copy.deepcopy(failed)
    result.update(schema_version=TRANSITION_SCHEMA, transition_id='STAGE17-TRANSITION-003-D242-1',
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
    return dict(schema_version='cpu-prefetch-stage17-d242-consumption/1', policy_id=POLICY,
        consumed_at_utc=timestamp, authorization=authority, signature=signature,
        transition=transition, committed_journal=journal, automatic_retries=0, execution_authority=False)


def transitions(**arguments):
    refs = arguments['references']
    if len(refs) < 3 or refs[2]['path'] != TRANSITION_NAME:
        return core._transitions(**arguments)
    require(len(refs) == 3 and arguments['evidence_root'] == EVIDENCE
            and arguments['repository_root'] == REPOSITORY, 'recovery outside fixed E25 edge')
    prior = dict(arguments, references=refs[:2])
    state, previous = core._transitions(**prior)
    require(state == 'PREFLIGHT_ACCEPTED', 'historical transition prefix changed')
    path, document, digest = core._record(EVIDENCE, refs[2], 'D242 transition')
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
    # Full original semantic admission, immutable-prefix/fork checks and output
    # construction are retained. Historical transition code is never modified.
    function = types.FunctionType(core.validate_operational_journal.__code__,
        {**core.validate_operational_journal.__globals__, '_transitions': transitions},
        argdefs=core.validate_operational_journal.__defaults__)
    function.__kwdefaults__ = core.validate_operational_journal.__kwdefaults__
    return function(**arguments)


def activate():
    predecessor.activate()
    predecessor.validate_operational_journal = validate_operational_journal


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
            EVIDENCE/'journal/stage17-state-journal-000009.d242-candidate', TRANSACTION/'consumption.json')),
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
    candidate = EVIDENCE/'journal/stage17-state-journal-000009.d242-candidate'
    write_exclusive(candidate, journal_raw)
    validation = validate_operational_journal(repository_root=REPOSITORY, evidence_root=EVIDENCE,
        latest_journal=candidate, journal_directory=EVIDENCE/'journal', pilot_archive=archive,
        pilot_sidecar=sidecar, as_of_utc=support._now(), allow_synthetic_test_evidence=False)
    require(validation.current_state == 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
            and validation.transition_count == 3 and not validation.pilot_ready, 'recovered transition did not validate')
    validate_authority(document, expected, support._now())
    write_exclusive(EVIDENCE/NEXT_NAME, journal_raw)
    return receipt
