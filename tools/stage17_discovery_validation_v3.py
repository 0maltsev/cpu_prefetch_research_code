"""Independent D207 retained-byte validation (D213 successor), no execution authority.

Raw streams are processed one row/chunk at a time. Large JSON drain arrays are
spooled to temporary files; all other JSON has explicit software memory bounds.
Unknown/missing evidence fails closed. Native status flags are cross-checked
against retained observations, not used as substitutes for those observations.
"""
from __future__ import annotations

import array
import contextlib
import hashlib
import hmac
import itertools
import json
import os
import pathlib
import re
import stat
import struct
import tempfile
from dataclasses import dataclass

import stage17_discovery_contract_v2 as contract
import stage17_output_registry_v10 as registry
import stage17_q16a_discovery_v2 as selector
import stage17_raw_stream_decoder_v1 as codec
import stage17_discovery_environment_v1 as environment

U64 = (1 << 64) - 1
CHUNK = 1024 * 1024
MAX_JSON_NODES = 10_000_000
MAX_TOKEN_BYTES = CHUNK
MAX_RESIDENT_TEXT = 256 * CHUNK
MAX_ARENA_BYTES = 128 * CHUNK
MAX_PACKED_PAGE_BYTES = 256 * CHUNK
PAGE_BLOCK_ITEMS = 8192
PAGE_DELIMITER = re.compile(r'[,\]\s]')


class PackedPages:
    """Fixed 64-KiB numeric blocks; reader charges capacity before allocation.

    No retained Python int per page, no append-growth allocation, and no
    conversion of these arrays back to lists. Final block slack is charged too.
    """
    def __init__(self, signed):
        self.typecode = 'q' if signed else 'Q'
        self.blocks = []
        self.count = 0

    def __len__(self):
        return self.count

    def __iter__(self):
        for ordinal, block in enumerate(self.blocks):
            yield from itertools.islice(block, min(PAGE_BLOCK_ITEMS,
                                                   self.count - ordinal * PAGE_BLOCK_ITEMS))


