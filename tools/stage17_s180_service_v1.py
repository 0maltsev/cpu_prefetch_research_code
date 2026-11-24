"""Fixed stand service entry; authenticate software before importing controllers.

The external installer pins profile.json's digest in the loaded systemd unit.
The profile contains source bindings only, never commands, keys or permission.
Only `run` begins the once-only operational window. `check` is read-only except
for a disposable, non-JSON offline signer challenge. No retry/adoption exists.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import ctypes
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time

PACKAGE=Path('/opt/cpu-prefetch-s180-service-1')
COMMON=Path('/opt/cpu-prefetch-s180-common-0919b87-1')
NATIVE_SOURCE=Path('/opt/cpu-prefetch-s180-native-sources-34247ce-1')
ARCHIVE=Path('/home/omaltsev/stage17-owner-evidence/s180-archive-component-877271c-stand-1')
RUN=Path('/run/cpu-prefetch-s180-operator-1')
PYTHON=Path('/usr/bin/python3.14')
PYTHON_SHA='52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41'
COMMON_SHA='bccde38abc2d97181f20100e18a2f5e1e8e62e4d41683c8ec497fb4d63fbcd7d'
SOURCE_SHA='bd86f1b81686ab119607868cb64f94f6617e620fa82e93750b9877e6ba1c578b'
PROFILE_SCHEMA='cpu-prefetch-stage17-s180-service-source-profile/1'
SUPPORT=('clean-support-build.json','gcc-clean-software_prefetch_t0_mapping_codegen_report.json',
    'clang-clean-software_prefetch_t0_mapping_codegen_report.json','gcc-probe','gcc-mutant','clang-probe','clang-mutant')
RELOCATED=('tools/stage17_s180_qualification_evidence_v1.py',
    'tools/software_prefetch_mapping_codegen_probe.cpp','tools/software_prefetch_mapping_codegen_mutant.cpp',
    'tools/check_software_prefetch_mapping_codegen.py','config/schemas/qualification-evidence-v3.schema.json')
HEADER='include/cpu_prefetch/runner/software_prefetch.hpp'
MEMBERS=frozenset(('stage17_s180_service_v1.py','tools/stage17_s180_execution_v1.py',
    'tools/stage17_s180_family_analysis_v1.py','tools/stage17_s180_exit_v1.py','stop_post.py',
    'metadata-timing.json',HEADER,*RELOCATED,*('support/'+name for name in SUPPORT)))
NS=10**9
GIB=1024**3


def require(ok,message):
    if not ok:raise RuntimeError('S180 service: '+message)


def _read(path,maximum):
    require(path.is_absolute() and path.resolve(strict=True)==path,'canonical software file required')
    for parent in path.parents:
        s=parent.stat(follow_symlinks=False)
        require(stat.S_ISDIR(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022,'unprotected software ancestor')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        s=os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1
            and not s.st_mode&0o022 and 0<=s.st_size<=maximum,'unprotected or oversized software file')
        with os.fdopen(os.dup(fd),'rb') as stream:raw=stream.read(maximum+1)
        after=os.fstat(fd);named=path.stat(follow_symlinks=False)
        stamp=lambda row:(row.st_dev,row.st_ino,row.st_size,row.st_mtime_ns,row.st_ctime_ns,row.st_nlink)
        require(len(raw)==s.st_size and stamp(s)==stamp(after)==stamp(named),'software bytes changed during read')
        return raw
    finally:os.close(fd)


def _manifest(root,name,digest):
    raw=_read(root/name,2*1024**2)
    require(hashlib.sha256(raw).hexdigest()==digest,'externally pinned source manifest differs')
    document=json.loads(raw);seen=set()
    require(type(document.get('files')) is list and len(document['files'])<=10000,'bounded source inventory required')
    for row in document['files']:
        relative=row['path'];path=Path(relative)
        require(type(relative) is str and relative==str(path) and not path.is_absolute()
            and '..' not in path.parts and relative not in seen and relative!='.','unsafe or duplicate source member')
        seen.add(relative);data=_read(root/path,256*1024**2)
        require(len(data)==row['size_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],
            'source member bytes differ: '+relative)
    require(_inventory(root)==seen|{name},'unexpected or missing software package member')
    return document,seen


def _inventory(root):
    files=set();count=0
    for current,dirs,names in os.walk(root,followlinks=False):
        for name in (*dirs,*names):
            path=Path(current)/name;s=path.stat(follow_symlinks=False);count+=1
            require(count<=20000 and s.st_uid==0 and not s.st_mode&0o022
                and (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)),'unsafe software inventory')
            if stat.S_ISREG(s.st_mode):files.add(str(path.relative_to(root)))
    return files


def authenticate(expected):
    require(os.getresuid()==(0,0,0),'full root service required')
    require(type(expected) is str and len(expected)==64 and all(c in '0123456789abcdef' for c in expected),
        'external exact profile digest required')
    require(Path(__file__).resolve(strict=True)==PACKAGE/'stage17_s180_service_v1.py','fixed service source location required')
    profile,seen=_manifest(PACKAGE,'profile.json',expected)
    require(set(profile)=={'schema_version','source_revision','files'} and profile['schema_version']==PROFILE_SCHEMA
        and seen==MEMBERS,'exact qualified service profile fields/membership required')
    revision=profile['source_revision']
    require(type(revision) is str and len(revision)==40 and all(c in '0123456789abcdef' for c in revision),
        'clean component source revision required')
    require(hashlib.sha256(_read(PYTHON,16*1024**2)).hexdigest()==PYTHON_SHA,'accepted actual interpreter required')
    _manifest(COMMON,'S180_COLD_SOURCE_MANIFEST.json',COMMON_SHA)
    _manifest(NATIVE_SOURCE,'FROZEN_SOURCE_MANIFEST.json',SOURCE_SHA)
    for relative in RELOCATED:
        require(_read(PACKAGE/relative,2*1024**2)==_read(COMMON/relative,2*1024**2),
            'relocated qualification source differs: '+relative)
    require(_read(PACKAGE/HEADER,65536)==_read(NATIVE_SOURCE/HEADER,65536),'original emitter header differs')
    sys.path[:0]=[str(PACKAGE/'tools'),str(COMMON/'tools')]
    import stage17_s180_execution_v1 as execution
    import stage17_s180_exit_v1 as exit_check
    for module in (execution,execution.analysis,execution.qualification,exit_check):
        require(Path(module.__file__).resolve(strict=True).parent==PACKAGE/'tools','controller overlay was not loaded')
    require(execution.SCHEMA.endswith('/2') and execution.analysis.SCHEMA.endswith('/4'),
        'qualified current controller/epoch versions required')
    require(_read(PACKAGE/'stop_post.py',4096)==execution.compaction.stop_post_script(),'fixed recovery entry bytes required')
    return profile,execution,exit_check


def analysis_budget(timing):
    """Measured projections plus explicit allowances; never a runtime guarantee."""
    require(timing['status']=='SOFTWARE_METADATA_TIMING_PASS' and timing['scientific_captures_collected']==0
        and timing['original_research_raw_bytes_read']==0 and timing['operational_window_started'] is False,
        'actual software-only metadata measurement required')
    observed=sum(timing[key] for key in ('original_header_receipt_metadata_180_repeated_same_capture_ns',
        'synthetic_family_roundtrip_ns','synthetic_complete_family_consistency_ns'))
    require(observed==timing['total_measured_metadata_components_ns'] and observed>0 and 3*observed<60*NS,
        'metadata measurement no longer fits its explicit60-second allowance')
    # D359 observed linear projections, not newly invented platform values.
    primary=4673412436309;pages=440992782339;context=19529296447
    # Original31.016-second replay scaled for all9016 prospective extra records
    # is below35 seconds. This is an estimate with the existing finite cap.
    old_replay=31016034928
    require(old_replay*(79869+9016)<=35*NS*79869,'prospective ledger projection exceeds allowance')
    total=primary+pages+context+35*NS+120*NS+60*NS
    require(total<=5400*NS,'whole analysis estimate exceeds approved90-minute cap')
    return dict(primary_projection_ns=primary,page_projection_ns=pages,context_projection_ns=context,
        prospective_ledger_allowance_ns=35*NS,final_environment_allowance_ns=120*NS,
        metadata_allowance_ns=60*NS,measured_metadata_ns=observed,estimated_analysis_ns=total,
        analysis_cap_ns=5400*NS,estimated_analysis_margin_ns=5400*NS-total,
        estimated_whole_run_ns=(24480+23004+5400+1800+1800+600)*NS,
        operational_cap_ns=86400*NS,estimate_is_guarantee=False,execution_authority=False)


def _census(execution,deadline):
    base=execution.ROOT.parent.parent;programme=execution.PROGRAM
    excluded=[base/'local-authoring-cpuprefetchv5-19'/name for name in ('discovery-output-1','discovery-output-r2-1')]
    excluded.append(base/'local-authoring-cpuprefetchv5-20/discovery-output-r3-1')
    charged=0;seen=set();count=0;device=base.stat().st_dev
    def excluded_path(path):
        if any(path==root or root in path.parents for root in excluded):return True
        if path==programme or programme in path.parents:
            return not any(path==programme/name or programme/name in path.parents for name in ('working','spool','hold'))
        return False
    for current,dirs,files in os.walk(base,followlinks=False):
        for name in (*dirs,*files):
            path=Path(current)/name;s=path.stat(follow_symlinks=False);count+=1
            require(count<=500000 and time.monotonic_ns()<deadline,'retained metadata census limit exceeded')
            require(s.st_dev==device,'retained census crosses an unclassified filesystem')
            require(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode),
                'unclassified retained evidence object')
            if excluded_path(path):continue
            identity=(s.st_dev,s.st_ino)
            if identity in seen:continue
            seen.add(identity);charged+=max(s.st_size,512*s.st_blocks)
    require(charged<=88*GIB,'fresh retained census exceeds explicit D362 W/S commitment')
    return dict(objects_scanned=count,charged_extent_upper_bytes=charged,requested_commitment_bytes=88*GIB,
        payload_bytes_read=0)


def _signer_check(execution,base,deadline):
    # Non-JSON/non-authorizing challenge, exclusively owned disposable software.
    with tempfile.TemporaryDirectory(prefix='cpu-prefetch-s180-sign-readiness-',dir='/run') as temporary:
        path=Path(temporary)/'challenge';path.write_bytes(b'SOFTWARE SIGNER READINESS; NO EXECUTION AUTHORITY\n'+os.urandom(32))
        path.chmod(0o600)
        result=subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(execution.KEY),'-n',execution.NAMESPACE,str(path)],
            stdin=subprocess.DEVNULL,capture_output=True,timeout=min(30,(deadline-time.monotonic_ns())/NS),
            env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        require(result.returncode==0 and len(result.stdout)<=16384 and len(result.stderr)<=16384,'offline signer unavailable')
        execution.authority.signatures._verify_signature(path.read_bytes(),Path(str(path)+'.sig'),
            base.resolutions['S17-EXT-003'].semantic_context['trust'])


def preflight(execution,profile):
    deadline=time.monotonic_ns()+600*NS
    require(not os.path.lexists(execution.ROOT),'original operational root already exists; never adopt/retry')
    sizing=execution.archive.parse_json(_read(COMMON/execution.author.SIZING_PATH,4*1024**2))
    execution.author.requirements(sizing)
    e=execution.ROOT.parent
    name='cpu-prefetch-pilot-candidate-2.0.0-7b7c263-clean-5e100e05e49b.tar.gz'
    arguments=dict(repository_root=e/'admission-root',evidence_root=e,latest_journal=e/'journal/stage17-state-journal-000010.json',
        journal_directory=e/'journal',pilot_archive=e.parent/name,pilot_sidecar=e.parent/(name+'.sha256'))
    base=execution.original.verify_original(base_replay_arguments=arguments,deadline_ns=deadline)
    import stage17_s180_archive_bundle_profile_v1 as bundle
    bundle.verify_package(bundle_root=ARCHIVE,runtime_root=Path('/'),expected_manifest=dict(path=bundle.MANIFEST_PATH,
        size_bytes=5941,sha256='5ac1524cc557d57d4d7216949812c875be8c8e5b3e7b976d7b9f4a33f688973c'))
    archive_profile=bundle.load_profile(bundle_root=ARCHIVE,runtime_root=Path('/'),expected=execution.archive.PhysicalBinding(
        7058,sizing['storage']['implementation_profile_sha256']),deadline_ns=deadline)
    release=COMMON/'frozen-native-release'
    def image(name,size,sha):return execution.runtime.ImageBinding(release/name,size,sha)
    native=image('cpu_prefetch_runner',execution.compaction.NATIVE_SIZE,execution.compaction.NATIVE_SHA)
    clock=image('cpu_prefetch_q15_clock_qualification_tool',execution.compaction.CLOCK_SIZE,execution.compaction.CLOCK_SHA)
    helper=image('cpu_prefetch_q15_qualification_evidence_tool',execution.qualification.HELPER_SIZE,execution.qualification.HELPER_SHA)
    for current in (native,clock,helper):execution.runtime._image_bytes(current,deadline)
    execution.qualification._codegen(PACKAGE/'support')
    for row in sizing['hardware']['prestate']:
        fd,_=execution.environment._open_msr(row['cpu'])
        try:require(execution.environment._read_msr(fd)==row['value'],'current hardware prestate differs')
        finally:os.close(fd)
    budget=analysis_budget(json.loads(_read(PACKAGE/'metadata-timing.json',65536)))
    census=_census(execution,deadline)
    report=execution.author.planning.native_layouts(sizing,worker=native,deadline_ns=deadline)
    codec=ctypes.CDLL(str(archive_profile.decoder.zstd_library_path))
    codec.ZSTD_compressBound.argtypes=[ctypes.c_size_t];codec.ZSTD_compressBound.restype=ctypes.c_size_t
    bounded,envelope=execution.budgets.bound_packet(sizing,report,compress_bound=codec.ZSTD_compressBound)
    require(bounded==sizing,'exact prospective sizing differs from cold native')
    process=execution.budgets.process_envelope(sizing,report,envelope)
    timing=execution.budgets.time_envelope(sizing,report)
    require(timing['total_declared_stage_caps_ns']==85681*NS,'unchanged declared stage caps required')
    native_limits,limits,_,_=execution._limits(sizing,archive_profile,deadline)
    observation=execution.resources.platform_observation()
    execution.resources.assess_platform(observation,process_envelope=process,native_limits=native_limits)
    execution.phase.assess_memory(observation)
    declaration=json.loads(_read(COMMON/'config/stage17/d362-s180-storage-commitments-v1.json',65536))
    unrelated={key:declaration[key] for key in ('reserved_bytes','reserved_inodes','workspace_committed_bytes','scratch_committed_bytes')}
    unrelated['declaration_sha256']=execution.DECLARATION_SHA
    space,records,files=execution.resources.capacity_plan(sizing,envelope,limits,
        workspace_committed_bytes=unrelated['workspace_committed_bytes'],scratch_committed_bytes=unrelated['scratch_committed_bytes'])
    with execution.stores.ProgramStore(execution.PROGRAM,scope_sha256=sizing['storage']['program_scope_sha256'],family_id='0'*64,
            limits=limits,ext009_resolution_sha256=None) as store:
        require(not store._capture_pending and store.reserved_bytes()==0
            and all(row['kind']=='RELEASED' for row in store._states.values()),'prior original custody incomplete')
        require(not any(row.get('storage_extension') for row in store._families.values()),'prior S180 family exists')
        usage=store.physical_accounting();fs=os.statvfs(store.root)
        snapshot=execution.custody.CapacitySnapshot(fs.f_bavail*fs.f_frsize,fs.f_favail,usage.quota_bytes,0,
            unrelated['reserved_bytes'],unrelated['reserved_inodes'])
        execution.custody.check_capacity(snapshot,space)
        require(usage.quota_bytes+envelope['archive_family_upper_bytes']+space.retained_metadata_bytes<=execution.custody.PROGRAM_QUOTA,
            'full future family exceeds shared quota')
        require(store._sequence+records<=limits.max_ledger_records and usage.unique_objects+files<=limits.max_inventory_files,
            'future family metadata exceeds custody limits')
    _signer_check(execution,base.view(),deadline)
    require(time.monotonic_ns()<deadline,'complete read-only preflight expired')
    history=execution._binding(COMMON/'inputs/d342-local-audit.json')
    inputs=dict(base_owner=base,sizing=sizing,native_image=native,clock_image=clock,evidence_helper=helper,
        support_root=PACKAGE/'support',native_source_root=NATIVE_SOURCE,native_release_root=release,
        codegen_report=release/'s180_codegen_report-final.json',archive_profile=archive_profile,
        local_history_binding=history,operator_revision=profile['source_revision'],unrelated_reservations=unrelated)
    return inputs,dict(status='S180_READONLY_PREFLIGHT_PASSED',whole_run_budget=budget,declared_caps=timing,
        census=census,capacity_snapshot=asdict(snapshot),source_preparation_performed=False,
        qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False)


def prepare_runtime(execution):
    require(RUN.resolve(strict=True)==RUN and not any(RUN.iterdir()),'fresh protected runtime directory required')
    # Real copies: recovery's fixed core refuses symlink ancestors. Retain them
    # across main service exit for independent verification, never adopt them.
    for name in ('tools','docs','config'):
        shutil.copytree(COMMON/name,RUN/name,symlinks=False)
    shutil.copyfile(PACKAGE/'stop_post.py',RUN/'stop_post.py')
    for path in RUN.rglob('*'):
        require(not path.is_symlink(),'runtime recovery source symlink')
        path.chmod(0o555 if path.is_dir() else 0o444)
    manifest=json.loads(_read(COMMON/'S180_COLD_SOURCE_MANIFEST.json',2*1024**2))
    for row in manifest['files']:
        if row['path'].split('/',1)[0] not in ('tools','docs','config'):continue
        path=RUN/row['path'];raw=_read(path,256*1024**2)
        require(len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],
            'installed recovery source differs')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:os.fsync(fd)
        finally:os.close(fd)
    require(_read(RUN/'stop_post.py',4096)==execution.compaction.stop_post_script(),'installed recovery entry differs')


def service_units(profile_sha256):
    """Installer renders fixed units only after the clean packet is verified."""
    require(len(profile_sha256)==64 and all(c in '0123456789abcdef' for c in profile_sha256),'exact profile digest required')
    command=f'{PYTHON} -B {PACKAGE}/stage17_s180_service_v1.py'
    option=' --profile-sha256 '+profile_sha256
    shared=('User=root\nGroup=root\nSlice=-.slice\nKillMode=control-group\nSendSIGKILL=yes\n'
        'Restart=no\nLimitAS=4294967296:68719476736\nLimitMEMLOCK=68719476736\nLimitNOFILE=1024\n'
        'LimitCORE=0\nUMask=0077\nEnvironment=PYTHONDONTWRITEBYTECODE=1\nTimeoutStopSec=120\n')
    operator=('[Unit]\nDescription=Approved once-only descriptive S180 pilot\n'
        'OnSuccess=cpu-prefetch-s180-exit-1.service\n[Service]\nType=exec\n'+shared+
        'RuntimeDirectory=cpu-prefetch-s180-operator-1\nRuntimeDirectoryMode=0700\nRuntimeDirectoryPreserve=yes\n'
        'RuntimeMaxSec=86400\nExecStartPre='+command+' prepare-runtime'+option+'\nExecStart='+command+' run'+option+
        f'\nExecStopPost={PYTHON} -B {RUN}/stop_post.py\n')
    observer=('[Unit]\nDescription=Independent S180 operational exit verification\n[Service]\nType=exec\n'+shared+
        'RuntimeMaxSec=1800\nExecStart='+command+' exit'+option+'\n')
    return {'cpu-prefetch-s180-operator-1.service':operator,'cpu-prefetch-s180-exit-1.service':observer}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('check','prepare-runtime','run','exit'))
    p.add_argument('--profile-sha256',required=True);args=p.parse_args()
    profile,execution,exit_check=authenticate(args.profile_sha256)
    resource.setrlimit(resource.RLIMIT_AS,(4*GIB,64*GIB));resource.setrlimit(resource.RLIMIT_MEMLOCK,(64*GIB,64*GIB))
    resource.setrlimit(resource.RLIMIT_NOFILE,(1024,1024));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    if args.action=='prepare-runtime':prepare_runtime(execution);return
    if args.action=='exit':
        # Original replay remains actual; no check-mode root absence gate here.
        e=execution.ROOT.parent;name='cpu-prefetch-pilot-candidate-2.0.0-7b7c263-clean-5e100e05e49b.tar.gz'
        base=execution.original.verify_original(base_replay_arguments=dict(repository_root=e/'admission-root',evidence_root=e,
            latest_journal=e/'journal/stage17-state-journal-000010.json',journal_directory=e/'journal',
            pilot_archive=e.parent/name,pilot_sidecar=e.parent/(name+'.sha256')),deadline_ns=time.monotonic_ns()+600*NS)
        result=exit_check.observe(base_owner=base,operator_revision=profile['source_revision'],operator_profile_sha256=args.profile_sha256)
    else:
        inputs,result=preflight(execution,profile)
        if args.action=='run':
            script=execution.runtime.ImageBinding(execution.compaction.RECOVERY_SCRIPT,len(execution.compaction.stop_post_script()),
                hashlib.sha256(execution.compaction.stop_post_script()).hexdigest())
            supervision=execution.compaction.verify_supervision(recovery_script=script,deadline_ns=time.monotonic_ns()+60*NS)
            result=execution.execute_once(execution.Inputs(**inputs,supervision=supervision,operator_profile_sha256=args.profile_sha256))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
