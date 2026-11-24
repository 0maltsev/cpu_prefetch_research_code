"""D306: one approved continuation of the unused, registered Q16c request.

Historical operators and signed files remain unchanged. Native/scientific
execution is inherited unchanged; only stopped-state admission and paths differ.
"""
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import time
import types

import stage17_q16c_saved_request_v1 as saved

PROPOSAL_SHA = '97928f7779b8d2de60a3a8c9eb6f1b67634891d7b8454683ef90d2609a16fc75'
SAVED_SHA = '8611cfef3e36f0b35653c577f21a0341c442d0bbc5e82e24a52fd0de4007827f'
STOPPED_CONFIGURATION_SHA = '7211b3618a386cd45ea095888cbaaac9e4a64002288bec37070ab98ff604987b'
STOPPED_AUTH_SHA = 'd79d9be2fbcd86e4aebf953fdea4ee6f4e3a4a760ec9ba1107c29e3aa42e6b70'
STOPPED_SIGNATURE_SHA = '3a40999a3845e004c3ae7d83034649200c44cd2c4b512c416129ad286b2eb18a'
STOPPED_PREPARED_SHA = 'dd9a57a78c6030c0275e60ac369c294eba88b693788d13f1e29ae1239e9c402a'
STOPPED_RESULT_SHA = 'c335a071f68889ab3d586718450bcd227ae678464007d32652f3b7c553485a43'
STOPPED_RECOVERY_SHA = '101a970321ff3f9a829e47be60e43920679d4a75c97cb32932c270d4e744cc82'
E, ENVELOPE, NATIVE_SOURCE = saved.E, saved.ENVELOPE, saved.NATIVE_SOURCE
ORIGINAL_DEADLINE, SIGNED_DAY_DEADLINE = saved.ORIGINAL_DEADLINE, saved.SIGNED_DAY_DEADLINE
require = saved.require


def parent_verified():
    saved.parent_verified()
    require(hashlib.sha256(Path(saved.__file__).read_bytes()).hexdigest() == SAVED_SHA,
            'exact repaired D305 administrative parent')


def validate_acceptance(value):
    expected = dict(decision_id='D306', owner_message='approve', exact_decision_text_approved=True,
        recorded_decision_sha256=PROPOSAL_SHA, new_execution_windows=0, manual_continuations=1,
        automatic_retry=False, repeat_qualification=False, repeat_completed_measurements=False,
        repeat_completed_raw_validations=False, reused_capture_count=86, remaining_capture_count=94,
        maximum_remaining_seconds=31460, admitted_day_deadline_monotonic_ns=SIGNED_DAY_DEADLINE,
        latest_start_monotonic_ns=SIGNED_DAY_DEADLINE-ENVELOPE, phase18_authority=False)
    for key, item in expected.items():
        require(type(value.get(key)) is type(item) and value[key] == item, 'exact D306 approval '+key)


def runtime_deadline(c=None):
    if c is None:
        return ORIGINAL_DEADLINE
    import stage17_q16c_continuation_operator_v1 as io
    require(c['continuation_decision'] == 'D306', 'D306 continuation scope')
    require(hashlib.sha256(io.read(c['continuation_authority']['proposal'])).hexdigest() == PROPOSAL_SHA,
            'exact D306 proposal')
    validate_acceptance(io.document(c['continuation_authority']['acceptance']))
    require(saved.runtime_deadline(c) == SIGNED_DAY_DEADLINE, 'retained D302 signed-day proof')
    return SIGNED_DAY_DEADLINE


def check_time(now, c=None):
    require(type(now) is int and 0 < now < runtime_deadline(c)-ENVELOPE,
            'complete31460s envelope must fit inside the admitted original signed day')


def _function(original, replacements=()):
    """Retain the pinned implementations, replacing explicit administrative seams."""
    parent_verified()
    text = inspect.getsource(original)
    for old, new in replacements:
        text = saved.previous.replace_once(text, old, new)
    namespace = {**saved.__dict__, **globals()}
    exec(compile(text, __file__+':'+original.__name__, 'exec'), namespace)
    return namespace[original.__name__]


def verify_supplement(c, trust):
    import stage17_q16c_continuation_operator_v1 as io
    from stage17_phase_controller_v2 import _verify_signature
    saved.verify_supplement(c, trust)
    old = io.document(c['stopped_configuration'])
    proof = old['continuation_authority']
    require(hashlib.sha256(io.read(proof['proposal'])).hexdigest() == saved.PROPOSAL_SHA,
            'retained D301 proposal')
    raw = io.read(proof['acceptance']); saved.validate_acceptance(json.loads(raw))
    io.read(proof['signature'])
    _verify_signature(raw, Path(proof['signature']['path']), trust)


