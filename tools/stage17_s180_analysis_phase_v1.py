"""Owned post-restoration S180 analysis resource transition, not run admission.

The qualified outer must authenticate completed native collection/custody,
input/output census and its analysis package before invoking actual analysis.
This gate supplies none of that evidence and never launches a worker.
"""
from __future__ import annotations
from contextlib import contextmanager
import os
from pathlib import Path
import resource
import signal
import threading
import time

import stage17_s180_environment_v1 as environment
import stage17_s180_verified_sources_v1 as sources
import stage17_s180_resource_admission_v1 as resources
import stage17_s180_resource_plan_v1 as bounds
import stage17_process_group_supervisor_v3 as supervisor

archive=resources.archive
_TOKEN=object()
SCHEMA='cpu-prefetch-stage17-s180-owned-analysis-phase/1'


def require(ok,message):
    if not ok:raise resources.ResourceError('S180 analysis phase: '+message)


def physical_cpus(allowed,topology):
    require(type(allowed) in (set,frozenset) and allowed and set(topology)==allowed,
        'complete actual allowed CPU topology required')
    chosen={}
    for cpu in sorted(allowed):
        archive.uint(cpu,'actual CPU');pair=topology[cpu]
        require(type(pair) is tuple and len(pair)==2,'actual package/core pair required')
        for value in pair:archive.uint(value,'actual package/core')
        chosen.setdefault(pair,cpu)
    require(len(chosen)>=bounds.ANALYSIS_WORKERS,'twelve actual distinct physical cores required')
    return list(chosen.values())[:bounds.ANALYSIS_WORKERS]


def phase_deadline(started,window):
    start=archive.uint(started,'original analysis start',positive=True)
    require(type(window) is dict and set(window)=={'boot_id','start_monotonic_ns','end_monotonic_ns'},'original window fields')
    begin=archive.uint(window['start_monotonic_ns'],'original window start',positive=True)
    end=archive.uint(window['end_monotonic_ns'],'original window end',positive=True)
    require(end-begin==86400*10**9 and begin<=start,'unchanged original24h window required')
    deadline=start+bounds.EXTERNAL_TIME['independent_validation_ns']
    require(deadline+bounds.EXTERNAL_TIME['restoration_and_exit_ns']<=end,
        'complete original90-minute analysis and exit reserve do not fit')
    return deadline


def assess_memory(observed):
    needed=4*bounds.GIB+bounds.ANALYSIS_WORKERS*bounds.ANALYSIS_CHILD_AS
    require(observed['memory_available_bytes']>=needed,'physical RAM omits full analysis stage')
    for row in observed['memory_ancestors']:
        maximum=row['maximum_bytes']
        require(maximum is None or maximum>=row['current_bytes']+needed,'finite memory ancestor omits analysis stage')
    soft,hard=observed['rlimit_as']
    require(0<soft<=4*bounds.GIB and (hard==resource.RLIM_INFINITY or soft<=hard),'actual bounded parent AS required')
    require(observed['base_page_bytes']==4096,'accepted actual base page required')
    return needed


class _AnalysisPhase:
    def __init__(self,*,token,source_owner,environment_owner,plan_sha256,window,started,deadline,lease,cpus,observation):
        require(token is _TOKEN,'only actual owned transition constructs an analysis phase')
        self.source_owner=source_owner;self.environment_owner=environment_owner;self.lease=lease
        self.plan_sha256=plan_sha256;self.window=archive.canonical(window);self.deadline_ns=deadline
        self.cpus=tuple(cpus);self.pid=os.getpid();self.closed=False;self.failed=False;self._pool_consumed=False
        self._report=archive.canonical(dict(schema_version=SCHEMA,plan_sha256=plan_sha256,window_binding=window,
            started_monotonic_ns=started,deadline_monotonic_ns=deadline,physical_cpus=cpus,
            worker_count=bounds.ANALYSIS_WORKERS,worker_address_space_bytes=bounds.ANALYSIS_CHILD_AS,
            decoder_soft_address_space_bytes=2*bounds.GIB,platform_observation=observation,
            stage_address_space_upper_bytes=4*bounds.GIB+bounds.ANALYSIS_WORKERS*bounds.ANALYSIS_CHILD_AS,
            native_environment_restored=True,source_descriptors_released=True,initial_owned_children_absent=True,
            actual_analysis_performed=False,original_archive_custody_verified=False,execution_authority=False,phase18_authority=False))

    def check(self):
        require(not self.closed and not self.failed and self.pid==os.getpid(),'original analysis phase closed/failed/foreign')
        try:
            require(time.monotonic_ns()<self.deadline_ns,'original analysis deadline expired')
            self.lease.identity_model.verify_stable()
            self.source_owner.released_proof(plan_sha256=self.plan_sha256)
            self.environment_owner.restored_proof(plan_sha256=self.plan_sha256)
            return archive.parse_json(self._report)
        except BaseException:self.failed=True;raise


@contextmanager
def analysis_phase(*,source_owner,environment_owner,plan_sha256):
    """Hold one no-overlap phase after actual same-process cleanup, not reports.

    The pool runner must use this lease for descendant-safe cleanup, enforce
    every worker's affinity/limits, retain failures and stop on the first error.
    This resource gate grants no scientific or collection admission by itself.
    """
    require(type(source_owner) is sources._VerifiedSources and type(environment_owner) is environment._PreparedEnvironment,
        'actual owned sources and environment required')
    require(threading.current_thread() is threading.main_thread() and threading.active_count()==1
        and signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'single-threaded default-SIGCHLD parent required')
    archive.sha(plan_sha256,'original collected plan')
    require(environment.planning.sha(archive.parse_json(environment_owner._plan))==plan_sha256,
        'original owned environment plan differs')
    require(not environment_owner._analysis_phase_consumed,'original analysis phase already consumed; no retry')
    environment_owner._analysis_phase_consumed=True
    released=source_owner.released_proof(plan_sha256=plan_sha256)
    restored=environment_owner.restored_proof(plan_sha256=plan_sha256)
    window=archive.parse_json(environment_owner._window)
    require(released['boot_id']==restored['boot_id']==window['boot_id'],'actual transition boot differs')
    started=time.monotonic_ns();deadline=phase_deadline(started,window)
    lease=supervisor.SupervisorLease();owner=None
    try:
        lease.enter()
        require(not lease.identity_model.direct_children(),'native/qualification/broker descendants remain')
        observed=resources.platform_observation();assess_memory(observed)
        require(observed['boot_id']==window['boot_id'],'fresh physical observation boot differs')
        allowed=set(os.sched_getaffinity(0));topology={}
        for cpu in allowed:
            base=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
            topology[cpu]=tuple(int((base/name).read_text()) for name in ('physical_package_id','core_id'))
        cpus=physical_cpus(allowed,topology)
        require(time.monotonic_ns()<deadline,'original analysis phase expired in admission')
        owner=_AnalysisPhase(token=_TOKEN,source_owner=source_owner,environment_owner=environment_owner,
            plan_sha256=plan_sha256,window=window,started=started,deadline=deadline,lease=lease,cpus=cpus,observation=observed)
        owner.check();yield owner
    finally:
        if owner is not None:owner.closed=True
        lease.close()
