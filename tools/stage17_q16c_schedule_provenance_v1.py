"""D232 cold provenance checks for accepted D029/D036 Q16c schedules.

Caller authenticates D230 and the prospective namespace registry, supplying
its explicit parent namespace. Hashes alone do not authenticate their author.
Binary validation/regeneration is streaming, using the unchanged accepted
generator primitives, not a new RNG or exponential transform. Native vectors
are compared in place; request-vector limits and authority remain external.
"""
from __future__ import annotations

import decimal
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
from fractions import Fraction

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

import generate_schedule as generator
import stage17_formal_calibration_v1 as calibration

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = 'cpu-prefetch-stage17-q16c-schedule-provenance/1'
MAX_METADATA_BYTES = 1024 * 1024
U64 = (1 << 64) - 1
SCALES = (Fraction(1), Fraction(9, 10), Fraction(4, 5), Fraction(7, 10), Fraction(3, 5))
LOADS = dict(L025=Fraction(1, 4), L050=Fraction(1, 2), L075=Fraction(3, 4))


class ScheduleProvenanceError(ValueError):
    """Bound source, accepted generation, or prospective coordinates differ."""


def require(condition, message):
    if not condition:
        raise ScheduleProvenanceError(message)


def uint(value, positive=False):
    require(type(value) is int and (1 if positive else 0) <= value <= U64,
            'expected exact unsigned-64 integer')
    return value


def binding(value):
    require(isinstance(value, dict) and set(value) == {'artifact_id', 'size_bytes', 'sha256'},
            'binding needs artifact_id/size_bytes/sha256')
    require(isinstance(value['artifact_id'], str) and bool(value['artifact_id']), 'empty artifact identity')
    uint(value['size_bytes'])
    require(isinstance(value['sha256'], str) and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None,
            'noncanonical artifact SHA256')
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _noninteger(_value):
    raise ScheduleProvenanceError('noninteger JSON number')


def _metadata(raw, source, schema):
    binding(source)
    require(type(raw) is bytes and len(raw) <= MAX_METADATA_BYTES, 'metadata must be bounded original UTF-8 bytes')
    require(len(raw) == source['size_bytes'] and hashlib.sha256(raw).hexdigest() == source['sha256'],
            'original metadata byte binding differs')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
                       parse_float=_noninteger, parse_constant=_noninteger)
    Draft202012Validator(json.loads((ROOT / schema).read_text())).validate(value)
    return value


def _self_hash(value, field):
    zeroed = dict(value)
    zeroed[field] = '0' * 64
    require(value[field] == hashlib.sha256(generator.canonicalize(zeroed).encode()).hexdigest(),
            field + ' self hash differs')


def _append(digest, value):
    digest.update(struct.pack('>Q', len(value)))
    digest.update(value)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def verify_schedule_source(*, schedule, phase, duration_ns, scale_ordinal, load_level,
                           calibration_record, artifact_path, artifact_binding,
                           envelope_utf8_bytes, envelope_binding,
                           derivation_utf8_bytes, derivation_binding,
                           expected_parent_namespace_id):
    """Verify one warmup/measurement source; return bounded factual provenance.

All three bindings have exactly artifact_id,size_bytes,sha256. artifact_path is
the caller-resolved local binary path; artifact_uri is retained, never opened.
The explicit expected parent comes from the authenticated prospective schedule
namespace registry, never an arena namespace. D230 provenance/stand/revision
and complete-family schedule sharing/isolation are the caller's gates.
"""
    try:
        return _verify(schedule=schedule, phase=phase, duration_ns=duration_ns,
                       scale_ordinal=scale_ordinal, load_level=load_level,
                       calibration_record=calibration_record, artifact_path=artifact_path,
                       artifact_binding=artifact_binding, envelope_utf8_bytes=envelope_utf8_bytes,
                       envelope_binding=envelope_binding, derivation_utf8_bytes=derivation_utf8_bytes,
                       derivation_binding=derivation_binding,
                       expected_parent_namespace_id=expected_parent_namespace_id)
    except ScheduleProvenanceError:
        raise
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError, ValidationError) as error:
        raise ScheduleProvenanceError(str(error)) from error


