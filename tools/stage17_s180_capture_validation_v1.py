"""Independent original-byte S180 capture validation and descriptive analysis.

The caller authenticates checkpoint/admission/custody and budgets before this
offline operation. Reconstruct published schedules/arena/nodes, check all
controls, join both primary phases, then analyze accepted measurement events.
No experiment, source regeneration, replacement, whole-family admission or freeze.
"""
from __future__ import annotations
import array
from contextlib import ExitStack
import copy
import fcntl
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import struct
import sys
from types import SimpleNamespace

import stage17_s180_capture_controls_v1 as controls
import stage17_s180_raw_join_v1 as join
import stage17_s180_tail_numerics_v1 as tails
import stage17_s180_checkpoint_v1 as checkpoint_contract
import stage17_formal_service_capture_validation_v1 as old
from stage17_formal_archive_v1 import canonical,ArchiveError
from stage17_formal_archive_custody_v1 import BoundFile

common,raw,codec=controls.common,join.raw,join.codec
require,exact,uint=common.require,common.exact,common.uint
SCHEMA='cpu-prefetch-stage17-s180-capture-validation/1'
MAX_CONTROL_BYTES=256*1024**2
MAX_CONTEXTS=6
METADATA_RESERVE=1024**2


def before(deadline):join.before(deadline)
def sha(value):return hashlib.sha256(canonical(value)).hexdigest()
def stamp(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def prospective_capture(capture,entry):
    """Exact metadata construction used by the frozen native publisher."""
    exact(entry['execution_ordinal'],capture['execution_ordinal'],'admitted execution ordinal')
    exact(entry['cell_ordinal'],capture['cell_ordinal'],'admitted cell ordinal')
    result=copy.deepcopy(capture);require(len(entry['phases'])==2,'two original source declarations')
    result['schedules']=[dict(schedule_id=p['schedule_id'],namespace_id=capture[name+'_schedule_namespace'],
        source_artifact=p['source_artifact']) for name,p in zip(('warmup','measurement'),entry['phases'],strict=True)]
    return result


def _node_order(seed,namespace,count,deadline):
    order=array.array('Q',range(count));draws=common.draws(common.key(seed,namespace,'node-order'))
    for remaining in range(count,1,-1):
        if remaining%256==0:before(deadline)
        threshold=((-remaining)&join.U64)%remaining
        while True:
            value=next(draws)
            if value>=threshold:break
        selected=value%remaining;order[remaining-1],order[selected]=order[selected],order[remaining-1]
    before(deadline);return order


def _pattern(order,line,page,deadline):
    n=len(order);counts=array.array('I',[0])*(2*n-1)
    require(counts.itemsize==4,'bounded uint32 delta counters required')
    adjacent=0
    for i,left in enumerate(order):
        if i%256==0:before(deadline)
        delta=order[(i+1)%n]-left;counts[delta+n-1]+=1;adjacent+=abs(delta)==1
    best=0;modal=None
    for index,count in enumerate(counts):
        if index%256==0:before(deadline)
        if index!=n-1 and count>best:best=count;modal=(index-n+1)*line
    return dict(transition_count=n,distinct_line_count=n,distinct_page_count=(n*line+page-1)//page,
        shortest_period=n,adjacent_line_transition_count=adjacent,modal_nonzero_delta_count=best,
        modal_nonzero_delta=modal,adjacent_fraction_at_most_one_percent=adjacent<=n//100,
        modal_fraction_at_most_one_percent=best<=n//100)


class ReplayCache:
    """At most six deterministic contexts; packed-array alteration latches failure.

    This amortizes offline arena/node reconstruction, never schedule generation
    or measurement. A fresh cache/report cannot grant provenance or admission.
    """
    def __init__(self):self._entries={};self._failed=False

    @staticmethod
    def _integrity(value):
        arena,nodes,pattern=value
        digest=hashlib.sha256()
        for a in (arena.order,arena.payload,nodes):digest.update(memoryview(a).cast('B'))
        digest.update(canonical(dict(arena_hashes=list(arena.hashes),pattern=pattern)))
        return digest.digest()

    def get(self,capture,master_seed_hex,deadline):
        try:
            before(deadline);require(not self._failed,'failed deterministic context cache cannot be reused')
            require(type(master_seed_hex) is str and re.fullmatch('[0-9a-f]{64}',master_seed_hex),'exact original master seed')
            g=capture['requested_geometry']
            require(8<=uint(g['capacity'],'capacity')<=join.MAX_RECORDS,'bounded arena capacity')
            line=uint(g['cache_line_bytes'],'line');page=uint(g['base_page_bytes'],'page')
            require(64<=line<=page and line&(line-1)==0 and page&(page-1)==0,'explicit power-of-two geometry')
            for name in ('arena_namespace','node_order_namespace'):
                require(type(capture[name]) is str and 0<len(capture[name])<=512,'bounded persistent namespace')
            require(capture['arena_namespace']!=capture['node_order_namespace'],'distinct arena/node namespaces')
            identity=sha(dict(master_seed_hex=master_seed_hex,geometry=g,
                arena_namespace=capture['arena_namespace'],node_order_namespace=capture['node_order_namespace']))
            if identity not in self._entries:
                require(len(self._entries)<MAX_CONTEXTS,'more than six persistent replay contexts')
                namespace=SimpleNamespace(geometry=SimpleNamespace(**g),arena_seed=SimpleNamespace(
                    seed_hex=master_seed_hex,namespace_id=capture['arena_namespace']))
                arena=common.Arena(namespace);before(deadline)
                nodes=_node_order(master_seed_hex,capture['node_order_namespace'],g['capacity']+1,deadline)
                value=(arena,nodes,_pattern(nodes,line,page,deadline))
                self._entries[identity]=(value,self._integrity(value))
            value,original=self._entries[identity]
            require(self._integrity(value)==original,'deterministic replay arrays altered')
            before(deadline);return value
        except BaseException:self._failed=True;raise


class _RawReader(io.RawIOBase):
    def __init__(self,stream):super().__init__();self.stream=stream
    def readable(self):return True
    def readinto(self,buffer):
        block=self.stream.read(len(buffer));buffer[:len(block)]=block;return len(block)


class _Inputs:
    def __init__(self,root,stack,deadline,references,candidate_ids):
        self.root=Path(root);self.stack=stack;self.deadline=deadline;self.seen={};self.identities=set()
        self.fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        stack.callback(os.close,self.fd);self.original=os.fstat(self.fd);self.expected={};identities=set()
        for reference in references:
            before(deadline)
            stream=raw._open_stream(stack,self.fd,_binding(reference,reference['size_bytes'],1),'S180 original precheck')
            info=stream.before;identity=(info.st_dev,info.st_ino)
            require(identity not in identities and identity not in candidate_ids,'original/candidate physical alias')
            require(info.st_nlink==1 and not info.st_mode&0o022,'protected single-link original required')
            identities.add(identity);self.expected[reference['file_name']]=stamp(info)

    def open(self,binding):
        before(self.deadline);stream=raw._open_stream(self.stack,self.fd,binding,'S180 original')
        info=stream.before;name=binding['path'];identity=(info.st_dev,info.st_ino)
        require(name in self.expected and stamp(info)==self.expected[name],'original changed since inventory precheck')
        require(name not in self.seen and identity not in self.identities,'original artifact aliases another role')
        require(info.st_nlink==1 and not info.st_mode&0o022,'protected single-link original required')
        self.identities.add(identity);self.seen[name]=stamp(info);return stream

    def control(self,binding):
        require(0<binding['size_bytes']<=MAX_CONTROL_BYTES,'finite original control extent')
        source=self.open(binding)
        # Closing the adapters does not close the separately held source file.
        with io.TextIOWrapper(io.BufferedReader(_RawReader(source)),encoding='utf-8',errors='strict') as text:
            result=common.JsonReader(text,self.stack).document()
        source.finish();before(self.deadline);return result

    def finish(self):
        before(self.deadline);current=os.stat(self.root,follow_symlinks=False)
        require((current.st_dev,current.st_ino)==(self.original.st_dev,self.original.st_ino),'original root replaced')
        require(set(self.seen)==set(self.expected),'not every original artifact independently consumed')
        for name,original in self.seen.items():
            require(stamp(os.stat(name,dir_fd=self.fd,follow_symlinks=False))==original,
                'original artifact changed across capture validation')


def _binding(reference,count,row_bytes):
    return raw._binding(dict(path=reference['file_name'],size_bytes=reference['size_bytes'],
        sha256=reference['sha256'],row_count=count),'S180 original',row_bytes)


def _arena(control,capture,replay,regions):
    arena=replay[0];g=capture['requested_geometry']
    expected=dict(capacity=g['capacity'],cache_line_bytes=g['cache_line_bytes'],base_page_bytes=g['base_page_bytes'],
        allocated_bytes=g['capacity']*g['cache_line_bytes'],distinct_cache_lines=g['capacity'],
        distinct_pages=(g['capacity']*g['cache_line_bytes']+g['base_page_bytes']-1)//g['base_page_bytes'],
        base_page_aligned=True,every_record_line_aligned=True,padding_initialized=True,storage_address=regions[7]['address'],
        content_unchanged=True,prepared_content_sha256=arena.hashes[0],publication_content_sha256=arena.hashes[0],
        ordered_index_sha256=arena.hashes[1],address_delta_sha256=arena.hashes[2],ordered_index_error=None,address_delta_error=None)
    exact(control['arena'],expected,'independent persistent arena reconstruction')


def _sources(inputs,control,capture,entry,references,windows):
    require(len(control['schedules'])==2,'two actual source publications')
    values=[];reports=[]
    for i,(name,p,row) in enumerate(zip(('warmup','measurement'),entry['phases'],control['schedules'],strict=True)):
        before(inputs.deadline);count=uint(p['offered_count'],'offered')
        require(count<=(join.MAX_WARMUP if i==0 else join.MAX_MEASUREMENT),'frozen source-count ceiling')
        uint(p['source_origin_ticks'],'original source origin');uint(p['source_horizon_ticks'],'original source horizon')
        source=capture['schedules'][i]
        exact(row['prospective'],source,'actual mapped source identity')
        for k,v in dict(prepared_available=True,prepared_count=count,source_origin_ticks=p['source_origin_ticks'],
                source_horizon_ticks=p['source_horizon_ticks'],time_unit=raw.TIME_UNIT,
                coordinates='SOURCE_SCHEDULE_BEFORE_ACTUAL_ORIGIN_TRANSLATION',phase_released=True,
                attempted=count,all_arrivals_attempted=True).items():exact(row[k],v,'published source '+k)
        reference={k:row['stream'][k] for k in ('file_name','size_bytes','sha256')}
        exact(reference,references[5+i],'source/checkpoint binding')
        binding=old._binding(row['stream'],'S180_PREPARED_SCHEDULE','SCHEDULE-DEADLINES-U64LE-v1',count,8)
        stream=inputs.open(binding);packed=array.array('Q');digest=hashlib.sha256();remaining=count*8
        while remaining:
            before(inputs.deadline);block=codec._read_exact(stream,min(65536,remaining),'published source')
            little=array.array('Q');little.frombytes(block)
            if sys.byteorder!='little':little.byteswap()
            packed.extend(little)
            if sys.byteorder=='little':little.byteswap()
            digest.update(little.tobytes());remaining-=len(block)
        stream.finish();exact(digest.hexdigest(),p['source_artifact']['sha256'],'original big-endian source bytes')
        previous=p['source_origin_ticks']
        for ordinal,value in enumerate(packed):
            if ordinal%256==0:before(inputs.deadline)
            require(previous<=value<p['source_horizon_ticks'],'source order/window');previous=value
        last=windows[i]['measurement_origin']['relative_picoseconds']+packed[-1]-p['source_origin_ticks'] if count else None
        actual=control['native_result_before_publication_returns']['session']['scheduled']['schedules'][i]
        exact(actual['mapped_last_deadline'],last,'last actual mapped source deadline')
        values.append(packed);reports.append(dict(phase=name,offered_count=count,
            original_source_artifact=p['source_artifact'],publication=reference,original_big_endian_sha256=digest.hexdigest()))
    return values,reports


def _nodes(inputs,control,capture,replay,reference):
    arena,nodes,pattern=replay;g=capture['requested_geometry'];count=g['capacity']+1
    exact(control['node_order_count'],count,'persistent node count for every package')
    exact({k:control['node_order'][k] for k in ('file_name','size_bytes','sha256')},reference,'node/checkpoint binding')
    binding=old._binding(control['node_order'],'S180_NODE_ORDER','NODEORDER-U64LE-v1',count,8)
    stream=inputs.open(binding)
    for i,value in enumerate(nodes):
        if i%256==0:before(inputs.deadline)
        exact(struct.unpack('<Q',codec._read_exact(stream,8,'original node'))[0],value,'accepted deterministic node order')
    stream.finish();exact(control['shared_data']['node_pattern'],pattern,'independent node address summary')
    require(pattern['adjacent_fraction_at_most_one_percent'] and pattern['modal_fraction_at_most_one_percent'],
        'required prepared node-pattern gate failed')
    require(control['shared_data']['node_bytes']%g['base_page_bytes']==0,'actual node arena page alignment')
    return dict(count=count,publication=reference,pattern=pattern)


def _phase(inputs,control,capture,entry,index,window,arena,source,reference_pair,candidate):
    phase=control['phases'][index];name=('warmup','measurement')[index]
    run=capture['warmup_run_id' if index==0 else 'run_id']
    adapted=dict(warmup=dict(run_id=capture['warmup_run_id']),measurement=dict(run_id=capture['run_id']))
    bindings=old._primary_bindings(phase,adapted,entry['resources'],index,'S180')
    opened={}
    for role,reference in zip(('producer','consumer'),reference_pair,strict=True):
        binding=bindings[role]
        exact({k:phase[role][k] for k in ('file_name','size_bytes','sha256')},reference,'primary/checkpoint binding')
        opened[role]=inputs.open(binding)
    p=entry['phases'][index]
    contract=dict(schema_version=join.CONTRACT,run_id=run,phase=name.upper(),
        clock_origin_absolute_nanoseconds=window['clock_origin_absolute_nanoseconds'],
        phase_origin_relative_picoseconds=window['measurement_origin']['relative_picoseconds'],duration_ticks=window['duration_ticks'],
        drain_deadline_ticks=window['measurement_origin']['relative_picoseconds']+window['duration_ticks']+p['drain_duration_ticks'],
        source_origin_ticks=p['source_origin_ticks'],source_horizon_ticks=p['source_horizon_ticks'],
        maximum_offered=max(1,p['producer_attempt_limit']),initial_checksum=entry['resources']['initial_consumer_state'],
        expected_checksum=phase['checksum'],streams=bindings)
    # Offered-count bounds may have been conservatively declared above the
    # frozen source ceiling; that cannot enlarge this independent decoder.
    contract['maximum_offered']=min(contract['maximum_offered'],join.MAX_WARMUP if index==0 else join.MAX_MEASUREMENT)
    audit,latencies=join.derive_phase(inputs.root,contract,record_order=arena.order,payloads=arena.payload,
        schedule_ticks=source,candidate=candidate,deadline_ns=inputs.deadline)
    state=control['native_result_before_publication_returns']['session']['scheduled']['lifecycle']['phases'][index]
    for field,key in (('requests','offered_count'),('retained_attempts','attempted_count'),('accepted','accepted_count'),
            ('full','full_count'),('retained_consumed_including_drain','consumed_count')):
        exact(phase[field],audit[key],'independently reconciled '+field)
    for field,key in (('attempted','attempted_count'),('accepted','accepted_count'),('full','full_count')):
        exact(state['producer'][field],audit[key],'session '+field)
    exact(state['consumer']['consumed_including_drain'],audit['consumed_count'],'session consumed count')
    for field in ('polls','empty'):exact(phase[field],state['consumer'][field],'retained '+field)
    exact(phase['initial_checksum'],entry['resources']['initial_consumer_state'],'reset checksum')
    exact(phase['consumer_last_join'],dict(status=1,matched=audit['accepted_count'],failed_producer_row=None),'native join crosscheck')
    require('completion_interval' not in phase,'S180 must not apply Q16b completion filtering')
    require(state['producer']['last_observed_tick']>=audit['producer_last_completion_ticks']
        and state['consumer']['last_observed_tick']>=audit['consumer_last_action_ticks'],'owner clock precedes retained completion')
    last=None;count=bindings['producer']['row_count']
    if count:
        _,pb,_,_=codec.row_layout(run);opened['producer'].file.seek((count-1)*pb)
        last=codec._row(opened['producer'].file,pb,run,15,'final producer raw crosscheck')
    old._current(phase,last)
    return audit,latencies


def validate_capture(root,*,checkpoint,capture,entry,hardware,master_seed_hex,family_context_cleanup,
                     candidates,replay_cache,plan_sha256,program_scope_sha256,session_id,deadline_ns):
    """Return complete capture checks/analysis; candidate publication is separate.

    The two caller-owned fresh candidate files remain unpublished on failure.
    Original admission/custody, full-family identity, durable output publication
    and supervised resource/deadline enforcement remain mandatory outer gates.
    """
    try:
        before(deadline_ns);require(type(replay_cache) is ReplayCache,'actual deterministic context cache required')
        require(type(candidates) in (list,tuple) and len(candidates)==2,'two fresh independent joined candidates')
        candidate_ids={(os.fstat(s.fileno()).st_dev,os.fstat(s.fileno()).st_ino) for s in candidates}
        require(len(candidate_ids)==2,'joined candidates alias')
        prospective=prospective_capture(capture,entry);ordinal=capture['execution_ordinal']
        references=checkpoint_contract.original_references(checkpoint)
        require(len(references)==8,'all eight original artifacts required')
        declarations=tuple(SimpleNamespace(expected=BoundFile(**r)) for r in references)
        # Only validates declared checkpoint shape/lineage here. Every original
        # body must still pass its independent byte read/hash below.
        checkpoint_contract.validate_checkpoint(checkpoint,plan_sha256=plan_sha256,program_scope_sha256=program_scope_sha256,
            session_id=session_id,ordinal=ordinal,sources=declarations)
        exact(checkpoint['native_complete'],True,'native complete capture required')
        with ExitStack() as stack:
            inputs=_Inputs(root,stack,deadline_ns,references,candidate_ids)
            control=inputs.control(_binding(references[7],references[7]['size_bytes'],1))
            proof=controls.validate_capture_controls(control,checkpoint['native_result_after_private_cleanup'],capture=prospective,
                resources=entry['resources'],monitoring=entry['monitoring'],hardware_control=hardware,
                expected_layout=entry['expected_layout'],phase_bounds=entry['phases'],family_context_cleanup=family_context_cleanup,
                deadline_ns=deadline_ns)
            replay=replay_cache.get(capture,master_seed_hex,deadline_ns)
            _arena(control,capture,replay,proof['regions'])
            sources,source_reports=_sources(inputs,control,prospective,entry,references,proof['phase_windows'])
            nodes=_nodes(inputs,control,capture,replay,references[4])
            require(len(control['phases'])==2,'two original primary phases')
            phases=[];measurement=None
            for index in range(2):
                audit,latencies=_phase(inputs,control,prospective,entry,index,proof['phase_windows'][index],replay[0],
                    sources[index],references[index*2:index*2+2],candidates[index])
                phases.append(audit)
                if index==1:measurement=latencies
            inputs.finish();replay_cache.get(capture,master_seed_hex,deadline_ns)
            numerical=tails.analyze(measurement,maximum_samples=min(entry['phases'][1]['producer_attempt_limit'],tails.MAX_SAMPLES),
                deadline_ns=deadline_ns)
            inputs.finish()
            result=dict(schema_version=SCHEMA,execution_ordinal=ordinal,cell_ordinal=capture['cell_ordinal'],run_id=capture['run_id'],
                plan_sha256=plan_sha256,program_scope_sha256=program_scope_sha256,session_id=session_id,
                prospective_capture_sha256=sha(prospective),checkpoint_sha256=sha(checkpoint),original_artifacts=references,
                control_evidence=proof,source_publications=source_reports,nodes=nodes,phases=phases,tail_numerics=numerical,
                capture_validation_status='PASSED',capture_execution_evidence_validated=True,raw_reconciliation_validated=True,
                immutable_arena_validated=True,node_order_validated=True,source_publications_match_admitted_hashes=True,
                original_schedule_generation_repeated=False,prior_source_generation_verification_required=True,
                measurement_zero_loss=phases[1]['full_count']==0,warmup_zero_loss=phases[0]['full_count']==0,
                family_validity_established=False,run_validity_assessed=False,durable_joined_publication_verified=False,
                execution_authority=False,phase18_authority=False)
            before(deadline_ns);return result
    except common.ValidationError:raise
    except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,raw.DecodeError,ArchiveError) as error:
        raise common.ValidationError('S180 capture validation: '+str(error)) from error


def validate_and_publish_capture(root,*,output_directory,maximum_output_bytes,original_locations,deadline_ns,**kwargs):
    """Exclusive bounded offline result publication; failed evidence stays put.

    The qualified supervisor must first admit aggregate scratch/archive/inode,
    process and original-day budgets across all workers. This primitive checks
    its own actual output charge/capacity and never grants aggregate admission.
    An existing result directory is never adopted, cleared or retried.
    """
    before(deadline_ns);output=Path(output_directory);parent=output.parent
    require(output.is_absolute() and parent.resolve(strict=True)==parent
        and output.name not in ('','.','..'),'absolute nonsymlink output parent required')
    input_root=Path(root).resolve(strict=True)
    require(output!=input_root and not output.is_relative_to(input_root),'output must be outside original input tree')
    entry=kwargs['entry'];capture=kwargs['capture'];upper=METADATA_RESERVE
    require(type(original_locations) is dict and set(original_locations)==set(checkpoint_contract.capture_names(capture['execution_ordinal'])),
        'explicit durable locations for all eight originals required')
    for location in original_locations.values():
        raw._object(location,'artifact_uri compression','declared authoritative original location')
        require(all(type(x) is str and 0<len(x)<=4096 and '\0' not in x for x in location.values()),
            'bounded explicit original URI/compression required')
    for i,phase in enumerate(entry['phases']):
        count=uint(phase['offered_count'],'offered count')
        require(count<=(join.MAX_WARMUP if i==0 else join.MAX_MEASUREMENT),'frozen offered-count bound')
        run=capture['warmup_run_id' if i==0 else 'run_id'];upper+=count*codec.row_layout(run)[3]
    require(type(maximum_output_bytes) is int and upper<=maximum_output_bytes<=256*1024**3,
        'explicit sufficient per-capture output budget within aggregate scratch ceiling required')
    with ExitStack() as stack:
        parent_fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);stack.callback(os.close,parent_fd)
        pstat=os.fstat(parent_fd)
        require(pstat.st_uid==os.geteuid() and not pstat.st_mode&0o022,'protected caller-owned output parent required')
        fs=os.fstatvfs(parent_fd)
        require(fs.f_bavail*fs.f_frsize>=maximum_output_bytes,'actual free output capacity insufficient')
        require(fs.f_favail>=18,'actual output inode capacity insufficient')
        os.mkdir(output.name,0o700,dir_fd=parent_fd);os.fsync(parent_fd)
        fd=os.open(output.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent_fd);stack.callback(os.close,fd)
        identity=os.fstat(fd);created=set();metadata_bytes=0
        def check():
            before(deadline_ns)
            current=os.stat(output.name,dir_fd=parent_fd,follow_symlinks=False)
            require((current.st_dev,current.st_ino)==(identity.st_dev,identity.st_ino),'owned output root replaced')
            require(current.st_uid==os.geteuid() and not current.st_mode&0o077,'owned output root permissions changed')
            require(set(os.listdir(fd))==created,'unexpected object in owned result directory')
            total=max(current.st_size,current.st_blocks*512)
            for name in created:
                item=os.stat(name,dir_fd=fd,follow_symlinks=False)
                require(stat.S_ISREG(item.st_mode) and item.st_uid==os.geteuid() and item.st_nlink==1
                    and not item.st_mode&0o022,'unsafe output object')
                total+=max(item.st_size,item.st_blocks*512)
            require(total<=maximum_output_bytes and len(created)+1<=18,'actual output byte/inode budget exceeded')
            return total
        def new_file(name):
            rawfd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
            created.add(name);return rawfd
        def save(name,value):
            nonlocal metadata_bytes
            data=canonical(value);require(metadata_bytes+len(data)<=METADATA_RESERVE,'bounded result metadata exceeded')
            with os.fdopen(new_file(name),'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            metadata_bytes+=len(data);os.fsync(fd)
            return dict(file_name=name,size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        try:
            lockfd=new_file('.lock');stack.callback(os.close,lockfd);fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            save('intent.json',dict(schema_version='cpu-prefetch-stage17-s180-analysis-intent/1',
                plan_sha256=kwargs['plan_sha256'],execution_ordinal=capture['execution_ordinal'],
                original_deadline_ns=deadline_ns,maximum_output_bytes=maximum_output_bytes,
                output_upper_logical_bytes=upper,execution_authority=False))
            candidates=[stack.enter_context(os.fdopen(new_file(name+'-joined.pending.bin'),'w+b'))
                for name in ('warmup','measurement')]
            result=validate_capture(root,candidates=candidates,deadline_ns=deadline_ns,**kwargs)
            check();capture_binding=save('capture-validation.json',result)
            numerical_binding=save('tail-numerics.json',result['tail_numerics']);joined=[]
            for name,stream,audit in zip(('warmup','measurement'),candidates,result['phases'],strict=True):
                audit_id=kwargs['plan_sha256']+':analysis:'+str(capture['execution_ordinal'])+':'+name+':join-audit'
                check();audit_binding=save(name+'-join-audit.json',dict(
                    schema_version='cpu-prefetch-stage17-s180-validated-join-audit/1',
                    artifact_id=audit_id,
                    capture_validation=capture_binding,phase=name,join_status='PASSED',
                    independently_reconciled_primary_audit=audit,execution_authority=False))
                audit_binding['artifact_id']=audit_id
                os.fchmod(stream.fileno(),0o400);os.fsync(stream.fileno());stream.close()
                pending=name+'-joined.pending.bin';final=name+'-joined.bin'
                os.link(pending,final,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
                os.unlink(pending,dir_fd=fd);created.remove(pending);created.add(final)
                os.fsync(fd)
                source_refs=[dict(artifact_id=kwargs['plan_sha256']+':'+audit['primary_streams'][role]['path'],
                    sha256=audit['primary_streams'][role]['sha256']) for role in ('producer','consumer')]
                envelopes=[]
                for kind in ('PRODUCER','CONSUMER','JOINED_DERIVED'):
                    is_joined=kind=='JOINED_DERIVED'
                    original=None if is_joined else audit['primary_streams'][kind.lower()]
                    uri=(output/final).as_uri() if is_joined else original_locations[original['path']]['artifact_uri']
                    compression='NONE' if is_joined else original_locations[original['path']]['compression']
                    artifact_id=(kwargs['plan_sha256']+':analysis:'+str(capture['execution_ordinal'])+':'+name+':joined'
                        if is_joined else kwargs['plan_sha256']+':'+original['path'])
                    envelope=dict(schema_version='2.0.0-pre.3',protocol_version='2.0.0-pre.3',artifact_id=artifact_id,
                        run_id=audit['run_id'],stream_kind=kind,logical_row_schema_version='2.0.0-pre.3',
                        physical_format_record_id=codec.FORMAT_ID,encoding='U64LE_LENGTH_PREFIXED_UTF8_RUN_ID_PAD8',
                        time_unit=raw.TIME_UNIT,endianness='LITTLE_ENDIAN',compression=compression,
                        row_count=audit['joined_row_count'] if is_joined else original['row_count'],
                        byte_count=audit['joined_size_bytes'] if is_joined else original['size_bytes'],
                        immutable_ordering=True,storage=dict(mode='EXTERNAL_IMMUTABLE_ARTIFACT',artifact_uri=uri),
                        integrity_artifact_ref=dict(artifact_id=audit_id,sha256=audit_binding['sha256']),
                        artifact_sha256=audit['joined_sha256'] if is_joined else original['sha256'])
                    if is_joined:envelope['source_artifacts']=source_refs
                    envelopes.append(save(name+'-'+kind.lower()+'-envelope.json',envelope))
                joined.append(dict(phase=name,artifact=dict(file_name=final,size_bytes=audit['joined_size_bytes'],
                    sha256=audit['joined_sha256']),join_audit=audit_binding,raw_stream_envelopes=envelopes))
            charged=check()
            complete=dict(schema_version='cpu-prefetch-stage17-s180-analysis-publication/1',
                execution_ordinal=capture['execution_ordinal'],run_id=capture['run_id'],plan_sha256=kwargs['plan_sha256'],
                output_root_identity=dict(device=identity.st_dev,inode=identity.st_ino),
                capture_validation=capture_binding,tail_numerics=numerical_binding,joined=joined,
                charged_before_final_manifest_bytes=charged,maximum_output_bytes=maximum_output_bytes,
                durable_joined_publication_verified=True,aggregate_resource_admission_performed=False,
                original_archive_custody_verified=False,
                full_family_validity_established=False,execution_authority=False,phase18_authority=False)
            # The final marker is published only after its own bytes/charge and
            # all preceding evidence are durable; no earlier file implies success.
            save('complete.pending.json',complete);check()
            os.link('complete.pending.json','complete.json',src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
            os.unlink('complete.pending.json',dir_fd=fd);created.remove('complete.pending.json');created.add('complete.json')
            os.fsync(fd);check();return complete
        except BaseException as error:
            # Preserve every byte, including a late interrupted publication.
            # Failure takes precedence and an uncommitted marker is not success.
            try:
                if 'complete.json' in created:
                    os.rename('complete.json','uncommitted-complete.json',src_dir_fd=fd,dst_dir_fd=fd)
                    created.remove('complete.json');created.add('uncommitted-complete.json');os.fsync(fd)
                save('failure.json',dict(schema_version='cpu-prefetch-stage17-s180-analysis-failure/1',
                    status='FAILED',reason=str(error)[:2048],successful_result_published=False,
                    execution_authority=False,phase18_authority=False))
            except (OSError,ValueError):pass
            raise