def validate_handoff(c, validation=None):
    import stage17_q16c_continuation_operator_v1 as io
    old = io.document(c['stopped_configuration'])
    require(c['stopped_configuration']['sha256'] == STOPPED_CONFIGURATION_SHA, 'exact consumed D301 configuration')
    require(c['original_preconstruction'] == old['preconstruction'], 'original constructor identity')
    require(io.read(c['original_preconstruction']) == io.read(c['preconstruction']), 'byte-identical relocated wrapper')
    for key in ('saved_request', 'authorization_template', 'authorization_schema', 'family_registration',
                'program_root', 'packet_root', 'repository_root', 'source_revision', 'worker', 'candidate_inventory',
                'window_proof', 'deadline_supplement', 'latest_result', 'latest_recovery'):
        require(c[key] == old[key], 'unchanged stopped binding '+key)
    stopped = c['stopped_handoff']
    for role, digest in (('prepared', STOPPED_PREPARED_SHA), ('authorization', STOPPED_AUTH_SHA),
                         ('signature', STOPPED_SIGNATURE_SHA)):
        require(stopped[role]['sha256'] == digest, 'exact stopped '+role)
        io.read(stopped[role])
    prepared = io.document(stopped['prepared'])
    require(prepared['authorization'] == stopped['authorization'] and prepared['signature'] == stopped['signature']
            and prepared['request'] == c['saved_request'] and prepared['worker'] == c['worker'],
            'preserved signed handoff relationship')
    require(stopped['result']['sha256'] == STOPPED_RESULT_SHA and stopped['recovery']['sha256'] == STOPPED_RECOVERY_SHA,
            'exact stopped result and independent recovery bytes')
    result = io.document(stopped['result']); recovery = io.document(stopped['recovery'])
    require(result['success'] is False and [p['role'] for p in result['phases']] == ['authorize', 'sign-collect']
            and [p['exit_code'] for p in result['phases']] == [0, 1]
            and all(p['leader_reaped'] is True for p in result['phases'])
            and result['partition_restoration']['verified'] is True and 'native_terminal' not in result
            and recovery['verified'] is True and recovery['errors'] == [], 'exact restored pre-native handoff stop')
    out = Path(c['output_root']); ops = Path(c['operator_sources'][Path(__file__).name]['path']).parent
    require(out == ops/'runtime-output' and c['operational_authorization_path'] == str(ops/'authorization.json'),
            'distinct bound D306 administrative output paths')
    require(out != Path(old['output_root']) and not out.is_symlink()
            and io.binding(out/'constructed.json') == c['preconstruction'], 'fresh wrapper at exact output path')
    require(not (out/'prepared.json').exists() and not Path(c['operational_authorization_path']).exists()
            and not Path(c['operational_authorization_path']+'.sig').exists(), 'unused fresh operational authority')
    request = io.document(c['saved_request']); family = Path(request['evidence_root_binding']['absolute_path'])
    require(not family.is_symlink() and not list(family.iterdir()), 'no consumed native attempt or output')


def validate_saved_state(c, validation):
    old = """    require(not (Path(c['output_root'])/'prepared.json').exists()
            and not (Path(c['saved_request']['path']).parent/'authorization.json').exists()
            and not (Path(c['saved_request']['path']).parent/'authorization.json.sig').exists(),
            'no consumed operational authority')"""
    return _function(saved.validate_saved_state, [(old, '    validate_handoff(c,validation)')])(c, validation)


def owner_journal(configuration, digest, *, software_check=False):
    import stage17_q16c_continuation_operator_v1 as io
    require(os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups(), 'actual evidence owner')
    c = io.document(dict(path=str(configuration), size_bytes=Path(configuration).stat().st_size, sha256=digest))
    metadata = _function(saved._metadata_function, [("== 'D301'", "== 'D306'")])()
    return metadata(types.SimpleNamespace(configuration_sha256=digest, software_check=software_check), c)


def admit(args, c, *, software_check=False):
    return _function(saved.admit, [('d301-execution-owner-', 'd306-execution-owner-')])(args, c, software_check=software_check)


def prepare_authorization(c, deadline):
    validate_handoff(c)
    return _function(saved.prepare_authorization, [
        ("path=Path(c['saved_request']['path']).parent/'authorization.json'", "path=Path(c['operational_authorization_path'])")
    ])(c, deadline)


def render(name, raw):
    parent_verified()
    text = saved.render(name, raw).decode().replace('d301', 'd306').replace('D301', 'D306')
    text = text.replace('stage17_q16c_saved_request_v1', 'stage17_q16c_handoff_continuation_v1')
    ast.parse(text, filename=name)
    return text.encode()


def render_isolation():
    parent_verified()
    return saved.render_isolation().replace(b'd301', b'd306').replace(b'D301', b'D306')


if __name__ == '__main__':
    require(len(sys.argv) == 4 and sys.argv[1] in ('--owner-journal', '--owner-journal-check'), 'metadata-only owner entry')
    print(json.dumps(owner_journal(Path(sys.argv[2]), sys.argv[3], software_check=sys.argv[1].endswith('-check'))), flush=True)
