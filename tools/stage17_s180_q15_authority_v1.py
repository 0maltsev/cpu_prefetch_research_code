"""Signed scoped Q15-R/W requests for the current S180 qualification worker.

The qualified parent supplies independently derived context and authenticated
original-seven replay. This module verifies neither that parent's package nor
live Q15 evidence. Its immutable result is not a launch/EXT008 ticket. No CLI,
worker dispatch, key selection, signer invocation or legacy-policy mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

import stage17_formal_archive_v1 as archive
import stage17_s180_authority_v1 as pilot
import stage17_s180_environment_v1 as environment
import stage17_s180_resource_admission_v1 as resources
import stage17_output_registry_v4 as carrier

SCHEMA='cpu-prefetch-stage17-s180-q15-authorization/1'
CONTEXT_SCHEMA='cpu-prefetch-stage17-s180-q15-input-context/1'
RELEASE_ID='D310-S180-Q15-QUALIFIED-PROFILE-v1'
ROOT=environment.EVIDENCE.parent/'q15-qualification'
ROLE='STAGE17_FIXED_ACTION_WORKER'
PROFILE='STAGE17-FIXED-ACTION-WORKER-v4'
LIMIT=1024**2
COMMON=('plan_sha256 window_binding qualification_started_monotonic_ns '
    'qualification_deadline_monotonic_ns evidence_root_binding runtime_binding release_binding '
    'action_inputs session_id qualification_id stand_id action_id').split()
AUTH_FIELDS=set(COMMON)|set(('schema_version authorization_id request_id attempt_id actor trust_context '
    'base_resolutions issued_at_epoch_seconds expires_at_epoch_seconds permission_scope '
    'synthetic_test_only phase18_authority').split())
PERMISSIONS=dict(q15_r_max=1,q15_w_max=1,same_process_and_buffer=True,automatic_retry=False,
    reset_window=False,pilot_execution=False,replace_completed_calibration=False,stage18_execution=False)
require=pilot.require
same=pilot.same
fields=pilot.fields


def _opaque(value,label):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}',value) is not None,
        'Q15 '+label+' requires a bounded native identity')


def _inputs(context):
    """Check fixed method/shape; observed values still come from the parent."""
    value=context['action_inputs'];action=context['action_id']
    if action=='Q15-R':
        fields(value,{'qualification_id','attempt_id','session_id','probe_platform_binding'},'Q15-R inputs')
        same(value['qualification_id'],context['qualification_id'],'Q15 qualification identity')
        binding=value['probe_platform_binding']
        fields(binding,{'cpu','numa_node','verified_local_llc_bytes','verified_base_page_bytes'},'observed Q15 probe platform')
        same(binding['cpu'],0,'Q15 probe CPU');same(binding['numa_node'],0,'Q15 probe node')
        same(binding['verified_base_page_bytes'],4096,'Q15 observed page geometry')
        llc=archive.uint(binding['verified_local_llc_bytes'],'observed local LLC',positive=True)
        require(llc%4096==0,'Q15 observed LLC must cover whole accepted base pages')
        _opaque(value['attempt_id'],'R input attempt')
    else:
        require(action=='Q15-W','only Q15-R or Q15-W is in scope')
        fields(value,{'q15_r_attempt_sha256','q15_r_result_sha256','session_id','prestate'},'Q15-W inputs')
        for name in ('q15_r_attempt_sha256','q15_r_result_sha256'):archive.sha(value[name],name)
        rows=value['prestate']
        require(type(rows) is list and len(rows)==3,'Q15-W full three-CPU prestate required')
        for cpu,row in zip((0,1,8),rows,strict=True):
            fields(row,{'cpu','complete_value_hex'},'Q15-W prestate row')
            same(row['cpu'],cpu,'Q15-W accepted CPU order')
            require(type(row['complete_value_hex']) is str
                and re.fullmatch('[0-9a-f]{16}',row['complete_value_hex']) is not None,
                'Q15-W complete original prestate requires fixed-width hex')
            require(int(row['complete_value_hex'],16)&15==0,'Q15-W expected original H0 disable bits differ')
    same(value['session_id'],context['session_id'],'same-buffer session')


def _context(value):
    """Shape/scope only; never constructs an independently qualified producer."""
    raw=archive.canonical(value);require(len(raw)<=LIMIT,'Q15 context byte limit')
    value=archive.parse_json(raw)
    fields(value,set(COMMON)|{'schema_version','phase18_authority'},'independent Q15 context')
    require(value['schema_version']==CONTEXT_SCHEMA and value['phase18_authority'] is False,
        'separately scoped Q15 context required')
    for name in ('session_id','qualification_id','stand_id'):_opaque(value[name],name)
    archive.sha(value['plan_sha256'],'S180 plan')
    window=value['window_binding']
    fields(window,{'boot_id','start_monotonic_ns','end_monotonic_ns'},'original S180 window')
    pilot.opaque(window['boot_id'],'original boot')
    start=archive.uint(window['start_monotonic_ns'],'window start',positive=True)
    end=archive.uint(window['end_monotonic_ns'],'window end',positive=True)
    begin=archive.uint(value['qualification_started_monotonic_ns'],'qualification start',positive=True)
    deadline=archive.uint(value['qualification_deadline_monotonic_ns'],'qualification end',positive=True)
    require(end-start==pilot.DAY_NS and start<=begin<deadline<=end
        and deadline-begin<=environment.resources.EXTERNAL_TIME['qualification_ns'],
        'Q15 must preserve the original qualification and operational budgets')
    root=value['evidence_root_binding']
    fields(root,{'absolute_path','device','inode','owner_uid','mode'},'Q15 output root')
    same(root['absolute_path'],str(ROOT),'fixed Q15 namespace')
    archive.uint(root['device'],'Q15 output device',positive=True);archive.uint(root['inode'],'Q15 output inode',positive=True)
    same(root['owner_uid'],0,'Q15 output root owner');same(root['mode'],'0700','Q15 output root protection')
    runtime=value['runtime_binding']
    fields(runtime,{'role','profile','sha256','size_bytes'},'current Q15 runtime')
    same(runtime,dict(role=ROLE,profile=PROFILE,sha256=resources.NATIVE_SHA,size_bytes=resources.NATIVE_SIZE),
        'current frozen Q15 worker')
    release=value['release_binding']
    fields(release,{'source_resolution_id','source_resolution_sha256','artifact_role','runtime_profile',
        'worker_size_bytes','worker_sha256','source_revision'},'separate Q15 qualification release')
    same(release['source_resolution_id'],RELEASE_ID,'Q15 profile leaf identity')
    archive.sha(release['source_resolution_sha256'],'independently qualified operator/profile')
    same(release['source_revision'],environment.NATIVE_REVISION,'frozen Q15 source revision')
    for key,actual in (('artifact_role',runtime['role']),('runtime_profile',runtime['profile']),
        ('worker_size_bytes',runtime['size_bytes']),('worker_sha256',runtime['sha256'])):
        same(release[key],actual,'Q15 release '+key)
    _inputs(value)
    return value


@dataclass(frozen=True)
class VerifiedQ15Request:
    authorization_bytes:bytes
    request_bytes:bytes

    def request(self):
        # Original native v4 result validation hashes this legacy JSON+LF
        # carrier. The separately signed S180 authorization remains JCS-I64.
        require(self.request_bytes.endswith(b'\n'),'original Q15 request terminator required')
        value=archive.parse_json(self.request_bytes[:-1])
        require(carrier.canonical(value)==self.request_bytes,'original Q15 request encoding differs')
        return value

    def native_context(self,*,fixed_action_definition_sha256):
        """Native v4 carrier only; the parent must pin this definition first."""
        archive.sha(fixed_action_definition_sha256,'qualified fixed action definition')
        authorization=archive.parse_json(self.authorization_bytes)
        request=self.request()
        return dict(schema_version='cpu-prefetch-stage17-fixed-action-context/4',
            **{k:request[k] for k in ('authorization_id','request_id','session_id','attempt_id','action_id')},
            authorization_sha256=pilot.sha(self.authorization_bytes),request_sha256=pilot.sha(self.request_bytes),
            fixed_action_definition_sha256=fixed_action_definition_sha256,
            runtime_sha256=request['runtime_binding']['sha256'],release_sha256=request['release_binding']['worker_sha256'],
            predecessor_sha256s=[r['sha256'] for r in request['predecessor_resolutions']],
            issued_at_epoch_seconds=authorization['issued_at_epoch_seconds'],
            expires_at_epoch_seconds=authorization['expires_at_epoch_seconds'],
            per_run_deadline_seconds=180,synthetic_test_only=False,phase18_authority=False)

    def proof(self):
        return dict(schema_version='cpu-prefetch-stage17-s180-q15-signature-proof/1',
            authorization_sha256=pilot.sha(self.authorization_bytes),request_sha256=pilot.sha(self.request_bytes),
            signature_verified=True,qualified_parent_replay_performed=False,attempt_consumed=False,
            execution_authority=False,full_qualification=False,phase18_authority=False)


def verify_authorization(*,authorization_bytes,signature_path,qualification_context,base_validation):
    """Verify exact owner signature against a separately derived live context.

    Context is qualified code's input, never copied from authorization data.
    The future parent must independently verify source/profile/platform, clocks,
    live R/W lineage, output inode and remaining time before any native dispatch.
    """
    require(type(authorization_bytes) is bytes and 0<len(authorization_bytes)<=LIMIT,'Q15 authorization byte bound')
    context=_context(qualification_context);value=archive.parse_json(authorization_bytes)
    fields(value,AUTH_FIELDS,'scoped Q15 authorization')
    require(value['schema_version']==SCHEMA and value['synthetic_test_only'] is False
        and value['phase18_authority'] is False,'current production scoped Q15 authority required')
    for name in COMMON:same(value[name],context[name],'independently derived Q15 '+name)
    for name in ('authorization_id','request_id','attempt_id'):_opaque(value[name],name)
    if value['action_id']=='Q15-R':same(value['action_inputs']['attempt_id'],value['attempt_id'],'Q15-R input attempt')
    same(value['permission_scope'],PERMISSIONS,'Q15-only permissions')
    resolutions=base_validation.resolutions
    require(set(resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,8)},'exact authenticated original seven required')
    expected=[pilot.binding(resolutions[f'S17-EXT-{i:03d}']) for i in range(1,8)]
    for i,row in enumerate(expected,1):
        same(row['input_id'],f'S17-EXT-{i:03d}','original input identity')
        archive.sha(row['sha256'],'original resolution')
    same(value['base_resolutions'],expected,'preserved original resolutions')
    same(value['stand_id'],resolutions['S17-EXT-002'].semantic_context['stand_id'],'original stand identity')
    same(value['trust_context'],dict(ext002_resolution=expected[1],ext003_resolution=expected[2]),'original owner trust')
    trust=resolutions['S17-EXT-003'].semantic_context['trust']
    same(value['actor'],trust['measurements']['principal'],'admitted Q15 signer')
    prior=resolutions['S17-EXT-007'].semantic_context
    require(prior.get('data_provenance_accepted') is True and prior.get('legacy_statistical_freeze_satisfied') is False,
        'descriptive calibration scope required')
    pilot.signatures._verify_signature(authorization_bytes,Path(signature_path),trust)
    issued=archive.uint(value['issued_at_epoch_seconds'],'Q15 issue',positive=True)
    expires=archive.uint(value['expires_at_epoch_seconds'],'Q15 expiry',positive=True)
    epoch=time.time_ns()//10**9;now=time.monotonic_ns();window=context['window_binding']
    require(window['boot_id']==environment._boot() and window['start_monotonic_ns']
        <=context['qualification_started_monotonic_ns']<=now
        <context['qualification_deadline_monotonic_ns'] and issued<=epoch<expires,
        'Q15 original boot/window/authority is not live')
    require((expires-epoch-1)*10**9>=context['qualification_deadline_monotonic_ns']-now,
        'Q15 authority does not conservatively cover the original qualification deadline')
    request={key:value[key] for key in ('request_id','session_id','action_id','stand_id','authorization_id','attempt_id',
        'runtime_binding','evidence_root_binding','action_inputs','synthetic_test_only','phase18_authority')}
    request['schema_version']='cpu-prefetch-stage17-fixed-action-request/4'
    # The native v4 carrier has six release fields. The independently qualified
    # profile leaf is NOT an original EXT003 journal resolution or its old image.
    request['release_binding']={k:v for k,v in context['release_binding'].items() if k!='source_revision'}
    request['predecessor_resolutions']=expected
    return VerifiedQ15Request(authorization_bytes,carrier.canonical(request))