def _verify(**args):
    source, phase = args['schedule'], args['phase']
    require(phase in ('warmup', 'measurement'), 'unsupported phase')
    duration = uint(args['duration_ns'], True) * 1000
    uint(duration, True)
    if phase == 'warmup':
        require(duration == 5_000_000_000_000, 'formal bootstrap warmup must be five seconds')
    scale = uint(args['scale_ordinal'])
    require(scale < len(SCALES) and args['load_level'] in LOADS, 'unknown D036 scale/load')
    parent = args['expected_parent_namespace_id']
    require(isinstance(parent, str) and bool(parent), 'explicit registry parent required')
    record = calibration.validate_calibration_record(args['calibration_record'])
    require(record['action_id'] == 'Q16b' and record['status'] == 'VALIDATED', 'complete validated Q16b required')
    mu = record['derived_result']['mu_ref']
    rate = Fraction(mu['numerator'], mu['denominator']) * SCALES[scale] * LOADS[args['load_level']] / 10**12
    uint(rate.numerator, True)
    uint(rate.denominator, True)

    schema = json.loads((ROOT / 'config/schemas/stage17-formal-scheduled-native-input-v1.schema.json').read_text())
    Draft202012Validator({'$ref': '#/$defs/schedule', '$defs': schema['$defs']}).validate(source)
    for field in ('schedule_id', 'namespace_id', 'seed_id'):
        require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}', source[field]) is not None,
                'noncanonical native source identity')
    require(re.fullmatch('[0-9a-f]{64}', source['seed_hex']) is not None, 'noncanonical master seed')
    origin, end, count = (uint(source[key]) for key in ('source_origin_ticks', 'source_horizon_ticks', 'offered_count'))
    require(end == uint(origin + duration) and len(source['deadline_ticks']) == count,
            'native duration/count differs')
    require(phase == 'warmup' or count > 0, 'measurement needs at least one offered event')
    for value in source['deadline_ticks']:
        uint(value)
    binary = binding(args['artifact_binding'])
    require(source['source_artifact'] == {key: binary[key] for key in ('artifact_id', 'sha256')},
            'native source_artifact must bind original binary')
    require(binary['size_bytes'] == uint(count * 8), 'binary size differs from row count')
    envelope = _metadata(args['envelope_utf8_bytes'], args['envelope_binding'],
                         'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json')
    derivation = _metadata(args['derivation_utf8_bytes'], args['derivation_binding'],
                           'config/schemas/schedule-derivation-v2.schema.json')
    require(len({binary['artifact_id'], args['envelope_binding']['artifact_id'],
                 args['derivation_binding']['artifact_id']}) == 3, 'three distinct source artifacts required')
    _self_hash(envelope, 'schedule_sha256')
    _self_hash(derivation, 'record_sha256')
    expected = dict(schedule_id=source['schedule_id'], schedule_kind='WARMUP' if phase == 'warmup' else 'CALIBRATION',
                    arrival_family='POISSON_EXPONENTIAL', namespace_id=source['namespace_id'],
                    time_unit='ps', deadline_encoding='ABSOLUTE_INTEGER_TICKS', origin_ticks=origin,
                    horizon_ticks=duration, offered_count=count, overflow_rule_record_id=generator.OVERFLOW_RULE,
                    nominal_offered_rate=dict(numerator_events=rate.numerator, denominator_ticks=rate.denominator))
    require(all(envelope[key] == value for key, value in expected.items()), 'envelope phase/coordinates/rate differs')
    # Schema integer accepts integral floats; strict parsing above and these
    # exact type checks also prevent bool==0/1 aliases in cross-field checks.
    for key in ('origin_ticks', 'horizon_ticks', 'offered_count'):
        uint(envelope[key])
    require(all(envelope['inclusion_boundary'][key] is True for key in ('start_inclusive', 'end_exclusive'))
            and envelope['immutable_ordering'] is True, 'accepted half-open immutable order required')
    require(envelope['rng'] == dict(algorithm=generator.SCHEDULE_ALGORITHM, version=generator.SCHEDULE_VERSION,
            seed_id=source['seed_id'], derivation_record_id=derivation['record_id'], parent_namespace_id=parent),
            'envelope RNG identity differs')
    require(all(derivation[key] == value for key, value in dict(seed_id=source['seed_id'],
            namespace_id=source['namespace_id'], parent_namespace_id=parent).items()), 'derivation namespace/seed differs')
    storage = envelope['deadline_storage']
    require(storage['mode'] == 'EXTERNAL_IMMUTABLE_ARTIFACT', 'original external binary required')
    require(all(storage[key] == value for key, value in dict(artifact_id=binary['artifact_id'],
            artifact_sha256=binary['sha256'], byte_count=binary['size_bytes'], row_count=count).items()),
            'envelope binary binding differs')
    uint(storage['byte_count']); uint(storage['row_count'])
    spec = generator.ScheduleSpec(source['schedule_id'], expected['schedule_kind'], source['namespace_id'], parent,
        source['seed_id'], derivation['record_id'], bytes.fromhex(source['seed_hex']), origin, duration,
        rate.numerator, rate.denominator, binary['artifact_id'], storage['artifact_uri'])
    generator._require_python_runtime()
    generator.validate_spec(spec)
    key = generator._derive_key(spec.master_seed, spec.namespace_id)
    require(derivation['derived_key_u32be_hex'] == f'{key[0]:08x}{key[1]:08x}', 'derived key differs from master seed')

    decoded = hashlib.sha256()
    for value in (b'cpu-prefetch/decoded-deadlines-sha256/v1', generator.DERIVATION_DOMAIN_PROTOCOL_VERSION.encode(),
                  generator.SCHEDULE_SUITE.encode(), b'ps', *(struct.pack('>Q', n)
                  for n in (origin, duration, rate.numerator, rate.denominator, count))):
        _append(decoded, value)
    digest = hashlib.sha256()
    path = Path(args['artifact_path'])
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == binary['size_bytes'], 'binary not expected regular file')
        previous = origin
        total = decimal.Decimal(0)
        with decimal.localcontext(generator._decimal_context(decimal)) as active:
            # Exactly count+1 candidates: a forged truncated stream cannot
            # hide additional generated in-horizon arrivals or induce an
            # unbounded regeneration loop.
            for ordinal in range(count + 1):
                next_total = generator._advance_cumulative(active, decimal, total,
                    generator._philox_draw(key, ordinal), rate.numerator, rate.denominator)
                require(next_total.is_finite() and next_total > total, 'accepted Decimal generator made no progress')
                total = next_total
                offset = int(total.to_integral_value(rounding=decimal.ROUND_FLOOR, context=active))
                deadline = uint(origin + offset)
                if ordinal == count:
                    require(deadline >= end, 'binary omits generated in-horizon arrivals')
                    break
                raw = stream.read(8)
                require(len(raw) == 8, 'truncated binary deadline')
                actual = struct.unpack('>Q', raw)[0]
                require(previous <= actual < end and actual == source['deadline_ticks'][ordinal] == deadline,
                        'binary/native/accepted-generated deadline differs')
                previous = actual
                digest.update(raw); _append(decoded, raw)
        require(stream.read(1) == b'', 'binary has trailing bytes')
        require(_identity(before) == _identity(os.fstat(stream.fileno())) == _identity(path.lstat()),
                'binary identity changed during validation')
    require(digest.hexdigest() == binary['sha256'], 'original binary SHA256 differs')
    require(decoded.hexdigest() == envelope['decoded_deadlines_sha256'], 'decoded deadline hash differs')
    return dict(schema_version=SCHEMA_ID, phase=phase, schedule_id=source['schedule_id'],
        namespace_id=source['namespace_id'], parent_namespace_id=parent, seed_id=source['seed_id'],
        artifact_binding=dict(binary), envelope_binding=dict(args['envelope_binding']),
        derivation_binding=dict(args['derivation_binding']), schedule_sha256=envelope['schedule_sha256'],
        derivation_record_sha256=derivation['record_sha256'], decoded_deadlines_sha256=decoded.hexdigest(),
        artifact_uri=storage['artifact_uri'], source_origin_ticks=origin, source_horizon_ticks=end,
        duration_ticks=duration, offered_count=count, scale_ordinal=scale, load_level=args['load_level'],
        nominal_offered_rate=expected['nominal_offered_rate'],
        calibration_record_sha256=hashlib.sha256(calibration.canonical(record)).hexdigest(),
        accepted_generation_verified=True, execution_authority=False, phase18_authority=False)
