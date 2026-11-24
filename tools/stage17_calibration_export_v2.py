"""D239 archive-aware export preparation, without freeze/admission authority.

The D237 schema remains /1 and UNRESOLVED: this software successor changes only
which original prospective plans can be checked. Authenticated EXT007 admission
must separately verify the signed lifecycle and archival representation ledger.
"""
from __future__ import annotations

import types

import stage17_calibration_export_v1 as previous
import stage17_formal_calibration_v2 as calibration
import stage17_formal_plan_v2 as plans

SCHEMA_ID = previous.SCHEMA_ID
SCHEMA_PATH = previous.SCHEMA_PATH
ExportError = previous.ExportError


def _bind(function, replacements):
    result = types.FunctionType(function.__code__,
        {**function.__globals__, **replacements},
        name=function.__name__, argdefs=function.__defaults__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


_probe_reports = _bind(previous._probe_reports, {
    "calibration": types.SimpleNamespace(**{**vars(previous.calibration),
                                            "canonical": calibration.plan_bytes}),
})
_probe = _bind(previous._probe, {"_probe_reports": _probe_reports})
_build = _bind(previous._build, {
    "_probe": _probe,
    "plans": types.SimpleNamespace(**{**vars(previous.plans),
                                      "validate_plan": plans.validate_plan}),
    "calibration": types.SimpleNamespace(**{**vars(previous.calibration),
                                            "evaluate": calibration.evaluate}),
})
_export = _bind(previous.build_export, {"_build": _build})


def build_export(*, identity, owner_decision, source_packets):
    """Preserve exact original /2 lineage and all unresolved provenance gates."""
    return _export(identity=identity, owner_decision=owner_decision,
                   source_packets=source_packets)


_validate = _bind(previous.validate_export, {"build_export": build_export})


def validate_export(document, *, owner_decision, source_packets):
    """Recompute from original packets, with no authority promotion callback."""
    return _validate(document, owner_decision=owner_decision,
                     source_packets=source_packets)
