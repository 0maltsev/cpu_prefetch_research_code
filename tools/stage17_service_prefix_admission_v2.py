"""Read the exact D261 software diagnostic without weakening scientific JSON.

The 5742-byte, hash-pinned analysis manifest contains elapsed-time diagnostics.
Parse those decimals exactly only for that already authenticated document.
Every plan, report, checkpoint, receipt, source and hardware input keeps the
original integer-only reader. This module authorizes no admission retry.
"""
from decimal import Decimal
import hashlib
import json
import types

import stage17_service_prefix_admission_v1 as previous
import stage17_archive_metadata_fast_v1 as metadata

SIZE=5742
SHA256=previous.VALIDATION_SHA256


def software_diagnostic(raw):
    previous.require(type(raw) is bytes and len(raw)==SIZE
        and hashlib.sha256(raw).hexdigest()==SHA256,'exact completed software diagnostic required')
    def pairs(items):
        result={}
        for key,value in items:
            previous.require(key not in result,'duplicate diagnostic JSON key');result[key]=value
        return result
    def invalid(value):raise previous.admission.AdmissionError('nonfinite diagnostic '+value)
    document=json.loads(raw,object_pairs_hook=pairs,parse_float=Decimal,parse_constant=invalid)
    previous.require(type(document['captures']) is int and document['captures']==17
        and document['all_raw_reconstructed_and_hash_checked'] is True,'completed17 diagnostic required')
    elapsed=document['elapsed_seconds']
    previous.require(type(elapsed) in (int,Decimal) and 0<elapsed<=5400,'original finite software-analysis duration')
    previous.require(len(document['reports'])==17,'all17 diagnostic report bindings required')
    for ordinal,row in enumerate(document['reports']):
        previous.require(type(row['ordinal']) is int and row['ordinal']==ordinal,'original report order')
        duration=row['seconds']
        previous.require(type(duration) in (int,Decimal) and 0<duration<=900,'original per-capture analysis duration')
    return document


class DiagnosticReader(previous.admission.BoundReader):
    def document(self,binding):
        if binding.get('size_bytes')==SIZE and binding.get('sha256')==SHA256:
            return software_diagnostic(self.read(binding))
        return super().document(binding)


def admit(plan,validation):
    admission_globals={**vars(previous.admission),'BoundReader':DiagnosticReader}
    scope={**previous.admit.__globals__,
           'admission':types.SimpleNamespace(**admission_globals)}
    return metadata._clone(previous.admit,scope)(plan,validation)