class ValidationError(ValueError):
    """Invalid or unsupported retained evidence; never a selection result."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def uint(value, label):
    require(type(value) is int and 0 <= value <= U64, label + ': expected uint64')
    return value


def exact(value, expected, label):
    # bool/int equality must not admit a different JSON type.
    require(type(value) is type(expected) and value == expected, label + ': differs')
    if isinstance(expected,dict):
        for key in expected: exact(value[key],expected[key],label+'.'+key)
    elif isinstance(expected,(list,tuple)):
        for actual,wanted in zip(value,expected,strict=True):exact(actual,wanted,label+'[]')


class Spool:
    def __init__(self, stack):
        self.file = stack.enter_context(tempfile.TemporaryFile(mode='w+b'))
        self.count = 0

    def append(self, value):
        self.file.write(json.dumps(value, separators=(',', ':')).encode() + b'\n')
        self.count += 1

    def __len__(self):
        return self.count

    def __iter__(self):
        self.file.seek(0)
        for line in self.file:
            yield json.loads(line)


class JsonReader:
    """Strict JSON: drains spooled, page integers packed, other metadata bounded."""
    def __init__(self, stream, stack):
        self.stream, self.stack = stream, stack
        self.buffer, self.pos, self.nodes, self.text_bytes = '', 0, 0, 0
        self.packed_bytes = 0

    def packed_pages(self, key, depth):
        signed = key == 'page_status'
        result = PackedPages(signed)
        require(array.array(result.typecode).itemsize == 8, 'unsupported packed integer ABI')
        low, high = (-(1 << 63), (1 << 63) - 1) if signed else (0, U64)
        self.ws()
        if self.peek() == ']':
            self.take(); return result
        require(depth + 1 < 64, 'unsupported JSON resident metadata size/depth')
        while True:
            self.ws()
            token = ''
            while self.peek():
                delimiter = PAGE_DELIMITER.search(self.buffer, self.pos)
                end = delimiter.start() if delimiter else len(self.buffer)
                token += self.buffer[self.pos:end]
                self.pos = end
                require(len(token) <= 20, 'packed page integer token size')
                if delimiter:
                    break
            require(re.fullmatch(r'-?(?:0|[1-9][0-9]*)', token) is not None,
                    'packed page value must be a JSON integer')
            value = int(token)
            require(low <= value <= high, 'packed page integer range')
            offset = result.count % PAGE_BLOCK_ITEMS
            if offset == 0:
                capacity = PAGE_BLOCK_ITEMS * 8
                require(self.packed_bytes + capacity <= MAX_PACKED_PAGE_BYTES,
                        'unsupported cumulative packed page capacity')
                self.packed_bytes += capacity
                result.blocks.append(array.array(result.typecode, [0]) * PAGE_BLOCK_ITEMS)
            result.blocks[-1][offset] = value
            result.count += 1
            self.ws(); end = self.take()
            if end == ']':
                return result
            require(end == ',', 'JSON packed page array delimiter')

    def peek(self):
        if self.pos == len(self.buffer):
            self.buffer = self.stream.read(65536)
            self.pos = 0
        return self.buffer[self.pos:self.pos + 1]

    def take(self):
        value = self.peek()
        self.pos += bool(value)
        return value

    def ws(self):
        while self.peek() and self.peek() in ' \r\n\t':
            self.take()

    def value(self, key='', depth=0):
        self.nodes += 1
        require(self.nodes <= MAX_JSON_NODES and depth < 64,
                'unsupported JSON resident metadata size/depth')
        self.ws()
        char = self.take()
        if char == '{':
            result = {}
            self.ws()
            if self.peek() == '}':
                self.take(); return result
            while True:
                name = self.value(depth=depth + 1)
                require(type(name) is str and name not in result, 'JSON duplicate/nonstring key')
                self.ws(); require(self.take() == ':', 'JSON missing colon')
                result[name] = self.value(name, depth + 1)
                self.ws(); end = self.take()
                if end == '}': return result
                require(end == ',', 'JSON object delimiter')
        if char == '[':
            if key in ('page_addresses', 'page_status'):
                return self.packed_pages(key, depth)
            result = Spool(self.stack) if key == 'drain_rows' else []
            self.ws()
            if self.peek() == ']':
                self.take(); return result
            while True:
                previous,previous_text = self.nodes,self.text_bytes
                result.append(self.value(depth=depth + 1))
                if isinstance(result, Spool): self.nodes,self.text_bytes = previous,previous_text
                self.ws(); end = self.take()
                if end == ']': return result
                require(end == ',', 'JSON array delimiter')
        token = [char]
        if char == '"':
            escaped = False
            while True:
                ch = self.take()
                require(bool(ch), 'JSON unfinished string')
                token.append(ch)
                require(len(token) <= MAX_TOKEN_BYTES, 'unsupported JSON token size')
                if ch == '"' and not escaped: break
                escaped = ch == '\\' and not escaped
        else:
            while self.peek() and self.peek() not in ',]} \r\n\t':
                token.append(self.take())
                require(len(token) <= MAX_TOKEN_BYTES, 'unsupported JSON token size')
        self.text_bytes += len(token)*4
        require(self.text_bytes<=MAX_RESIDENT_TEXT,'unsupported JSON resident string size')
        result = json.loads(''.join(token))
        require(not isinstance(result, float), 'noninteger/nonfinite JSON evidence')
        return result

    def document(self):
        result = self.value()
        self.ws(); require(not self.peek(), 'JSON trailing data')
        return result


@contextlib.contextmanager
def opened(root, binding):
    name = binding['file_name']
    require(isinstance(name, str) and name not in ('', '.', '..') and '/' not in name,
            'unsafe retained filename')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(descriptor, 'rb', buffering=CHUNK) as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), 'not a regular retained file')
        exact(info.st_size, binding['size_bytes'], 'artifact byte count')
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(CHUNK), b''): digest.update(chunk)
        exact(digest.hexdigest(), binding['sha256'], 'artifact SHA256')
        stream.seek(0)
        yield stream
        after = os.fstat(stream.fileno())
        require((after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
                (info.st_size, info.st_mtime_ns, info.st_ctime_ns), 'artifact changed during validation')


@contextlib.contextmanager
def document(root, binding):
    import io
    with contextlib.ExitStack() as stack:
        raw = stack.enter_context(opened(root, binding))
        text = io.TextIOWrapper(raw, encoding='utf-8', errors='strict')
        try:
            yield JsonReader(text, stack).document()
        finally:
            text.detach()


def field(data):
    return struct.pack('>Q', len(data)) + data


def key(seed, namespace, purpose):
    message = b''.join(field(v.encode()) for v in
                       ('2.0.0-pre.1', 'PHILOX4X32-10-HMAC-SHA256-v1', namespace, purpose))
    return struct.unpack('>2I', hmac.digest(bytes.fromhex(seed), message, 'sha256')[:8])


def block(stream_key, ordinal):
    k0, k1 = stream_key
    a, b, c, d = ordinal >> 32, ordinal & 0xffffffff, 0, 0
    for _ in range(10):
        p, q = 0xd2511f53 * a, 0xcd9e8d57 * c
        a, b, c, d = ((q >> 32) ^ b ^ k0, q & 0xffffffff,
                      (p >> 32) ^ d ^ k1, p & 0xffffffff)
        k0, k1 = (k0 + 0x9e3779b9) & 0xffffffff, (k1 + 0xbb67ae85) & 0xffffffff
    return (a << 32) | b, (c << 32) | d


def draw(stream_key, ordinal):
    return block(stream_key,ordinal//2)[ordinal%2]


def draws(stream_key):
    ordinal=0
    while True:
        yield from block(stream_key,ordinal)
        ordinal+=1


def mix(state, index, payload):
    value = ((state + 0x9e3779b97f4a7c15) & U64) ^ index
    value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & U64
    value ^= payload
    value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & U64
    return value ^ (value >> 31)


class Arena:
    """Replay one immutable arena, bounded packed arrays (not Python-int lists)."""
    def __init__(self, capture):
        g = capture.geometry
        self.line_bytes=g.cache_line_bytes
        require(16<=g.cache_line_bytes<=CHUNK,'unsupported replay record stride')
        require(g.capacity * 16 <= MAX_ARENA_BYTES, 'unsupported arena replay memory bound')
        # Fixed-size packed allocation: avoid append-growth overhead at the
        # 8,388,608-record context, and never construct an O(N) Python-int list.
        self.order = array.array('Q',[0]) * g.capacity
        self.payload = array.array('Q',[0]) * g.capacity
        for i in range(g.capacity):self.order[i]=i
        order_key = key(capture.arena_seed.seed_hex, capture.arena_seed.namespace_id, 'event-order')
        payload_key = key(capture.arena_seed.seed_hex, capture.arena_seed.namespace_id, 'event-payload')
        order_draws=draws(order_key);payload_draws=draws(payload_key)
        for remaining in range(g.capacity, 1, -1):
            threshold = ((-remaining) & U64) % remaining
            while True:
                value = next(order_draws)
                if value >= threshold: break
            selected = value % remaining
            self.order[remaining - 1], self.order[selected] = self.order[selected], self.order[remaining - 1]
        content, order_hash, delta_hash = (hashlib.sha256() for _ in range(3))
        content.update(field(b'cpu-prefetch/event-record-content-sha256/v1'))
        order_hash.update(field(b'cpu-prefetch/ordered-index-sha256/v1'))
        delta_hash.update(field(b'cpu-prefetch/address-delta-sha256/v1'))
        def number(digest, value): digest.update(field(struct.pack('>Q', value & U64)))
        number(content, g.cache_line_bytes)
        for digest in (content, order_hash, delta_hash): number(digest, g.capacity)
        for i in range(g.capacity):
            payload = next(payload_draws); self.payload[i]=payload
            number(content, i); number(content, payload)
            number(content, g.cache_line_bytes - 16)
            content.update(field(bytes(g.cache_line_bytes - 16)))
            number(order_hash, self.order[i])
            number(delta_hash, (self.order[(i + 1) % g.capacity] - self.order[i]) * g.cache_line_bytes)
        self.hashes = (content.hexdigest(), order_hash.hexdigest(), delta_hash.hexdigest())


def clock_pair(absolute, relative, origin, label):
    uint(absolute, label); uint(relative, label); uint(origin,label+' origin')
    exact(relative, (absolute - origin) * 1000, label + ' clock conversion')
    return relative


def clock(value, origin, label):
    exact(value['status'], 0, label + ' clock status')
    return clock_pair(value['absolute_nanoseconds'], value['relative_picoseconds'], origin, label)


def call(value, expected=0, *, minimum=None):
    require(isinstance(value, dict), 'missing syscall evidence')
    exact(value['error_number'], 0, 'syscall errno')
    result = value['return_value']
    require(type(result) is int and -(1<<63)<=result<(1<<63)
            and (result == expected if minimum is None else result >= minimum),
            'failed syscall return')
    return result


@dataclass(frozen=True)
class PhaseValidation:
    attempted: int
    accepted: int
    full: int
    consumed: int
    counts: selector.ObservationCounts
    elapsed_ns: int
    capacity_limited: bool
    drain_begin_tick: int
    drain_end_tick: int

    @property
    def zero_loss(self): return self.full == 0


def current_capture(event, outcome, clock_origin):
    require(event['failed_boundary'] is None,'current event boundary failure')
    captured=event['capture']
    exact(captured['operation_performed'],True,'current operation performed')
    exact(captured['outcome'],outcome,'current attempt outcome')
    exact(captured['operation_outcome'],outcome,'current operation outcome')
    exact(captured['before_status'],0,'current before clock')
    exact(captured['after_status'],0,'current after clock')
    require(captured['failed_clock_status'] is None,'current failed clock')
    before=clock(event['demand_before'],clock_origin,'current demand before')
    after=clock(event['demand_after'],clock_origin,'current demand after')
    require(before<after,'current nonpositive demand')
    return before,after


def validate_current(root,phase,workers,*,run_id,clock_origin,arena,arena_address):
    _,pbytes,cbytes,_=codec.row_layout(run_id)
    pcount=workers[0]['attempts'];advanced=workers[1]['advanced']
    for role,count in (('producer',pcount),('consumer',workers[1]['attempts'])):
        event=phase[role+'_current']
        if not count:
            exact(event['capture']['operation_performed'],False,'unattempted current event')
            require(event['primary'] is None,'unattempted primary')
            continue
        worker=workers[0 if role=='producer' else 1];outcome=worker['last_attempt_outcome']
        require(outcome in ((0,1) if role=='producer' else (0,2)),'wrong owner current outcome')
        before,after=current_capture(event,outcome,clock_origin)
        demand_index=(count-1 if role=='producer' else
                      pcount+max(workers[0]['advanced']-1,0)+count-1)
        with opened(root,phase['demand']) as stream:
            stream.seek(demand_index*8);payload=stream.read(8)
            require(len(payload)==8,'missing current demand value')
            exact(struct.unpack('<Q',payload)[0],after-before,'current demand agrees with raw vector')
        if role=='producer':
            with opened(root,phase[role]) as stream:
                stream.seek((pcount-1)*pbytes);p=codec._row(stream,pbytes,run_id,15,'current producer')
            exact(outcome,1 if p[14]==codec.FULL_FLAGS else 0,'current producer raw outcome')
            exact(event['requested_attempt'],dict(logical_sequence=p[0],scheduled_arrival=p[2],
                candidate_accepted_ordinal=workers[0]['advanced']-(outcome==0)),'current producer request')
            exact(event['selected'],dict(record_index=p[1],record_address=arena_address+p[1]*arena.line_bytes),'current selected record')
            row=event['primary']
            for name,value in dict(logical_sequence=p[0],record_index=p[1],scheduled_arrival=p[2],outcome=outcome,
                                   accepted_ordinal=p[13] if outcome==0 else None).items():exact(row[name],value,'current producer primary '+name)
            for event_name,primary_name,i in (('handle_begin','producer_handle_begin',3),('lookup_completion','record_lookup_completion',5),
                                              ('enqueue_invocation','enqueue_invocation',7),('enqueue_completion','enqueue_attempt_completion',11)):
                exact(clock(event[event_name],clock_origin,event_name),p[i+1],'current producer clock')
                exact(row[primary_name],dict(absolute_nanoseconds=p[i],relative_picoseconds=p[i+1]),'current producer primary clock')
            require(p[8]<=before<after<=p[12],'current producer demand boundaries')
            if outcome==0:
                exact(clock(event['enqueue_publication'],clock_origin,'current publication'),p[10],'current publication')
                exact(row['enqueue_linearization'],dict(absolute_nanoseconds=p[9],relative_picoseconds=p[10]),'current linearization')
                require(after<=p[10],'demand after publication')
            else:require(event['enqueue_publication'] is None and row['enqueue_linearization'] is None,'FULL publication')
        else:
            invocation=clock(event['dequeue_invocation'],clock_origin,'current consumer invocation')
            require(invocation<=before,'current consumer demand before invocation')
            exact(event['candidate_consumed_ordinal'],advanced-(outcome==0),'current consumer candidate')
            exact(event['operation']['status'],0 if outcome==0 else 1,'current dequeue status')
            if outcome==2:
                require(event['operation']['event_address'] is None and all(event[name] is None for name in
                    ('primary','dequeue_observation','dequeue_completion','action_completion','access')),'EMPTY item-only observations')
                continue
            require(advanced>0,'advanced current without raw row')
            with opened(root,phase[role]) as stream:
                stream.seek((advanced-1)*cbytes);c=codec._row(stream,cbytes,run_id,10,'current consumer')
            exact(event['primary']['consumed_ordinal'],c[0],'current consumer ordinal')
            exact(event['primary']['observed_record_index'],c[1],'current consumer index')
            for event_name,primary_name,i in (('dequeue_invocation','dequeue_invocation',2),('dequeue_observation','dequeue_linearization',4),
                                              ('dequeue_completion','dequeue_completion',6),('action_completion','consumer_action_completion',8)):
                exact(clock(event[event_name],clock_origin,event_name),c[i+1],'current consumer clock')
                exact(event['primary'][primary_name],dict(absolute_nanoseconds=c[i],relative_picoseconds=c[i+1]),'current consumer primary clock')
            require(after<=c[5],'consumer demand after observation')
            exact(event['access'],dict(status=0,record_index=c[1],payload=arena.payload[c[1]]),'current record access')
            exact(event['operation']['event_address'],arena_address+c[1]*arena.line_bytes,'current record address')


def validate_phase(root, phase, workers, drain, *, run_id, phase_origin,
                   clock_origin, duration_ns, attempt_capacity, drain_capacity,
                   initial_checksum, arena, reset_required, arena_address):
    """Independent physical two-stream reconciliation; drain excluded from counts."""
    exact(phase['run_id'], run_id, 'producer identity')
    exact(phase['consumer_run_id'], run_id, 'consumer identity')
    for flag in ('producer_available', 'consumer_available', 'producer_prefix_complete', 'consumer_prefix_complete'):
        exact(phase[flag], True, flag)
    exact(phase['drain_retention_exhausted'], False, 'drain retention')
    require(len(workers) == 2, 'two worker results required')
    capacity_limited = any(w['stop'] == 1 for w in workers)
    stops = [w['stop'] for w in workers]
    require(all(type(s) is int and s in (0, 1, 6) for s in stops), 'worker mandatory stop')
    require(capacity_limited or stops == [0, 0], 'peer stopped without capacity cause')
    exact(phase['capture_horizon_complete'], not capacity_limited, 'horizon completeness')
    deadline = phase_origin + duration_ns * 1000
    for w in workers:
        for name in ('attempts', 'advanced', 'full', 'empty'): uint(w[name], name)
        if w['last_observed_tick'] is None:
            require(w['stop']==6 and w['attempts']==0,'missing observed worker clock')
        else:uint(w['last_observed_tick'],'last observed tick')
        require(w['failed_clock_status'] is None, 'failed worker clock')
        require(w['attempts'] <= attempt_capacity, 'attempt capacity exceeded')
        if w['stop'] == 0: require(w['last_observed_tick'] >= deadline, 'early fixed deadline')
        if w['stop'] == 1:
            exact(w['attempts'], attempt_capacity, 'capacity stop count')
            require(phase_origin<=w['last_observed_tick']<deadline,'capacity stop outside half-open horizon')
        if w['attempts']:
            require(type(w['last_attempt_outcome']) is int and w['last_attempt_outcome'] in (0,1,2), 'failed last worker attempt')
            exact(w['last_operation_outcome'],w['last_attempt_outcome'],'last operation outcome')
            exact(w['last_attempt_before_status'],0,'last attempt before clock')
            exact(w['last_attempt_after_status'],0,'last attempt after clock')
        else:
            require(all(w[name] is None for name in ('last_attempt_outcome','last_operation_outcome',
                'last_attempt_before_status','last_attempt_after_status')),'unattempted worker has attempt evidence')
    exact(drain['stop'], 0, 'drain stop')
    exact(drain['reset_verified'], reset_required, 'drain reset')
    require(drain['failed_clock_status'] is None, 'drain clock failure')
    require(uint(drain['attempts'], 'drain attempts') <= drain_capacity, 'drain capacity exceeded')
    audit = drain['final_audit']
    exact(audit['occupied_slots'], 0, 'drain occupancy')
    exact(audit['positions_in_range'], True, 'drain positions')
    exact(audit['producer_position'], audit['consumer_position'], 'empty cursors')
    require(uint(audit['producer_position'],'producer cursor')<len(arena.order) and
            uint(audit['consumer_position'],'consumer cursor')<len(arena.order),'drain cursor outside ring')
    uint(drain['last_observed_tick'],'drain final clock')
    prefix, pbytes, cbytes, jbytes = codec.row_layout(run_id)
    counts = []
    for role, row_bytes, stream_kind in (('producer', pbytes, 0), ('consumer', cbytes, 1)):
        binding, snapshot = phase[role], phase[role + '_snapshot']
        exact(binding['schema_identity'], codec.FORMAT_ID, 'raw codec')
        exact(binding['role'], 'DISCOVERY_' + role.upper() + '_RAW', 'raw role')
        size = uint(binding['size_bytes'], 'raw byte size')
        require(size % row_bytes == 0, 'raw partial row')
        count = size // row_bytes; counts.append(count)
        for name, expected in dict(run_id=run_id,stream_kind=stream_kind,row_count=count,
                                   row_bytes=row_bytes,retained_bytes=size,overflowed=False,
                                   completeness='SEALED_INCOMPLETE' if capacity_limited else 'SEALED_COMPLETE').items():
            exact(snapshot[name], expected, 'snapshot.' + name)
        require(count <= uint(snapshot['row_capacity'], 'row capacity'), 'raw capacity exceeded')
        exact(snapshot['row_capacity'], attempt_capacity, 'snapshot capacity')
        expected_layout = dict(run_id_bytes=len(run_id.encode()),prefix_bytes=prefix,
                               producer_row_bytes=pbytes,consumer_row_bytes=cbytes,joined_row_bytes=jbytes)
        exact(phase[role + '_layout'], expected_layout, 'row layout')
    pcount, ccount = counts
    accepted = full = 0; checksum = initial_checksum
    last_producer = last_consumer = phase_origin
    with (opened(root, phase['producer']) as ps, opened(root, phase['consumer']) as cs,
          opened(root,phase['demand']) as demands):
        for logical in range(pcount):
            p = codec._row(ps, pbytes, run_id, 15, 'producer')
            exact(p[0], logical, 'logical sequence')
            exact(p[1], arena.order[logical % len(arena.order)], 'record order')
            require(p[14] in (codec.ACCEPTED_FLAGS, codec.FULL_FLAGS), 'producer flags')
            times = [clock_pair(p[i], p[i+1], clock_origin, 'producer') for i in (3,5,7,11)]
            require(last_producer <= times[0] <= times[1] <= times[2] <= times[3], 'producer boundary order')
            require(phase_origin <= p[2] <= times[0] and p[2] < deadline, 'producer half-open horizon')
            last_producer = times[-1]
            demand=demands.read(8);require(len(demand)==8,'short producer demand')
            require(struct.unpack('<Q',demand)[0] <= times[3]-times[2], 'producer demand exceeds actual enqueue boundaries')
            if p[14] == codec.FULL_FLAGS:
                require(p[9] == p[10] == p[13] == 0, 'FULL accepted-only fields')
                full += 1; continue
            exact(p[13], accepted, 'accepted ordinal')
            pub = clock_pair(p[9], p[10], clock_origin, 'publication')
            require(times[2] <= pub <= times[3], 'publication boundary')
            c = codec._row(cs, cbytes, run_id, 10, 'consumer')
            exact(c[0], accepted, 'consumer ordinal'); exact(c[1], p[1], 'consumer record')
            ct = [clock_pair(c[i], c[i+1], clock_origin, 'consumer') for i in (2,4,6,8)]
            require(last_consumer <= ct[0] <= ct[1] <= ct[2] <= ct[3] and pub <= ct[1],
                    'consumer boundary order')
            last_consumer = ct[-1]
            # Consumer admission is the qualified loop's preceding clock read,
            # not dequeue_invocation. An admitted attempt may cross the horizon;
            # the physical consumer codec does not retain that admission read.
            if accepted < workers[1]['advanced'] and workers[1]['stop'] in (0,1):
                require(ct[-1]<=workers[1]['last_observed_tick'],'consumer action after final worker clock')
            checksum = mix(checksum, p[1], arena.payload[p[1]])
            accepted += 1
        require(not ps.read(1) and not cs.read(1), 'raw trailing bytes')
    exact(ccount, accepted, 'drained consumer count')
    exact(audit['producer_position'],accepted%len(arena.order),'drained cursor from accepted raw events')
    if workers[0]['stop'] in (0,1):
        require(last_producer<=workers[0]['last_observed_tick'],'producer action after final worker clock')
    for name, expected in dict(attempted=pcount,accepted=accepted,full=full,
                               producer_row_count=pcount,consumer_row_count=ccount,
                               consumed_including_drain=ccount,initial_checksum=initial_checksum,
                               checksum=checksum,drain_requests=drain['attempts']).items():
        exact(phase[name], expected, name)
    exact(phase['producer_last_append'],0 if pcount else None,'producer append status')
    exact(phase['consumer_last_append'],0 if ccount else None,'consumer append status')
    exact(phase['consumer_last_join'],dict(status=1,matched=ccount,failed_producer_row=None),'independent join agrees')
    exact(workers[0]['attempts'], pcount, 'producer attempts')
    exact(workers[0]['advanced'], accepted, 'producer advanced')
    exact(workers[0]['full'], full, 'producer FULL'); exact(workers[0]['empty'], 0, 'producer EMPTY')
    exact(workers[1]['full'], 0, 'consumer FULL')
    exact(workers[1]['attempts'], workers[1]['advanced'] + workers[1]['empty'], 'consumer accounting')
    exact(ccount, workers[1]['advanced'] + drain['dequeued'], 'consumer drain accounting')
    exact(phase['producer_nonadvancing'], full, 'producer nonadvancing')
    exact(phase['consumer_nonadvancing'], workers[1]['empty'], 'consumer nonadvancing')
    names = ('producer_demand','producer_issue','consumer_demand','consumer_issue')
    exact(phase['demand']['role'],'DISCOVERY_DEMAND_RAW','demand role')
    exact(phase['demand']['schema_identity'],'DISCOVERY-FOUR-U64LE-VECTORS-v1','demand codec')
    expected_counts = (pcount,max(accepted-1,0),workers[1]['attempts'],max(workers[1]['advanced']-1,0))
    # A peer-stopped owner can finish an in-flight operation after the other
    # owner signals capacity, then exit before another loop clock read. Bound
    # its retained durations by actual event endpoints, not a fabricated poll.
    observed_ticks=[w['last_observed_tick'] for w in workers if w['last_observed_tick'] is not None]
    for role,w in zip(('producer','consumer'),workers,strict=True):
        if w['attempts']:
            event=phase[role+'_current']
            endpoint=(event['enqueue_completion'] if role=='producer' else
                      event['action_completion'] if event['action_completion'] is not None else event['demand_after'])
            observed_ticks.append(clock(endpoint,clock_origin,'last measured event'))
    observed_end=max(observed_ticks)
    vectors = phase['demand_vectors']; require(len(vectors) == 4, 'four demand vectors required')
    offset = 0
    with opened(root, phase['demand']) as stream:
        for item, name, count in zip(vectors,names,expected_counts,strict=True):
            exact(item, dict(name=name,available=True,offset_bytes=offset,count=count), 'demand vector geometry')
            for remaining in range(0,count,CHUNK//8):
                payload = stream.read(min(count-remaining,CHUNK//8)*8)
                require(len(payload) == min(count-remaining,CHUNK//8)*8, 'short demand vector')
                for (value,) in struct.iter_unpack('<Q',payload):
                    require(value%1000==0 and 0 < value <= observed_end - phase_origin,
                            'demand/issue duration outside observed horizon')
            offset += count * 8
        require(not stream.read(1), 'demand trailing bytes')
    exact(phase['demand']['size_bytes'],offset,'demand bytes')
    # Demand-start clocks are not all published separately. Advancing issue
    # intervals must nevertheless fit the independent primary clock brackets.
    for role,wordcount,row_bytes,start,end,advanced,offset in (
            ('producer',15,pbytes,8,10,accepted,pcount*8),
            ('consumer',10,cbytes,3,5,workers[1]['advanced'],sum(expected_counts[:3])*8)):
        previous=None;seen=0
        with opened(root,phase[role]) as raw,opened(root,phase['demand']) as issues:
            issues.seek(offset)
            for i in range(pcount if role=='producer' else advanced):
                row=codec._row(raw,row_bytes,run_id,wordcount,'issue boundary')
                if role=='producer' and row[14]==codec.FULL_FLAGS:continue
                low,high=row[start],row[end]
                if previous is not None:
                    payload=issues.read(8);require(len(payload)==8,'short issue interval')
                    delta=struct.unpack('<Q',payload)[0]
                    require(max(0,low-previous[1])<=delta<=high-previous[0],
                            role+' issue interval contradicts primary boundaries')
                previous=(low,high);seen+=1
            exact(seen,advanced,'issue advancing count')
    rows = phase['drain_rows']; exact(len(rows),drain['attempts'],'drain raw count')
    drained = 0;drain_begin=None;prior_drain_end=phase_origin
    with opened(root,phase['consumer']) as stream:
        stream.seek(workers[1]['advanced']*cbytes)
        for index,event in enumerate(rows):
            require(event['failed_boundary'] is None, 'drain boundary failure')
            captured = event['capture']
            exact(captured['operation_performed'],True,'drain operation')
            require(captured['failed_clock_status'] is None, 'drain event clock failure')
            exact(captured['before_status'],0,'drain before status');exact(captured['after_status'],0,'drain after status')
            before = clock(event['demand_before'],clock_origin,'drain demand before')
            after = clock(event['demand_after'],clock_origin,'drain demand after')
            begin=clock(event['dequeue_invocation'],clock_origin,'drain invocation')
            require(begin>=prior_drain_end,'drain attempt clock order')
            if drain_begin is None:drain_begin=begin
            require(begin<=before<=after,'drain demand reversal')
            is_last=index==len(rows)-1
            exact(event['candidate_consumed_ordinal'],workers[1]['advanced']+drained,'drain candidate ordinal')
            exact(captured['outcome'],2 if is_last else 0,'drain outcome')
            exact(captured['operation_outcome'],2 if is_last else 0,'drain operation outcome')
            exact(event['operation']['status'],1 if is_last else 0,'drain dequeue status')
            if is_last:
                require(event['primary'] is None and event['operation']['event_address'] is None,'final drain must observe EMPTY')
                require(all(event[name] is None for name in ('dequeue_observation','dequeue_completion','action_completion','access')),
                        'EMPTY contains item-only observations')
                require(prior_drain_end<=drain['last_observed_tick']<=begin,'final drain poll clock')
                prior_drain_end=after
                continue
            observation=clock(event['dequeue_observation'],clock_origin,'drain observation')
            end=clock(event['dequeue_completion'],clock_origin,'drain completion')
            action=clock(event['action_completion'],clock_origin,'drain action')
            require(after<=observation<=end<=action,'drain item boundary order')
            prior_drain_end=action
            row=event['primary'];ordinal=workers[1]['advanced']+drained
            c=codec._row(stream,cbytes,run_id,10,'drain consumer')
            exact(c[0],ordinal,'drain ordinal');exact(row['consumed_ordinal'],ordinal,'drain retained ordinal')
            exact(row['observed_record_index'],c[1],'drain record index')
            for name,offset in (('dequeue_invocation',2),('dequeue_linearization',4),('dequeue_completion',6),('consumer_action_completion',8)):
                exact(row[name],dict(absolute_nanoseconds=c[offset],relative_picoseconds=c[offset+1]),'drain primary '+name)
            exact(event['access']['status'],0,'drain record access')
            exact(event['access']['record_index'],c[1],'drain access index')
            exact(event['access']['payload'],arena.payload[c[1]],'drain actual payload')
            exact(event['operation']['event_address'],arena_address+c[1]*arena.line_bytes,'drain actual record address')
            exact((begin,observation,end,action),(c[3],c[5],c[7],c[9]),'drain primary/event clock agreement')
            drained+=1
    exact(drained,drain['dequeued'],'drain observed advances')
    exact(len(rows),drained+1,'drain terminating EMPTY')
    require(observed_end<=drain_begin,'drain precedes measured event completion')
    validate_current(root,phase,workers,run_id=run_id,clock_origin=clock_origin,arena=arena,arena_address=arena_address)
    elapsed = ((observed_end if capacity_limited else min(w['last_observed_tick'] for w in workers))-phase_origin)//1000
    require(elapsed >= 0, 'negative observed elapsed')
    return PhaseValidation(pcount,accepted,full,ccount,
        selector.ObservationCounts(expected_counts[0],expected_counts[2],expected_counts[1],expected_counts[3]),
        elapsed,capacity_limited,drain_begin,prior_drain_end)


def file_text(value):
    exact(value['complete'], True, 'thread file complete')
    raw = value['raw_bytes']
    require(isinstance(raw,list) and all(type(b) is int and 0 <= b < 256 for b in raw),
            'thread raw bytes malformed')
    call(value['read'],len(raw)); call(value['end_probe'],0)
    require(value['end_probe_byte'] is None, 'unexpected EOF byte')
    text = bytes(raw).decode('ascii')
    require(text.endswith('\n') and '\0' not in text, 'truncated thread file')
    return text


def parse_stat(text):
    begin,end = text.find(' ('),text.rfind(') ')
    require(begin > 0 and end > begin, 'malformed stat comm')
    tid = int(text[:begin]); values = text[end+2:].split()
    require(tid > 0 and len(values) >= 50 and values[0] in 'RSDZTtXxKWPI', 'incomplete task stat')
    require(values[0] not in ('Z','X','x'), 'task exited')
    require(all(re.fullmatch(r'-?[0-9]+',v) for v in values[1:]), 'nonnumeric task stat')
    result = dict(task_id=tid,state=values[0],start_time_ticks=int(values[19]),
                  minor_faults=int(values[7]),major_faults=int(values[9]),last_cpu=int(values[36]))
    for k,v in result.items():
        if k != 'state': uint(v,'stat.'+k)
    return result


def parse_status(text):
    mapping = dict(Pid='task_id',Tgid='thread_group_id',voluntary_ctxt_switches='voluntary_context_switches',
                   nonvoluntary_ctxt_switches='involuntary_context_switches')
    result = {}
    for line in text.splitlines():
        require(':' in line,'malformed thread status')
        name,value = line.split(':',1)
        if name in mapping:
            target = mapping[name]
            require(target not in result and re.fullmatch(r'\s*[0-9]+\s*',value), 'duplicate/invalid thread status')
            result[target] = uint(int(value),'status.'+name)
    require(set(result) == set(mapping.values()), 'incomplete thread status')
    return result


def validate_thread(value, cpu, tid):
    exact(value['stop'],7,'thread sampled')
    first,last = (parse_stat(file_text(value[k])) for k in ('stat_before_read','stat_after_read'))
    status = parse_status(file_text(value['status_read']))
    for k,v in (('stat_before',first),('stat_after',last),('status',status)): exact(value[k],v,k+' independent parse')
    for item in (first,last,status): exact(item['task_id'],tid,'owner task ID')
    exact(first['start_time_ticks'],last['start_time_ticks'],'task identity')
    exact(first['last_cpu'],cpu,'owner CPU before'); exact(last['last_cpu'],cpu,'owner CPU after')
    words = value['affinity_mask']
    require(isinstance(words,list) and words,'missing affinity mask')
    mask = 0
    for index,word in enumerate(words): mask |= uint(word,'affinity word') << (64*index)
    call(value['affinity_call'],minimum=1)
    require(value['affinity_call']['return_value'] <= len(words)*8,'affinity bytes exceed storage')
    require(value['affinity_call']['return_value']%8==0,'affinity partial word')
    require(all(word==0 for word in words[value['affinity_call']['return_value']//8:]),'affinity bits outside returned syscall prefix')
    exact(mask,1<<cpu,'raw affinity singleton')
    exact(value['affinity_cpu_count'],1,'affinity count'); exact(value['singleton_affinity_cpu'],cpu,'affinity CPU')
    require(status['thread_group_id'] > 0,'invalid thread group')
    require(last['minor_faults'] >= first['minor_faults'] and last['major_faults'] >= first['major_faults'],
            'thread counter regression')
    return first,last,status


def owner(value, cpu):
    call(value['affinity']); call(value['current_cpu'],cpu); call(value['thread_id'],minimum=1); call(value['faults'])
    exact(value['affinity_cpu_count'],1,'owner affinity count')
    exact(value['requested_cpu_in_affinity'],True,'owner affinity membership')
    uint(value['minor_faults'],'owner minor faults'); uint(value['major_faults'],'owner major faults')
    return value['thread_id']['return_value']


def validate_mapping(value, expected, *, stack=False, cleanup=False, readonly=False):
    exact(value['requested'],expected,'mapping requested plan')
    page = expected['verified_base_page_bytes']
    call(value['base_page_bytes'],page)
    exact(value['stop'],11 if stack else 10,'mapping ready')
    exact(value['mapping']['error_number'],0,'mapping errno')
    address = uint(value['mapping']['address'],'mapping address')
    require(address > 0 and address % page == 0,'mapping alignment')
    call(value['binding']); call(value['no_huge_pages']); call(value['lock'])
    if stack:
        call(value['minimum_stack_bytes'],minimum=1)
        require(expected['bytes'] >= value['minimum_stack_bytes']['return_value'],'stack minimum')
        call(value['guard']); call(value['populate'])
        before,after = value['before_populate'],value['after_populate']
        for name in ('attribute_init','attribute_stack','attribute_guard','attribute_affinity',
                     'create','attribute_destroy'):
            exact(value['thread'][name],0,'thread '+name)
        if cleanup: exact(value['thread']['join'],0,'thread join')
        address += page
    else:
        call(value['affinity_request'])
        before,after = value['before_touch'],value['after_touch']
        exact(value['prefaulted_pages'],expected['bytes']//page,'prefault count')
        if readonly: call(value['read_only'])
    tid = owner(before,expected['owner_cpu'])
    exact(owner(after,expected['owner_cpu']),tid,'mapping owner identity')
    require(after['minor_faults']>=before['minor_faults'] and after['major_faults']>=before['major_faults'],
            'mapping preparation counter regression')
    if cleanup:
        exact(value['cleanup_attempted'],True,'mapping cleanup attempted')
        call(value['unlock']); call(value['unmap'])
    return dict(address=address,bytes=expected['bytes'],expected_node=expected['requested_node']),tid


def validate_tls(control, regions, resources, tids):
    snapshots = control['tls_snapshots']; require(len(snapshots)==6,'six TLS snapshots required')
    for index,snapshot in enumerate(snapshots):
        role = index%2 if index<4 else 2
        region = regions[(3,4,6)[role]]
        exact(snapshot['stop'],6,'TLS complete'); exact(snapshot['iteration_return'],0,'TLS iterator')
        call(snapshot['thread_before'],tids[role]); call(snapshot['thread_after'],tids[role]); call(snapshot['fs_read'])
        base,end = region['address'],region['address']+region['bytes']
        require(base <= uint(snapshot['fs_base'],'FS base') < end,'FS outside declared stack')
        modules = snapshot['modules']
        for name in ('loader_adds','loader_subs','visited_objects'):uint(snapshot[name],'TLS '+name)
        exact(snapshot['used'],len(modules),'TLS module count')
        require(len(modules)<=resources['tls_module_capacity'],'TLS capacity exceeded')
        require(len(modules)<=snapshot['visited_objects'],'TLS modules exceed visited objects')
        seen = set()
        for module in modules:
            require(set(module)=={'image_base','module_id','address','bytes'},'TLS module shape')
            require(uint(module['module_id'],'TLS module ID')>0,'zero TLS module ID')
            identity=(module['image_base'],module['module_id'])
            require(identity not in seen,'duplicate TLS module'); seen.add(identity)
            for value in module.values(): uint(value,'TLS module')
            if module['bytes']:
                require(base <= module['address'] < end and module['address']+module['bytes'] <= end,'TLS outside declared stack')
    for first,second in ((0,2),(1,3),(4,5)):
        for name in ('fs_base','loader_adds','loader_subs','visited_objects','used','modules'):
            exact(snapshots[first][name],snapshots[second][name],'persistent TLS '+name)


def validate_controls(control, final, capture, resources, monitoring, hardware_control):
    """Validate actual six control groups and 42 page-query observations."""
    g = capture.geometry; page = g.base_page_bytes
    session = control['session']; origins=session['origins']
    clock_origin = control['clock_origin']['absolute_nanoseconds']
    exact(control['clock_origin']['status'],0,'origin clock')
    exact(final['clock_origin'],control['clock_origin'],'final clock origin')
    exact(final['session'],session,'final session')
    exact(final['publication_attempted'],True,'final publication attempted')
    exact(final['publication_succeeded'],True,'final publication succeeded')
    exact(control['publication_attempted'],True,'publication callback entered')
    exact(control['publication_succeeded'],False,'publication callback not yet returned')
    exact(control['cleanup_observation_scope'],'BEFORE_PUBLICATION_RETURNS_FINAL_CLEANUP_REQUIRES_RETURNED_NATIVE_RESULT','cleanup scope')
    expected_plans = []
    cpus=(g.producer_cpu,g.producer_cpu,g.consumer_cpu)
    nodes=(g.shared_node,g.producer_node,g.consumer_node)
    for i in range(3):
        expected_plans.append(dict(bytes=resources['region_bytes'][i],verified_base_page_bytes=page,
                                   owner_cpu=cpus[i],requested_node=nodes[i]))
    require(len(control['worker_mappings'])==3 and len(final['worker_mappings'])==3,'worker mappings required')
    regions=[];mapping_tids=[];controller_tids=[];monitor_region=None
    for i,plan in enumerate(expected_plans):
        region,tid=validate_mapping(control['worker_mappings'][i],plan,readonly=i==0)
        cleaned,aftertid=validate_mapping(final['worker_mappings'][i],plan,cleanup=True,readonly=i==0)
        exact(aftertid,tid,'mapping final owner');mapping_tids.append(tid)
        exact(cleaned,region,'mapping cleanup identity'); regions.append(region)
    tids=[]
    for i,name in enumerate(('producer_stack','consumer_stack')):
        region,tid=validate_mapping(control['worker_stacks'][i],resources['workers'][name],stack=True)
        cleaned,aftertid=validate_mapping(final['worker_stacks'][i],resources['workers'][name],stack=True,cleanup=True)
        exact(cleaned,region,'stack cleanup identity'); exact(aftertid,tid,'stack owner'); regions.append(region);tids.append(tid)
    controller = resources['controller_stack']
    for name,bytes_name in (('core_mapping','core_bytes'),('monitor_mapping','monitor_bytes')):
        plan=dict(controller,bytes=resources[bytes_name])
        region,tid=validate_mapping(control[name],plan)
        cleaned,aftertid=validate_mapping(final[name],plan,cleanup=True)
        exact(aftertid,tid,'controller final mapping owner');controller_tids.append(tid)
        exact(cleaned,region,'controller mapping cleanup identity')
        memory=control['core' if name=='core_mapping' else 'monitor_arena']
        exact(memory,dict(address=region['address'],bytes=region['bytes']),'controller mapping address')
        if name=='core_mapping': regions.append(region)
        else:monitor_region=region
    region,tid=validate_mapping(control['controller_stack'],controller,stack=True)
    cleaned,aftertid=validate_mapping(final['controller_stack'],controller,stack=True,cleanup=True)
    exact(cleaned,region,'controller stack cleanup identity');exact(aftertid,tid,'controller task')
    regions.append(region);tids.append(tid)
    require(len(set(tids))==3,'owner thread identities overlap')
    exact(mapping_tids,[tids[0],tids[0],tids[1]],'actual first-touch owners')
    exact(controller_tids,[tids[2],tids[2]],'actual controller mapping owners')
    exact(control['regions'],regions,'actual seven regions')
    for i,region in enumerate([*regions,monitor_region]):
        if i<7:exact(region['bytes'],resources['region_bytes'][i],'bound region size')
        for prior in regions[:i]:
            require(region['address']+region['bytes'] <= prior['address'] or
                    prior['address']+prior['bytes'] <= region['address'],'overlapping regions')
    for name in ('core_bytes','monitor_bytes','total_mapping_bytes','region_bytes'):
        exact(control['layout'][name],resources[name],'bound layout.'+name)
    exact(control['worker_preparation'],[7,7],'owner preparation')
    validate_tls(control,regions,resources,tids)
    prestate={v['cpu']:int(v['complete_value_hex'],16) for v in hardware_control['prestate']}
    require(len(prestate)==len(hardware_control['prestate']) and prestate,'duplicate/absent prestate')
    prep=control['hardware_preparation']
    exact(prep['attempted'],True,'hardware preparation');exact(prep['released'],True,'hardware release')
    exact(prep['stop'],6,'hardware prepared');exact(prep['resolver_errors'],[],'hardware resolver')
    exact(prep['requested_identity'],monitoring['hardware_identity'],'hardware identity')
    exact(prep['observed_identity'],dict(value=monitoring['hardware_identity'],errors=[]),'hardware CPUID')
    exact(prep['mapping_id'],hardware_control['mapping_id'],'hardware mapping')
    exact(prep['cpu_count'],len(prestate),'hardware CPU count')
    exact([v['cpu'] for v in prep['cpus']],list(prestate),'hardware CPU set')
    for item in prep['cpus']:
        value=prestate[item['cpu']]
        exact(item['expected_h0'],value,'H0 prestate');exact(item['expected_h1'],value|15,'H1 masked value')
        require(value & 15 == 0,'unsupported H0 disable bits')
        call(item['open'],minimum=0);call(item['close'])
    def scratch(value):
        exact(len(value['affinity_mask']),resources['thread_affinity_words'],'frozen affinity scratch')
        for name in ('stat_before_read','stat_after_read','status_read'):
            require(len(value[name]['raw_bytes'])<=resources['thread_status_bytes' if name=='status_read' else 'thread_stat_bytes'],
                    'thread file exceeds frozen scratch')
    preparations=control['thread_preparations'];require(len(preparations)==2,'two thread preparations')
    initial_identities={}
    for i,p in enumerate(preparations):
        exact(p['requested_task_id'],tids[i],'prepared TID');exact(p['attempted'],True,'thread prepare')
        # PreparedThreadMonitor::release clears ready before publication. The
        # retained initial sample and all three successful closes prove the
        # completed lifecycle; requiring ready here rejects real successful runs.
        exact(p['ready'],False,'thread monitor released')
        for name in ('directory_open','stat_open','status_open'):call(p[name],minimum=0)
        require(len(p['closes'])==3,'thread close evidence')
        for closed in p['closes']:call(closed)
        scratch(p['initial'])
        first,last,status=validate_thread(p['initial'],(g.producer_cpu,g.consumer_cpu)[i],tids[i])
        initial_identities[i]=(first['task_id'],first['start_time_ticks'],status['thread_group_id'])
    controls=control['controls'];require(len(controls)==6,'six control groups')
    baselines={};previous={}
    for group,item in enumerate(controls):
        phase,moment=divmod(group,3)
        request=dict(phase=phase,moment=moment,region_index=monitoring['control_region_index'],
                     offset_ticks=monitoring['during_offset_ticks'][phase] if moment==1 else 0)
        exact(item['request'],request,'control request');exact(item['attempted'],True,'control attempted');exact(item['stop'],6,'control sampled')
        require(len(item['workers'])==2,'two observed workers')
        for role,value in enumerate(item['workers']):
            scratch(value)
            first,last,status=validate_thread(value,(g.producer_cpu,g.consumer_cpu)[role],tids[role])
            identity=(first['task_id'],first['start_time_ticks'],status['thread_group_id'])
            exact(identity,initial_identities[role],'prepared task identity')
            counters=(last['minor_faults'],last['major_faults'],status['voluntary_context_switches'],status['involuntary_context_switches'])
            if role in previous:
                old_identity,old=previous[role]
                exact(identity,old_identity,'persistent owner identity')
                require(all(v>=b for v,b in zip((first['minor_faults'],first['major_faults'],*counters[2:]),old)), 'cross-snapshot counter regression')
            previous[role]=(identity,counters)
            if moment==0:baselines[role]=(first['minor_faults'],first['major_faults'],*counters[2:])
            limits=monitoring['counter_limits'][phase][role]
            for n,current,baseline in zip(('minor_faults','major_faults','voluntary_switches','involuntary_switches'),counters,baselines[role]):
                require(current>=baseline,'counter regression')
                if limits[n] is not None:require(current-baseline<=limits[n],'frozen disturbance limit: '+n)
        hw=item['hardware'];exact(hw['attempted'],True,'hardware sampled');exact(hw['stop'],4,'hardware sampled status')
        exact(hw['mapping_id'],hardware_control['mapping_id'],'hardware sample mapping')
        exact(hw['prepared_controller_identity'],monitoring['hardware_identity'],'sample CPU identity')
        exact(hw['requested_state'],0 if capture.hardware_state=='H0' else 1,'sample state')
        exact(hw['cpu_count'],len(prestate),'sample CPU count');exact([v['cpu'] for v in hw['cpus']],list(prestate),'sample CPU set')
        for cpu in hw['cpus']:
            expected=prestate[cpu['cpu']] | (15 if capture.hardware_state=='H1' else 0)
            call(cpu['read'],8);raw=cpu['raw_bytes']
            require(isinstance(raw,list) and len(raw)==8 and all(type(v)is int and 0<=v<256 for v in raw),'MSR raw bytes')
            observed=int.from_bytes(bytes(raw),'little')
            exact(observed,expected,'raw MSR readback');exact(cpu['observed_value'],observed,'parsed MSR');exact(cpu['expected_value'],expected,'expected MSR');exact(cpu['matches'],True,'MSR match flag')
    residency=control['residency'];require(len(residency)==42,'42 residency observations required')
    prior_tick=0
    for ordinal,row in enumerate(residency):
        phase,rest=divmod(ordinal,21);moment,region_index=divmod(rest,7)
        expected=dict(phase=phase,moment=moment,region_index=region_index,
                      offset_ticks=monitoring['during_offset_ticks'][phase] if moment==1 else 0)
        exact(row['request'],expected,'residency request');exact(row['stop'],8,'residency sampled')
        exact(row['controls'],2 if region_index==monitoring['control_region_index'] else 1,'control attachment')
        exact(row['query'],dict(syscall_return=0,error_number=0),'move_pages syscall')
        region=regions[region_index]
        first=monitoring['during_first_page'][region_index] if moment==1 else 0
        count=monitoring['during_page_count'][region_index] if moment==1 else region['bytes']//page
        addresses=row['page_addresses'];statuses=row['page_status']
        require(len(addresses)==len(statuses)==count,'residency page count')
        for i,(address,node) in enumerate(zip(addresses,statuses,strict=True)):
            exact(address,region['address']+(first+i)*page,'residency actual page')
            exact(node,region['expected_node'],'residency actual node')
        begin=clock(row['begin'],clock_origin,'residency begin');end=clock(row['end'],clock_origin,'residency end')
        require(prior_tick<=begin<=end,'observer clock order');prior_tick=end
        if moment==0:require(end<=origins[phase],'before observation after phase origin')
        if moment==2:
            phase_workers=session['warmup' if phase==0 else 'measurement']
            require(begin>=max(w['last_observed_tick'] for w in phase_workers if w['last_observed_tick'] is not None),
                    'after observation before workers stopped')
        if moment==1:
            limit=origins[phase]+(contract.WARMUP_NS if phase==0 else capture.measurement_ns)*1000
            require(origins[phase]+expected['offset_ticks']<=begin<=end<limit,'during observation outside horizon')
            first_tick=clock(row['wait_first'],clock_origin,'wait first');last_tick=clock(row['wait_last'],clock_origin,'wait last')
            require(origins[phase]<=first_tick<=last_tick==begin,'during wait clock')
            require(1<=uint(row['wait_polls'],'wait polls')<=monitoring['observer_wait_poll_limit'],'wait poll bound')
            exact(row['finished_before'],0,'workers alive before');exact(row['finished_after'],0,'workers alive after')
    environment.validate_environment(control,monitoring['environment_sources'],regions,base_page_bytes=page)
    return regions


def validate_capture(root, control, final, capture, resources, monitoring, hardware_control):
    exact(control['schema_version'],'cpu-prefetch-stage17-discovery-control/1','control schema')
    exact(control['capture_ordinal'],capture.ordinal,'capture ordinal')
    exact(control['diagnostic_only'],True,'diagnostic only')
    exact(control['execution_authority'],False,'no execution authority')
    exact(control['phase18_authority'],False,'no phase18 authority')
    require(not control.get('synthetic',False),'synthetic evidence cannot select production duration')
    session=control['session']
    require(session['stop'] in (8,9),'mandatory session stop')
    expected_stop=15 if session['stop']==8 else 13
    exact(control['capture_stop_before_publication'],expected_stop,'native stop before publication')
    exact(final['stop'],expected_stop,'native stop after cleanup')
    for flag in ('warmup_verified','measurement_verified'):exact(session[flag],True,flag)
    exact(session['preparation'],[1,1],'session preparation')
    exact(session['worker_exception'],[False,False],'worker exceptions')
    exact(session['private_reset_verified'],[True,True],'private reset')
    exact(session['origin_status'],[0,0],'origin status')
    exact(session['observed_origins'],session['origins'],'observed phase origins')
    require(len(session['origins'])==2,'two origins required')
    for origin in session['origins']:uint(origin,'phase origin')
    require(session['origins'][1]>=session['origins'][0]+contract.WARMUP_NS*1000,
            'measurement precedes warmup horizon')
    exact(session['observations'],[dict(before=2,during=2,after=2)]*2,'mandatory observations')
    regions=validate_controls(control,final,capture,resources,monitoring,hardware_control)
    arena=Arena(capture);observed=control['arena'];g=capture.geometry
    for name,expected in dict(capacity=g.capacity,cache_line_bytes=g.cache_line_bytes,
                              base_page_bytes=g.base_page_bytes,allocated_bytes=g.capacity*g.cache_line_bytes,
                              distinct_cache_lines=g.capacity,distinct_pages=(g.capacity*g.cache_line_bytes+g.base_page_bytes-1)//g.base_page_bytes,
                              base_page_aligned=True,every_record_line_aligned=True,padding_initialized=True,
                              storage_address=regions[0]['address'],content_unchanged=True,
                              prepared_content_sha256=arena.hashes[0],publication_content_sha256=arena.hashes[0],
                              ordered_index_sha256=arena.hashes[1],address_delta_sha256=arena.hashes[2],
                              ordered_index_error=None,address_delta_error=None).items():
        exact(observed[name],expected,'arena.'+name)
    require(len(control['phases'])==2,'two raw phases required')
    phases=[]
    for index,name in enumerate(('warmup','measurement')):
        identity=capture.warmup if index==0 else capture.measurement
        result=validate_phase(root,control['phases'][index],session[name],session[name+'_drain'],
            run_id=identity.run_id,phase_origin=session['origins'][index],
            clock_origin=control['clock_origin']['absolute_nanoseconds'],
            duration_ns=contract.WARMUP_NS if index==0 else capture.measurement_ns,
            attempt_capacity=capture.budget.warmup_attempt_capacity if index==0 else capture.budget.measurement_attempt_capacity,
            drain_capacity=capture.budget.drain_attempt_capacity,initial_checksum=resources['initial_consumer_state'],
            arena=arena,reset_required=index==0,arena_address=regions[0]['address'])
        phases.append(result)
        after_end=max(clock(row['end'],control['clock_origin']['absolute_nanoseconds'],'after observation')
            for row in control['residency'] if row['request']['phase']==index and row['request']['moment']==2)
        require(result.drain_begin_tick>=after_end,'drain began before AFTER observations completed')
    measurement_before=min(clock(row['begin'],control['clock_origin']['absolute_nanoseconds'],'measurement before')
        for row in control['residency'] if row['request']['phase']==1 and row['request']['moment']==0)
    require(phases[0].drain_end_tick<=measurement_before,'measurement preparation before warmup drain completed')
    require(not phases[0].capacity_limited,'warmup capacity is mandatory failure')
    exact(phases[1].capacity_limited,session['stop']==8,'measurement capacity classification')
    measured=phases[1]
    return selector.DiagnosticCapture(selector.CaptureKey(capture.context_ordinal,capture.measurement_ns),
        measured.elapsed_ns,measured.counts,
        selector.StopReason.trace_capacity if measured.capacity_limited else selector.StopReason.fixed_deadline),tuple(phases)


@dataclass(frozen=True)
class ValidatedStudy:
    plan_sha256: str
    retained_manifest_sha256: str
    captures: tuple[selector.DiagnosticCapture,...]
    phase_counts: tuple[tuple[PhaseValidation,...],...]
    selection: selector.DurationSelection
    execution_authority: bool = False
    formal_runs_contributed: int = 0
    diagnostic_only: bool = True


def validate_retained_study(*, action_inputs, retention_report, retention_binding, output_root):
    """Call after custody admission. Revalidates bound bytes, no signature authority.

    All eleven original bound documents are mandatory. The caller supplies the
    retention binding from the admitted worker result, not a newly rehashed file.
    Missing/unsupported evidence raises ValidationError; no partial selection.
    """
    try:
        return _validate_study(action_inputs,retention_report,retention_binding,pathlib.Path(output_root))
    except ValidationError:
        raise
    except (KeyError,TypeError,ValueError,OverflowError,UnicodeError,OSError,codec.DecodeError) as error:
        raise ValidationError('missing, malformed or unsupported evidence: '+str(error)) from error


def _validate_study(inputs,report,report_binding,root):
    import io
    from jsonschema import Draft202012Validator
    import stage17_phase_controller_v24 as controller
    plan=contract.validate_plan(inputs['plan'])
    exact(report_binding['file_name'],registry.REPORT_NAME,'retention filename')
    with document(root,report_binding) as actual:exact(actual,report,'admitted retention bytes')
    # The separately hash-bound analysis successor may live outside the
    # qualified root. Schema custody stays with its pinned registry dependency.
    schema=json.loads((pathlib.Path(registry.__file__).resolve().parents[1]/registry.REPORT_SCHEMA).read_text())
    require(not list(Draft202012Validator(schema).iter_errors(report)),'retention report schema')
    exact(report['plan_sha256'],plan.sha256,'retention plan binding')
    exact(report['hardware_state']['file_name'],'studyhardware.json','hardware filename')
    require(report_binding['size_bytes']+report['hardware_state']['size_bytes']<=plan.budget.metadata_output_bytes,
            'study metadata bound')
    bindings=[plan.stand,plan.qualification,plan.resource_plan,plan.monitoring_plan,plan.namespace_registry]
    bindings.extend(dep.resolution for dep in plan.dependencies)
    bound={}
    require(len(inputs['bound_documents'])==len(bindings),'incomplete bound inputs')
    for item in inputs['bound_documents']:
        require(item['artifact_id'] not in bound,'duplicate bound input')
        binding=next((b for b in bindings if b.artifact_id==item['artifact_id']),None)
        require(binding is not None,'unbound input')
        raw=item['utf8_bytes'].encode('utf-8')
        exact(len(raw),binding.size_bytes,'bound input size')
        exact(hashlib.sha256(raw).hexdigest(),binding.sha256,'bound input original SHA256')
        with contextlib.ExitStack() as stack:parsed=JsonReader(io.StringIO(item['utf8_bytes']),stack).document()
        exact(registry.canonical(parsed),registry.canonical(item['document']),'bound parsed document')
        bound[item['artifact_id']]=parsed
    resources=bound[plan.resource_plan.artifact_id];monitoring=bound[plan.monitoring_plan.artifact_id]
    try:
        controller._native_inputs(plan,resources,monitoring,inputs['native_captures'])
    except controller.ControllerError as error:
        raise ValidationError('bound native inputs: '+str(error)) from error
    all_bindings=[report_binding,report['hardware_state']]
    captures=[];phase_counts=[]
    with document(root,report['hardware_state']) as hardware:
        exact(hardware['schema_version'],'cpu-prefetch-stage17-discovery-hardware/1','hardware schema')
        exact(hardware['plan_sha256'],plan.sha256,'hardware plan binding')
        exact(hardware['mapping_id'],inputs['hardware_control']['mapping_id'],'study hardware mapping')
        exact(hardware['restoration_verified'],True,'study restoration')
        exact(hardware['mandatory_failure'],False,'study mandatory failure')
        exact(hardware['phase18_authority'],False,'no phase18 authority')
        require(len(hardware['native_results_after_cleanup'])==36,'36 final cleanup results required')
        prestate=inputs['hardware_control']['prestate']
        require(len(hardware['whole_plots'])==2,'exact two hardware whole plots')
        for state,plot in zip(('H0','H1'),hardware['whole_plots'],strict=True):
            exact(plot['state'],state,'whole plot state');exact(plot['restoration_verified'],True,'whole plot restoration')
            # D213: these are write-action readbacks, not the independent
            # per-capture observations. H0 verifies but never writes; H1
            # applies in prestate order and restores in reverse write order.
            expected_restore=list(reversed(prestate)) if state=='H1' else []
            expected_apply=[dict(cpu=v['cpu'],complete_value_hex=f"{int(v['complete_value_hex'],16)|15:016x}") for v in prestate] if state=='H1' else []
            exact(plot['restore_readback'],expected_restore,'whole plot restore prestate')
            exact(plot['apply_readback'],expected_apply,'whole plot applied state')
        for cap,retained,final,r,m in zip(plan.captures,report['captures'],hardware['native_results_after_cleanup'],
                                         resources['captures'],monitoring['captures'],strict=True):
            exact(retained['ordinal'],cap.ordinal,'retained ordinal')
            exact(retained['warmup_run_id'],cap.warmup.run_id,'retained warmup identity')
            exact(retained['measurement_run_id'],cap.measurement.run_id,'retained measurement identity')
            files=retained['artifacts'];exact([b['file_name'] for b in files],list(registry.capture_names(cap.ordinal)),'retained seven artifacts')
            require(sum(uint(b['size_bytes'],'artifact size') for b in files)<=cap.budget.max_output_bytes,'capture output bound')
            require(sum(b['size_bytes'] for b in files[:6])<=cap.budget.retained_output_bytes,'capture retained raw bound')
            require(files[-1]['size_bytes']<=cap.budget.metadata_output_bytes,'capture metadata bound')
            all_bindings.extend(files)
            with document(root,files[-1]) as control:
                for i,phase in enumerate(control['phases']):
                    for j,name in enumerate(('producer','consumer','demand')):
                        short={key:phase[name][key] for key in ('file_name','size_bytes','sha256')}
                        exact(short,files[i*3+j],'raw control custody binding')
                result,phases=validate_capture(root,control,final,cap,r,m,inputs['hardware_control'])
            exact(retained['native_stop'],'trace_capacity' if phases[1].capacity_limited else 'complete','retention stop')
            sufficient=not phases[1].capacity_limited and all(c>=100000 for c in result.counts.values())
            exact(retained['native_validity'],'VALID' if sufficient else 'INSUFFICIENT','retention count claim')
            captures.append(result);phase_counts.append(phases)
    require(sum(b['size_bytes'] for b in all_bindings)<=plan.maximum_output_bytes,'study output bound')
    return ValidatedStudy(plan.sha256,hashlib.sha256(registry.canonical(all_bindings)).hexdigest(),
        tuple(captures),tuple(phase_counts),selector.select_duration(captures))
