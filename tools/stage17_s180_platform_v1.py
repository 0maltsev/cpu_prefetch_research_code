"""Fresh fixed-stand topology/cache admission under D310; no hardware writes.

The collector reads kernel metadata only. Current qualification, owned isolation,
original calibration compatibility and prospective requests are separate inputs.
Neither a snapshot nor this component grants full EXT008 or execution authority.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

SCHEMA='cpu-prefetch-stage17-s180-platform-observation/1'
REQUEST_SCHEMA='cpu-prefetch-stage17-s180-platform-request/1'
PROOF_SCHEMA='cpu-prefetch-stage17-s180-platform-admission/1'
BLUEPRINT_SHA='e95183365023a06b9da0d6cdff042bce556b9eb60c701dfb0f9e6df6ca22685c'
FOOTPRINT='docs/evidence/stage17/DISCOVERY-RECOVERY-V19-20261103-01/frozen-preparation/preparation/footprint-stand-stdout.json'
FOOTPRINT_SHA='f1f607f1bce28f1c465db0d691e494168bbfc80924aca2e7479c0dcc5d8b9f6b'
REQUEST='config/stage17/d310-s180-platform-request-v1.json'
REQUEST_SHA='03e6b510a138b2a45aa19bd22512f3959f8dd5c5ba974e9f2733f6512b15590f'
CPUS=(0,1,2,8)
MAX_REPORT_BYTES=128*1024
METADATA_NS=120*10**9
FOOTPRINT_LIBRARIES={
    'libcpu_prefetch_queue.a':(51162,'dddd26e8788f362f3b68494aaf66b6c37d18f2cbcb288a3cc0ef93771164ddf6'),
    'libcpu_prefetch_workload.a':(102946,'24ffc94864ce4c373b2262dd3cd862aeeb9c97d68d998e15fb229813ed42f04c')}
_TOKEN=object()


class PlatformError(ValueError):pass


def require(value,message):
    if not value:raise PlatformError('S180 platform: '+message)


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def _sha(value):return hashlib.sha256(_canonical(value)).hexdigest()


def _before(deadline):
    require(type(deadline) is int and time.monotonic_ns()<deadline,'original metadata deadline expired')


def _cpus(value):
    require(type(value) is str and bool(re.fullmatch(r'[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*',value)),
        'canonical bounded CPU list required')
    result=set()
    for part in value.split(','):
        ends=part.split('-');first,last=int(ends[0]),int(ends[-1])
        require(0<=first<=last<4096,'CPU range exceeded')
        values=set(range(first,last+1));require(not result&values,'duplicate CPU list entry');result.update(values)
    return sorted(result)


def _number(value):
    require(type(value) is str and bool(re.fullmatch(r'0|[1-9][0-9]*',value)),'unsigned decimal kernel value required')
    result=int(value);require(result<2**64,'kernel integer exceeded');return result


def _size(value):
    require(bool(re.fullmatch(r'[1-9][0-9]*K',value)),'explicit kernel KiB cache size required')
    result=int(value[:-1])*1024;require(result<2**64,'cache size exceeded');return result


def _selected(value):
    tokens=value.split();selected=[t[1:-1] for t in tokens if t.startswith('[') and t.endswith(']')]
    require(len(selected)==1 and all(re.fullmatch(r'\[?[a-z+]+\]?',t) for t in tokens),
        'actual selected kernel policy required')
    return selected[0]


def observe(*,deadline_ns):
    """Bounded read-only kernel collector; intentionally has no fixture backend."""
    _before(deadline_ns);require(deadline_ns-time.monotonic_ns()<=METADATA_NS,'short metadata lease required')
    started=time.monotonic_ns();bindings=[]
    def read(path,maximum=4096):
        _before(deadline_ns)
        fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NONBLOCK|os.O_NOFOLLOW)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode),'regular kernel attribute required')
            raw=bytearray()
            while True:
                _before(deadline_ns);part=os.read(fd,min(65536,maximum+1-len(raw)))
                if not part:break
                raw.extend(part);require(len(raw)<=maximum,'kernel attribute byte bound exceeded')
        finally:os.close(fd)
        bindings.append(dict(path=path,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        require(len(bindings)<=128,'kernel read count exceeded')
        return raw.decode('ascii').strip()
    boot=read('/proc/sys/kernel/random/boot_id',128)
    online=_cpus(read('/sys/devices/system/cpu/online'))
    raw_cpu=read('/proc/cpuinfo',2*1024**2);inventory={}
    for block in raw_cpu.split('\n\n'):
        row={k.strip():v.strip() for line in block.splitlines() if ':' in line for k,v in [line.split(':',1)]}
        if row.get('processor') not in {str(cpu) for cpu in CPUS}:continue
        cpu=_number(row['processor']);require(cpu not in inventory,'duplicate processor inventory')
        inventory[cpu]=dict(vendor=row['vendor_id'],family=_number(row['cpu family']),model=_number(row['model']),
            microcode=row['microcode'],flags=sorted(row['flags'].split()))
    require(set(inventory)==set(CPUS),'complete four-CPU inventory required')
    cpus=[]
    for cpu in CPUS:
        prefix=f'/sys/devices/system/cpu/cpu{cpu}'
        topology={name:read(prefix+'/topology/'+name) for name in
            ('physical_package_id','core_id','thread_siblings_list','core_siblings_list')}
        caches={}
        for index in (2,3):
            values={name:read(prefix+f'/cache/index{index}/'+name) for name in
                ('level','type','size','coherency_line_size','shared_cpu_list')}
            require(values['level']==str(index) and values['type']=='Unified','actual unified L2/L3 identity required')
            caches[str(index)]=dict(size_bytes=_size(values['size']),cache_line_bytes=_number(values['coherency_line_size']),
                shared_cpus=_cpus(values['shared_cpu_list']))
        policy={name:read(prefix+'/cpufreq/'+name) for name in
            ('scaling_driver','scaling_governor','scaling_min_freq','scaling_max_freq')}
        for name in ('scaling_min_freq','scaling_max_freq'):policy[name]=_number(policy[name])
        require(policy['scaling_driver'] and policy['scaling_governor'] and 0<policy['scaling_min_freq']<=policy['scaling_max_freq'],
            'actual frequency-policy metadata required')
        cpus.append(dict(cpu=cpu,**inventory[cpu],package_id=_number(topology['physical_package_id']),
            core_id=_number(topology['core_id']),thread_siblings=_cpus(topology['thread_siblings_list']),
            package_cpus=_cpus(topology['core_siblings_list']),caches=caches,frequency_policy=policy))
    nodes=[]
    for node in (0,1):
        prefix=f'/sys/devices/system/node/node{node}'
        nodes.append(dict(node=node,cpus=_cpus(read(prefix+'/cpulist')),
            distances=[_number(v) for v in read(prefix+'/distance').split()]))
    mounts=read('/proc/self/mountinfo',128*1024)
    controls=dict(numa_balancing=_number(read('/proc/sys/kernel/numa_balancing')),
        thp_enabled=_selected(read('/sys/kernel/mm/transparent_hugepage/enabled')),
        thp_defrag=_selected(read('/sys/kernel/mm/transparent_hugepage/defrag')),
        clocksource=read('/sys/devices/system/clocksource/clocksource0/current_clocksource'))
    static=dict(base_page_bytes=os.sysconf('SC_PAGE_SIZE'),online_cpus=online,cpus=cpus,nodes=nodes,
        controls=controls,resctrl_mounted=any(' - resctrl ' in line for line in mounts.splitlines()))
    require(boot==read('/proc/sys/kernel/random/boot_id',128),'boot changed during platform reads')
    _before(deadline_ns)
    result=dict(schema_version=SCHEMA,boot_id=boot,started_monotonic_ns=started,
        completed_monotonic_ns=time.monotonic_ns(),static_platform=static,kernel_readings=bindings,
        qualification_performed=False,execution_authority=False,phase18_authority=False)
    require(len(_canonical(result))<=MAX_REPORT_BYTES//2,'platform observation byte bound exceeded')
    return result


def request_from_observation(observation,*,stand_id):
    """Prospective request only; the qualified operator must bind its custody."""
    require(observation['schema_version']==SCHEMA and type(stand_id) is str and stand_id,'actual observation and stand required')
    return dict(schema_version=REQUEST_SCHEMA,stand_id=stand_id,blueprint_sha256=BLUEPRINT_SHA,
        observed_boot_id=observation['boot_id'],observed_snapshot_sha256=_sha(observation),
        observed_completed_monotonic_ns=observation['completed_monotonic_ns'],
        requested_static_platform=json.loads(_canonical(observation['static_platform'])),
        source_is_read_only_observation=True,execution_authority=False,phase18_authority=False)


def _request():
    path=Path(__file__).resolve().parents[1]/REQUEST
    with path.open('rb') as stream:raw=stream.read(MAX_REPORT_BYTES+1)
    require(len(raw)<=MAX_REPORT_BYTES and hashlib.sha256(raw).hexdigest()==REQUEST_SHA,
        'exact prospective platform request required')
    value=json.loads(raw);require(_canonical(value)==raw,'canonical prospective request required');return value


def _footprints():
    path=Path(__file__).resolve().parents[1]/FOOTPRINT
    with path.open('rb') as stream:raw=stream.read(3537)
    require(len(raw)==3536 and hashlib.sha256(raw).hexdigest()==FOOTPRINT_SHA,'exact accepted footprint observation required')
    return json.loads(raw)


def assess(observation,*,blueprint,platform_request):
    """Pure comparisons for the fixed design, never proof of fresh collection."""
    require(observation['schema_version']==SCHEMA and _sha(blueprint)==BLUEPRINT_SHA,'exact platform/blueprint scope required')
    request=platform_request
    require(set(request)==set(('schema_version stand_id blueprint_sha256 observed_boot_id observed_snapshot_sha256 observed_completed_monotonic_ns '
        'requested_static_platform source_is_read_only_observation execution_authority phase18_authority').split())
        and request['schema_version']==REQUEST_SCHEMA and request['stand_id']==blueprint['stand_id']
        and request['blueprint_sha256']==BLUEPRINT_SHA and request['observed_boot_id']==observation['boot_id']
        and request['source_is_read_only_observation'] is True and request['execution_authority'] is False
        and request['phase18_authority'] is False,'prospective platform request scope differs')
    require(type(request['observed_snapshot_sha256']) is str and re.fullmatch('[0-9a-f]{64}',request['observed_snapshot_sha256']),
        'original prospective observation digest required')
    current=observation['static_platform']
    require(_canonical(request['requested_static_platform'])==_canonical(current),'requested and actual platform differ')
    require(current['base_page_bytes']==4096 and current['online_cpus']==list(range(32)),
        'actual page/online topology differs from fixed stand')
    rows=current['cpus'];require([r['cpu'] for r in rows]==list(CPUS),'exact CPU0/1/2/8 roles required')
    require(all(r['vendor']=='GenuineIntel' and r['family']==6 and r['model']==62 for r in rows),
        'actual four-CPU Intel06_3EH identity differs')
    require(len({(r['package_id'],r['core_id']) for r in rows})==4,'roles share an actual physical core')
    require([r['thread_siblings'] for r in rows]==[[0,16],[1,17],[2,18],[8,24]],
        'actual SMT reservations differ from fixed isolation')
    require(rows[0]['package_id']==rows[1]['package_id']==rows[2]['package_id']!=rows[3]['package_id'],
        'actual socket placements differ')
    nodes=current['nodes'];require([n['node'] for n in nodes]==[0,1],'actual two NUMA nodes required')
    require(not set(nodes[0]['cpus'])&set(nodes[1]['cpus'])
        and sorted(nodes[0]['cpus']+nodes[1]['cpus'])==current['online_cpus']
        and {0,1,2}<=set(nodes[0]['cpus']) and 8 in nodes[1]['cpus'],'actual CPU-to-NUMA mapping differs')
    require(all(r['package_cpus']==nodes[0 if r['cpu'] in (0,1,2) else 1]['cpus'] for r in rows),
        'actual socket and complete SMT/NUMA domains differ')
    for i,node in enumerate(nodes):
        require(len(node['distances'])==2 and 0<node['distances'][i]<node['distances'][1-i],
            'actual NUMA distance relation differs')
    require(not current['resctrl_mounted'] and not any(set(r['flags'])&{'cat_l3','cat_l2','cdp_l3','cdp_l2'} for r in rows),
        'cache-allocation regime differs from accepted nominal-cache interpretation')
    for row in rows:
        for level in ('2','3'):
            cache=row['caches'][level]
            require(cache['size_bytes']>0 and cache['cache_line_bytes']==64 and row['cpu'] in cache['shared_cpus'],
                'actual cache geometry differs')
        require(row['caches']['2']['shared_cpus']==row['thread_siblings'],'actual private L2 sharing differs')
        require(row['caches']['3']['shared_cpus']==row['package_cpus'],'actual LLC/socket sharing differs')
    require(rows[0]['caches']['3']==rows[1]['caches']['3']==rows[2]['caches']['3']
        and not set(rows[0]['caches']['3']['shared_cpus'])&set(rows[3]['caches']['3']['shared_cpus']),
        'actual near/controller shared LLC or disjoint far LLC differs')
    native=_footprints();require(native['cache_line_bytes']==64 and native['page_bytes']==4096,
        'accepted native ABI geometry differs')
    candidates=native['candidates'];require(len(candidates)==22 and all(r['capacity']==1<<i for i,r in enumerate(candidates)),
        'complete accepted power-of-two boundary table required')
    derived=[]
    for placement,consumer in (('NEAR',rows[1]),('FAR',rows[3])):
        l2=min(rows[0]['caches']['2']['size_bytes'],consumer['caches']['2']['size_bytes'])
        llc=rows[0]['caches']['3']['size_bytes']
        for working in ('L2_RESIDENT','LLC_RESIDENT','BEYOND_LLC'):
            def matches(r):
                values=(r['ring_full_bytes'],r['linked_full_bytes'])
                return all(4*64<x<=l2//2 if working=='L2_RESIDENT' else
                    2*l2<x<=llc//2 if working=='LLC_RESIDENT' else x>=2*llc for x in values)
            eligible=[r for r in candidates if matches(r)];require(eligible,'no common full-footprint capacity')
            selected=(min if working=='BEYOND_LLC' else max)(eligible,key=lambda r:r['capacity'])
            index=candidates.index(selected);neighbor=index-1 if working=='BEYOND_LLC' else index+1
            require(0<=neighbor<len(candidates) and not matches(candidates[neighbor]),'adjacent exact boundary unverified')
            captures=[r for r in blueprint['captures'] if (r['placement'],r['working_set_class'])==(placement,working)]
            geometry=dict(capacity=selected['capacity'],cache_line_bytes=64,base_page_bytes=4096,
                producer_cpu=0,producer_node=0,consumer_cpu=consumer['cpu'],consumer_node=0 if placement=='NEAR' else 1,shared_node=0)
            require(len(captures)==30 and all(r['requested_geometry']==geometry for r in captures),
                'frozen requested capacity/topology differs from actual full-footprint boundary')
            derived.append(dict(placement=placement,working_set_class=working,verified_geometry=geometry,
                nominal_smaller_l2_bytes=l2,nominal_producer_home_llc_bytes=llc,
                footprint=selected,adjacent_boundary=candidates[neighbor]))
    return dict(contexts=derived,footprint_source_sha256=FOOTPRINT_SHA,
        footprint_source_is_retained_software_evidence=True,instantaneous_residency_guaranteed=False,
        remote_llc_added=False,shared_home_llc_explicit=True,calibration_platform_strata_merged=False)


# Owned admission composes existing qualified producers; the collector above is
# standalone stdlib code so its exact bytes can be inspected remotely read-only.
def _modules():
    import stage17_formal_archive_v1 as archive
    import stage17_s180_environment_v1 as environment
    import stage17_s180_qualification_evidence_v1 as qualification
    import stage17_s180_calibration_compatibility_v1 as compatibility
    return archive,environment,qualification,compatibility


def _footprint_abi(software):
    # Both libraries match the original ac64633 footprint producer's actual
    # qualified inventory. D340's owned proof rehashes both old/current files.
    for name,(size,digest) in FOOTPRINT_LIBRARIES.items():
        rows=[r for r in software['files'] if Path(r['path']).name==name]
        require(len(rows)==2 and all(r['size_bytes']==size and r['sha256']==digest for r in rows),
            'retained footprint queue/workload ABI ancestry differs')


class _VerifiedPlatform:
    def __init__(self,*,token,plan,request,environment_owner,qualification_owner,compatibility_owner,base,deadline):
        require(token is _TOKEN,'actual live platform verification required')
        self._plan=_canonical(plan);self._request=_canonical(request);self.environment=environment_owner
        self.qualification=qualification_owner;self.compatibility=compatibility_owner;self.base=base
        self.deadline=deadline;self.pid=os.getpid();self.failed=False;self._report=None;self._last=None

    def _observe(self):
        archive,environment,qualification,compatibility=_modules()
        _before(self.deadline);require(self.pid==os.getpid() and not self.failed,'platform owner failed or belongs to another process')
        plan=json.loads(self._plan);family=_sha(plan);request=json.loads(self._request)
        require(self.qualification.owner.prepared.owner is self.environment,'qualification belongs to another environment')
        qualified=self.qualification.proof(plan_sha256=family)
        native=self.qualification.owner.proof(plan_sha256=family)
        require(native['plan_sha256']==family and native['stand_id']==plan['blueprint']['stand_id']
            ==self.base.resolutions['S17-EXT-002'].semantic_context['stand_id'],
            'qualified/current/original stand identity differs')
        software=self.compatibility.proof(base_validation=self.base,plan_sha256=family,for_execution=True)
        require(qualified['base_resolutions']==software['base_resolutions']
            and qualified['dynamic_qualification_verified'] is True and software['software_compatibility_verified'] is True
            and software['current_source_revision']==environment.NATIVE_REVISION
            and qualified['measurement_runtime_binding']['sha256']==qualification.q15.compaction.NATIVE_SHA
            and qualified['measurement_runtime_binding']['size_bytes']==qualification.q15.compaction.NATIVE_SIZE,
            'qualification/compatibility original ancestry or frozen native differs')
        _footprint_abi(software)
        before=self.environment.admission_observation(plan_sha256=family)
        require(type(request['observed_completed_monotonic_ns']) is int
            and 0<request['observed_completed_monotonic_ns']<before['window_binding']['start_monotonic_ns']
            and self.deadline<=before['window_binding']['end_monotonic_ns'],
            'prospective request or short metadata lease crosses original window boundary')
        observed=observe(deadline_ns=self.deadline)
        derived=assess(observed,blueprint=plan['blueprint'],platform_request=request)
        after=self.environment.admission_observation(plan_sha256=family)
        require(observed['boot_id']==before['boot_id']==after['boot_id']
            and before['window_binding']==after['window_binding']==qualified['window_binding'],
            'actual platform/environment/qualification window differs')
        self.environment.compaction_guard().check(boundary='ADMISSION');_before(self.deadline)
        result=dict(schema_version=PROOF_SCHEMA,plan_sha256=family,window_binding=after['window_binding'],
            platform_request_sha256=_sha(request),base_resolutions=qualified['base_resolutions'],
            qualification_sha256=qualified['qualification_sha256'],software_compatibility_sha256=_sha(software),
            observation=observed,geometry=derived,environment=after,
            current_geometry_and_regime_verified=True,full_platform_inventory_verified=False,
            full_ext008_admission=False,execution_authority=False,phase18_authority=False)
        require(len(_canonical(result))<=MAX_REPORT_BYTES,'platform admission report exceeds reserved bound')
        return result

    def proof(self,*,plan_sha256):
        try:
            require(plan_sha256==_sha(json.loads(self._plan)),'original platform plan differs')
            result=self._observe();self._last=_canonical(result)
            if self._report is None:self._report=self._last
            result['platform_evidence_sha256']=hashlib.sha256(self._report).hexdigest()
            return result
        except BaseException:
            self.failed=True;self.environment._qualification_failed=True
            raise

    def report(self):
        require(self._report is not None,'no actual platform proof exists');return bytes(self._report)


def verify_platform(*,plan,environment_owner,qualification_owner,compatibility_owner,base_validation,deadline_ns):
    """Only the qualified operator binds prospective request and original replay."""
    archive,environment,qualification,compatibility=_modules()
    require(type(environment_owner) is environment._PreparedEnvironment
        and type(qualification_owner) is qualification._VerifiedEvidence
        and type(compatibility_owner) is compatibility._VerifiedCompatibility,'actual owned platform prerequisites required')
    try:
        _before(deadline_ns);require(deadline_ns-time.monotonic_ns()<=METADATA_NS,'short original metadata lease required')
        environment._plan(plan)
        owner=_VerifiedPlatform(token=_TOKEN,plan=plan,request=_request(),environment_owner=environment_owner,
            qualification_owner=qualification_owner,compatibility_owner=compatibility_owner,base=base_validation,deadline=deadline_ns)
        owner.proof(plan_sha256=_sha(plan));return owner
    except BaseException:
        environment_owner._qualification_failed=True
        raise
