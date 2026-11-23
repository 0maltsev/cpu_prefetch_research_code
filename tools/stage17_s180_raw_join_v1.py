"""Independent offline S180 scheduled-phase primary join, not run admission.

Caller authenticates contract, schedule/arena provenance, full controls and
family lifetime, owns a fresh unpublished candidate file, and retains failures.
Only a returned PASSED audit permits its later durable publication. No native
joined rows/status are trusted and no experiment or filesystem publication runs.
"""
from __future__ import annotations
import array
from contextlib import ExitStack
import hashlib
import os
import stat
import struct
import time

import stage17_raw_stream_decoder_v1 as codec
import stage17_raw_stream_decoder_v2 as raw
from stage17_discovery_validation_v3 import mix

SCHEMA='cpu-prefetch-stage17-s180-primary-join/1'
CONTRACT='cpu-prefetch-stage17-s180-primary-join-contract/1'
MAX_MEASUREMENT=(5011713+1)//2
MAX_WARMUP=(5011713*5+1)//2
MAX_RECORDS=1048576
U64=2**64-1
FIELDS=('schema_version run_id phase clock_origin_absolute_nanoseconds '
    'phase_origin_relative_picoseconds duration_ticks drain_deadline_ticks '
    'source_origin_ticks source_horizon_ticks maximum_offered initial_checksum '
    'expected_checksum streams')


class JoinError(ValueError):
    def __init__(self,message):
        super().__init__('S180 raw join: '+message)
        self.audit=dict(schema_version=SCHEMA,join_status='FAILED',reason=str(message)[:2048],
            successful_joined_dataset=False,run_validity_assessed=False,
            execution_authority=False,phase18_authority=False)


def require(condition,message):
    if not condition:raise JoinError(message)


def before(deadline):
    require(type(deadline) is int and time.monotonic_ns()<deadline,'original analysis deadline expired')


def _uint(value,label):
    require(type(value) is int and 0<=value<=U64,label+' requires unsigned64 integer')
    return value


def _packed(values,maximum,label,deadline):
    require(type(values) is array.array and values.typecode=='Q' and values.itemsize==8,
        label+' requires packed unsigned64 values')
    require(len(values)<=maximum,label+' exceeds frozen bound')
    before(deadline);result=array.array('Q',values);before(deadline);return result


def _contract(contract):
    require(type(contract) is dict and set(contract)==set(FIELDS.split()),'exact phase contract fields required')
    c=dict(contract)
    require(c['schema_version']==CONTRACT and c['phase'] in ('WARMUP','MEASUREMENT'),'contract version/phase')
    run=c['run_id']
    require(type(run) is str and 0<len(run.encode())<=512
        and all(ord(x)>=32 and ord(x)!=127 for x in run),'bounded run identity required')
    for name in FIELDS.split()[3:-1]:_uint(c[name],name)
    duration=5000000000000 if c['phase']=='WARMUP' else 1000000000000
    require(c['duration_ticks']==duration,'approved five-second/one-second phase required')
    start=c['phase_origin_relative_picoseconds'];end=start+duration
    require(start%1000==0 and end<c['drain_deadline_ticks']<=U64,'phase/drain endpoint or clock resolution')
    require(c['clock_origin_absolute_nanoseconds']+(c['drain_deadline_ticks']+999)//1000<=U64,
        'absolute clock-domain endpoint overflows')
    require(c['source_horizon_ticks']==c['source_origin_ticks']+duration<=U64,'exact source horizon required')
    limit=MAX_WARMUP if c['phase']=='WARMUP' else MAX_MEASUREMENT
    require(0<c['maximum_offered']<=limit,'authenticated offered-count ceiling required')
    streams=c['streams'];require(type(streams) is dict and set(streams)=={'producer','consumer'},'two original primaries required')
    _,pb,cb,jb=codec.row_layout(run)
    c['streams']={role:dict(raw._binding(streams[role],role,size)) for role,size in (('producer',pb),('consumer',cb))}
    require(c['streams']['producer']['path']!=c['streams']['consumer']['path'],'primary paths alias')
    return c,pb,cb,jb


