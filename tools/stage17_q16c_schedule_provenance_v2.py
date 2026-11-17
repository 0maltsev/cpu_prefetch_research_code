"""D270 provenance for sealed original schedules and exact D269 descriptive rates.

No legacy VALIDATED record is manufactured. Accepted D029 generation and every
binary/envelope/derivation hash and identity check remain byte-for-byte the same.
Caller separately authenticates the basis handoff and prospective namespaces.
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
import stage17_q16c_schedule_provenance_v1 as old

ROOT, U64, MAX_METADATA_BYTES = old.ROOT, old.U64, old.MAX_METADATA_BYTES
SCHEMA_ID = 'cpu-prefetch-stage17-q16c-schedule-provenance/2'
BASIS_BYTES = 631
BASIS_SHA256 = '05833b52e286aea283906013ad4b10d943093aaff9397632f4c05f8e62549e79'
SCALES, LOADS = old.SCALES, old.LOADS
ScheduleProvenanceError = old.ScheduleProvenanceError
require, uint, binding = old.require, old.uint, old.binding
_unique, _noninteger, _metadata = old._unique, old._noninteger, old._metadata
_self_hash, _append, _identity = old._self_hash, old._append, old._identity


def verify_schedule_source(*, schedule, phase, duration_ns, scale_ordinal, load_level,
                           load_basis_utf8_bytes, artifact_path, artifact_binding,
                           envelope_utf8_bytes, envelope_binding,
                           derivation_utf8_bytes, derivation_binding,
                           expected_parent_namespace_id):
    try:
        return _verify(**locals())
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
    raw_basis = args['load_basis_utf8_bytes']
    require(type(raw_basis) is bytes and len(raw_basis) == BASIS_BYTES
            and hashlib.sha256(raw_basis).hexdigest() == BASIS_SHA256,
            'exact completed D269 descriptive load basis required')
    basis = json.loads(raw_basis, object_pairs_hook=_unique, parse_float=_noninteger,
                       parse_constant=_noninteger)
    require(scale == 0 and args['duration_ns'] == (5_000_000_000 if phase == 'warmup' else 1_000_000_000),
            'D270 only initial scale, five-second warmup and one-second measurement')
    mu = basis['base_rates'][args['load_level']]
    rate = Fraction(mu['numerator'], mu['denominator']) / 10**12
    uint(rate.numerator, True)
    uint(rate.denominator, True)

    schema = json.loads((ROOT / 'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json').read_text())
    Draft202012Validator({'$ref': '#/$defs/schedule', '$defs': schema['$defs']}).validate(source)
    for field in ('schedule_id', 'namespace_id', 'seed_id'):
        require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}', source[field]) is not None,
                'noncanonical native source identity')
    require(re.fullmatch('[0-9a-f]{64}', source['seed_hex']) is not None, 'noncanonical master seed')
    origin, end, count = (uint(source[key]) for key in ('source_origin_ticks', 'source_horizon_ticks', 'offered_count'))
    require(end == uint(origin + duration),
            'native duration/count differs')
    require(phase == 'warmup' or count > 0, 'measurement needs at least one offered event')
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
                require(previous <= actual < end and actual == deadline,
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
        descriptive_load_basis_sha256=BASIS_SHA256,
        family_method_id='MATRIX-FULL-DESCRIPTIVE-SCREEN-v1', confidence_claim=None,
        accepted_generation_verified=True, execution_authority=False, phase18_authority=False)
