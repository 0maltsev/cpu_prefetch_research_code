"""D271 original-source Q16c raw reconciliation; legacy scientific rules unchanged.

Read actual retained little-endian schedule publication, independently reconstruct
its original accepted-generator big-endian SHA256 and pin compact decoded values.
Those actual values feed the unchanged per-arrival/independent-owner validator.
No inline placeholders, generated replacements, event filtering or inference.
"""
from __future__ import annotations
import array
import copy
import hashlib
import os
import struct
import sys
import types
from contextlib import ExitStack
import stage17_formal_service_capture_validation_v1 as old
import stage17_formal_scheduled_descriptive_v1 as descriptive
import stage17_archive_metadata_fast_v1 as metadata

ValidationError = old.ValidationError
require, exact, uint = old.require, old.exact, old.uint
common, raw, codec, d210 = old.common, old.raw, old.codec, old.d210
PHASES, CONTROL_IDS = old.PHASES, old.CONTROL_IDS
SCHEMA_ID = 'cpu-prefetch-stage17-formal-scheduled-source-capture-validation/2'
SOURCE_VERSIONS = {**old.SOURCE_VERSIONS,
    'input_contract': 'stage17_formal_scheduled_descriptive_v1',
    'original_source_decoder': 'stage17_formal_scheduled_capture_validation_v2'}
plans = types.SimpleNamespace(**{**vars(old.plans),
    'NATIVE_SCHEMA': {**old.plans.NATIVE_SCHEMA, 'Q16c': descriptive.NATIVE_SCHEMA},
    '_schedules': descriptive._schedules})
_input = metadata._clone(old._input, {**old._input.__globals__, 'plans': plans})
_session, _node_order = old._session, old._node_order
_schedule_mapping, _schedule, _join_phase = old._schedule_mapping, old._schedule, old._join_phase


def _checked_original_values(root, control, capture):
    owned = copy.deepcopy(capture)
    total = 0
    for i, source in enumerate(owned['schedules']):
        count = source['offered_count']; total += count * 8
        require(total <= capture['budget']['memory_bytes'], 'decoded source arrays exceed native source ceiling')
        row = control['schedules'][i]
        binding = old._binding(row['stream'], 'Q16C_PREPARED_SCHEDULE', 'SCHEDULE-DEADLINES-U64LE-v1', count, 8)
        values = array.array('Q'); digest = hashlib.sha256()
        require(values.itemsize == 8, 'unsupported native packed uint64 width')
        with ExitStack() as stack:
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC); stack.callback(os.close, fd)
            stream = old._open(stack, fd, binding, set(), [])
            remaining = count * 8
            while remaining:
                block = codec._read_exact(stream, min(65536, remaining), 'published original schedule')
                little = array.array('Q'); little.frombytes(block)
                if sys.byteorder != 'little': little.byteswap()
                values.extend(little)
                big = array.array('Q', little)
                if sys.byteorder == 'little': big.byteswap()
                digest.update(big.tobytes()); remaining -= len(block)
            stream.finish()
        require(digest.hexdigest() == source['source_artifact']['sha256'],
                'retained schedule differs from the signed original big-endian artifact')
        previous = source['source_origin_ticks']
        for value in values:
            require(previous <= value < source['source_horizon_ticks'], 'original schedule window/order differs')
            previous = value
        source['deadline_ticks'] = values
    return owned


def validate_capture(root,control,final,capture,resources,monitoring,hardware_control):
    """Validate one capture after caller authentication; invalid evidence raises.

    FULL and genuine zero service completions are retained, never retried. No
    schedule generation/source admission, family inference or release seal here.
    """
    try:
        versions={'cpu-prefetch-stage17-formal-service-capture/1':'Q16b',
                  'cpu-prefetch-stage17-formal-scheduled-capture/2':'Q16c'}
        action=versions[capture['schema_version']]
        require(action == 'Q16c', 'sealed-source validator is Q16c-only')
        _input(capture,resources,monitoring,action)
        capture = _checked_original_values(root, control, capture)
        pre,session,windows=_session(control,final,capture,action)
        regions=d210._common_controls(control,final,pre,session,capture,resources,monitoring,hardware_control)
        arena=d210._arena(control,capture,regions)
        require(len(control['phases'])==2,'two primary phases')
        seen=set();retained=[]
        nodes=_node_order(root,control,capture,action,seen,retained)
        schedules=None
        if action=='Q16c':
            _schedule_mapping(control,capture,resources)
            require(len(control['schedules'])==2 and len(pre['session']['schedules'])==2,'two prepared source schedules')
            schedules=[_schedule(root,control,capture,i,windows[i],seen,retained) for i in range(2)]
        phases=[_join_phase(root,control['phases'][i],session['phases'][i],capture,resources,i,windows[i],arena,action,seen,retained) for i in range(2)]
        d210._stable_files(root,retained)
        return dict(schema_version=SCHEMA_ID,action_id=action,method_id=plans.METHOD[action],
                    source_versions=dict(SOURCE_VERSIONS,control=CONTROL_IDS[action]),capture_ordinal=capture['ordinal'],
                    phases=phases,node_order=nodes,schedules=schedules,raw_reconciliation_validated=True,
                    capture_execution_evidence_validated=True,zero_loss_all_phases=all(p['zero_loss'] for p in phases),
                    measurement_zero_loss=phases[1]['zero_loss'],family_validity_established=False,
                    execution_authority=False,phase18_authority=False)
    except ValidationError:raise
    except (KeyError,TypeError,ValueError,IndexError,OSError,codec.DecodeError,OverflowError) as error:
        raise ValidationError('formal service/scheduled evidence rejected: '+str(error)) from error