def _rows(stream,row_bytes,run,words):
    """Bounded blocks, full per-row identity/padding, original stream hashing."""
    encoded=run.encode();prefix_bytes=row_bytes-words*8
    expected=struct.pack('<I',len(encoded))+encoded+bytes(prefix_bytes-4-len(encoded))
    decoder=struct.Struct('<'+'Q'*words)
    remaining=stream.binding['row_count'];batch=max(1,65536//row_bytes)
    while remaining:
        count=min(remaining,batch);size=count*row_bytes;block=stream.read(size)
        require(len(block)==size,'short primary block')
        for offset in range(0,size,row_bytes):
            require(block[offset:offset+prefix_bytes]==expected,'primary run_id prefix/padding drift')
            yield decoder.unpack_from(block,offset+prefix_bytes)
        remaining-=count


def _clocks(words,offsets,origin):
    """Exact conversion for words already decoded as unsigned64 by Struct.

    An equal product fits uint64 because the stored relative word does. This
    retains the old origin and overflow conditions without rechecking Python
    integer types/bounds for every timestamp returned by the binary decoder.
    """
    for offset in offsets:
        absolute=words[offset]
        require(absolute>=origin and (absolute-origin)*1000==words[offset+1],
            'clock-domain conversion mismatch/overflow or timestamp before origin')


def _derive(root,c,order,payloads,schedule,candidate,deadline,pb,cb,jb):
    start=c['phase_origin_relative_picoseconds'];end=start+c['duration_ticks'];drain=c['drain_deadline_ticks']
    origin=c['clock_origin_absolute_nanoseconds'];source_origin=c['source_origin_ticks'];run=c['run_id']
    bindings=c['streams'];offered=len(schedule)
    require(bindings['producer']['row_count']==offered,'one producer attempt per offered arrival required')
    require(bindings['consumer']['row_count']<=offered,'consumer count exceeds offered count')
    require(candidate.seekable() and candidate.writable() and candidate.readable(),'read/write seekable candidate required')
    try:output_before=os.fstat(candidate.fileno())
    except OSError as error:raise JoinError('candidate requires an actual regular-file descriptor') from error
    require(stat.S_ISREG(output_before.st_mode) and output_before.st_size==0 and output_before.st_nlink==1
        and not output_before.st_mode&0o022 and candidate.tell()==0,'fresh private empty candidate file required')
    prefix_bytes=jb-24*8;encoded=run.encode()
    prefix=struct.pack('<I',len(encoded))+encoded+bytes(prefix_bytes-4-len(encoded))
    digest=hashlib.sha256();accepted=full=0;checksum=c['initial_checksum']
    previous_p=previous_c=start;previous_due=start;latencies=array.array('Q')
    with ExitStack() as stack:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);stack.callback(os.close,fd)
        root_before=os.fstat(fd)
        streams={role:raw._open_stream(stack,fd,binding,role) for role,binding in bindings.items()}
        producers=_rows(streams['producer'],pb,run,15);consumers=_rows(streams['consumer'],cb,run,10)
        identities={(s.before.st_dev,s.before.st_ino) for s in streams.values()}
        require(len(identities)==2 and (output_before.st_dev,output_before.st_ino) not in identities,'physical input/output alias')
        for logical,source_tick in enumerate(schedule):
            if logical%256==0:before(deadline)
            due=start+source_tick-source_origin
            require(previous_due<=due<end and source_tick>=source_origin,'source schedule order/window differs')
            previous_due=due
            p=next(producers)
            require(p[0]==logical and p[14] in (codec.ACCEPTED_FLAGS,codec.FULL_FLAGS),'producer sequence/flags differ')
            require(p[1]==order[logical%len(order)],'repeating record sequence differs')
            require(p[2]==due,'actual arrival differs from original source translation')
            _clocks(p,(3,5,7,11),origin)
            require(due<=p[4]<=p[6]<=p[8]<=p[12]<drain and previous_p<=p[4],'producer timestamp order/drain differs')
            previous_p=p[12]
            if p[14]==codec.FULL_FLAGS:
                require(p[9]==p[10]==p[13]==0,'FULL contains accepted-only fields')
                full+=1;continue
            _clocks(p,(9,),origin)
            require(p[13]==accepted and p[8]<=p[10]<=p[12],'accepted ordinal/publication bracket differs')
            require(accepted<bindings['consumer']['row_count'],'accepted event lacks consumer row')
            q=next(consumers)
            require(q[0]==accepted and q[1]==p[1],'independent accepted-ordinal/record join differs')
            _clocks(q,(2,4,6,8),origin)
            require(previous_c<=q[3]<=q[5]<=q[7]<=q[9]<drain and p[10]<=q[5],'consumer order/publication/drain differs')
            previous_c=q[9];checksum=mix(checksum,q[1],payloads[q[1]])
            joined=(accepted,p[0],p[1],logical,accepted,
                p[2],p[4],p[6],p[8],p[10],p[12],q[3],q[5],q[7],q[9],
                p[4]-p[2],p[6]-p[4],p[12]-p[8],p[10]-p[2],q[5]-p[10],
                q[7]-q[3],q[9]-q[5],q[9]-q[7],q[9]-p[2])
            require(joined[18]+joined[19]+joined[21]==joined[23],'additive latency partition differs')
            row=prefix+struct.pack('<24Q',*joined)
            require(candidate.write(row)==len(row),'short candidate write')
            digest.update(row)
            if c['phase']=='MEASUREMENT':latencies.append(joined[23])
            accepted+=1
        require(bindings['consumer']['row_count']==accepted,'unmatched consumer observations')
        for stream in streams.values():stream.finish()
        require(checksum==c['expected_checksum'],'full-drain payload checksum differs')
        after=os.stat(root,follow_symlinks=False)
        require((after.st_dev,after.st_ino)==(root_before.st_dev,root_before.st_ino),'raw root replaced')
    before(deadline);candidate.flush();os.fsync(candidate.fileno())
    out=os.fstat(candidate.fileno())
    require((out.st_dev,out.st_ino)==(output_before.st_dev,output_before.st_ino)
        and out.st_nlink==1 and not out.st_mode&0o022 and out.st_size==accepted*jb,'candidate identity/extent differs')
    candidate.seek(0);reread=hashlib.sha256();remaining=out.st_size
    while remaining:
        before(deadline);block=candidate.read(min(1048576,remaining))
        require(block,'short candidate reconstruction');reread.update(block);remaining-=len(block)
    require(not candidate.read(1) and reread.digest()==digest.digest(),'candidate reconstructed bytes differ')
    final=os.fstat(candidate.fileno())
    require((out.st_dev,out.st_ino,out.st_size,out.st_mtime_ns,out.st_ctime_ns)==
        (final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns,final.st_ctime_ns),'candidate changed during verification')
    before(deadline)
    audit=dict(schema_version=SCHEMA,join_status='PASSED',run_id=run,phase=c['phase'],
        physical_format=codec.FORMAT_ID,time_unit=raw.TIME_UNIT,endianness='LITTLE',
        offered_count=offered,attempted_count=offered,accepted_count=accepted,full_count=full,consumed_count=accepted,
        zero_loss_status='PASS' if not full else 'FAIL',payload_checksum=checksum,
        producer_last_completion_ticks=previous_p,consumer_last_action_ticks=previous_c,
        primary_streams=bindings,joined_row_count=accepted,joined_row_bytes=jb,
        joined_size_bytes=out.st_size,joined_sha256=digest.hexdigest(),
        measurement_latencies_including_normal_drain=len(latencies),record_index_is_event_identity=False,
        successful_joined_dataset_published=False,raw_reconciliation_performed=True,
        source_provenance_verified=False,full_controls_verified=False,family_lifetime_verified=False,
        run_validity_assessed=False,effective_tail_status='NOT_EVALUATED',execution_authority=False,phase18_authority=False)
    return audit,latencies


def derive_phase(root,contract,*,record_order,payloads,schedule_ticks,candidate,deadline_ns):
    """Return audit and measurement latencies only after complete reconstruction.

    On failure retain the original primaries and unpublished candidate; caller
    must durably retain JoinError.audit and stop. No retries/publication here.
    """
    try:
        before(deadline_ns);c,pb,cb,jb=_contract(contract)
        order=_packed(record_order,MAX_RECORDS,'record order',deadline_ns)
        values=_packed(payloads,MAX_RECORDS,'payloads',deadline_ns)
        schedule=_packed(schedule_ticks,c['maximum_offered'],'source schedule',deadline_ns)
        require(0<len(order)==len(values),'nonempty equal record/payload extents required')
        seen=bytearray(len(order))
        for i,value in enumerate(order):
            if i%256==0:before(deadline_ns)
            require(value<len(order) and not seen[value],'record order must be a permutation')
            seen[value]=1
        return _derive(root,c,order,values,schedule,candidate,deadline_ns,pb,cb,jb)
    except JoinError:raise
    except (OSError,ValueError,TypeError,KeyError,OverflowError,codec.DecodeError) as error:
        raise JoinError(str(error)) from error
