"""Exact D340 software edge from admitted descriptive calibration to S180.

The qualified operator supplies authenticated original-seven replay. This cold
verifier neither replays that journal nor qualifies current hardware. A mirror
is permitted explicitly for inspection only. No CLI, execution or retry exists.
"""
from __future__ import annotations
import contextlib
import hashlib
import os
from pathlib import Path
import stat

import check_formal_codegen as formal
import check_s180_codegen as pilot_codegen
import stage17_formal_archive_v1 as archive
import stage17_q16a_continuation_admission_v1 as readers
import stage17_s180_authority_v1 as authority

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'config/stage17/s180-calibration-compatibility-review-v1.json'
REVIEW_SHA='ef5c5868499f9b57be7c90ef92c27cc37185d3c36ff15e79077059d50dfd7642'
REVIEW_SCHEMA='cpu-prefetch-stage17-s180-calibration-compatibility-review/1'
SCHEMA='cpu-prefetch-stage17-s180-calibration-software-compatibility/1'
CALIBRATION_SCOPE='STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY'
INVENTORY_ENTRIES=8192
_TOKEN=object()


class CompatibilityError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise CompatibilityError('S180 compatibility: '+message)


def _same(value,expected,message):
    require(archive.canonical(value)==archive.canonical(expected),message)


def _review():
    # Qualified fixed input, never a data-selected exception or verifier.
    reader=readers.BoundReader()
    raw=reader.read(dict(path=str(REVIEW),size_bytes=REVIEW.stat().st_size,sha256=REVIEW_SHA))
    value=readers._json(raw);reader.finish()
    require(value['schema_version']==REVIEW_SCHEMA,'review version differs')
    return value


def _root(path):
    path=Path(path)
    require(path.is_absolute() and path.resolve(strict=True)==path and path.is_dir(),'canonical directory required')
    return path


def _inventory(document,root):
    rows=document['files']
    require(type(rows) is list and 0<len(rows)<=INVENTORY_ENTRIES,'bounded complete inventory required')
    result={}
    for row in rows:
        readers.fields(row,'path size_bytes sha256','inventory member')
        name=row['path'];require(type(name) is str and name not in result,'duplicate inventory member')
        require(name and not Path(name).is_absolute() and all(p not in ('','.','..') for p in name.split('/')),
            'noncanonical inventory member')
        readers._member(root,name)
        archive.uint(row['size_bytes'],'inventory member size');archive.sha(row['sha256'],'inventory member digest')
        result[name]=row
    return result


def _native_names(root):
    """Bounded complete source closure, including unexpected and hidden files."""
    names=set();pending=[root/'include',root/'src'];visited=0
    while pending:
        directory=pending.pop()
        require(stat.S_ISDIR(directory.lstat().st_mode),'source closure contains a symlink or nondirectory')
        require(len(directory.relative_to(root).parts)<=32,'source closure depth exceeded')
        with os.scandir(directory) as entries:
            for item in entries:
                visited+=1;require(visited<=4096,'source closure entry bound exceeded')
                require(not item.is_symlink(),'source closure contains a symlink')
                if item.is_dir(follow_symlinks=False):pending.append(Path(item.path))
                else:
                    require(stat.S_ISREG(item.stat(follow_symlinks=False).st_mode),'source closure contains a nonregular file')
                    names.add(str(Path(item.path).relative_to(root)))
    return names


def _ancestry(base,rules):
    rows=base.resolutions
    require(set(rows)=={f'S17-EXT-{i:03d}' for i in range(1,8)},'exact original-seven ancestry required')
    bindings=[]
    for key,row in sorted(rows.items()):
        require(row.input_id==key,'original input identity differs');archive.sha(row.sha256,'original resolution')
        bindings.append(authority.binding(row))
    release=rows['S17-EXT-006'];calibration=rows['S17-EXT-007']
    require(release.sha256==rules['original_ext006_sha256']
        and calibration.sha256==rules['original_ext007_sha256'],'accepted release/calibration ancestry differs')
    context=release.semantic_context;worker=rules['original_worker']
    require(context['source_revision']==rules['original_source_revision']
        and context['inventory_sha256']==rules['original_inventory']['sha256']
        and context['release_artifact_sha256']==worker['sha256']
        and context['release_artifact_size_bytes']==worker['size_bytes'],'qualified original release differs')
    root=context['archive_bundle_root']
    require(Path(root).is_absolute() and str(Path(root))==root and '..' not in Path(root).parts,
        'original release locator differs')
    require(context['release_artifact_path']==str(Path(root)/worker['path']),'original worker locator differs')
    value=calibration.semantic_context
    require(value.get('calibration_scope')==CALIBRATION_SCOPE and value.get('data_provenance_accepted') is True
        and value.get('legacy_statistical_freeze_satisfied') is False,'accepted descriptive calibration status differs')
    return bindings,archive.parse_json(archive.canonical(context))


def _codegen(original_report,current_report,*,original_bundle,source_root,worker):
    formal.validate_report_bindings(original_report,binary=original_bundle/'release/bin/cpu_prefetch_runner',
        source_root=original_bundle)
    pilot_codegen.validate_report_bindings(current_report,binary=worker,source_root=source_root,rule_root=ROOT)


class _VerifiedCompatibility:
    def __init__(self,*,token,receipt,files,paths):
        require(token is _TOKEN,'actual verification required')
        self._receipt=archive.canonical(receipt);self._files=archive.canonical(dict(files=files))
        self._paths=archive.canonical({k:str(v) for k,v in paths.items()});self.pid=os.getpid();self.failed=False

    def proof(self,*,base_validation,plan_sha256,for_execution=False):
        try:
            require(os.getpid()==self.pid and not self.failed,'owner belongs to another process or failed')
            require(type(for_execution) is bool,'explicit replay classification required')
            receipt=archive.parse_json(self._receipt)
            require(plan_sha256==receipt['plan_sha256'],'original plan differs')
            require(not for_execution or not receipt['inspection_mirror'],'inspection mirror cannot support execution')
            rules=_review();base,context=_ancestry(base_validation,rules)
            _same(base,receipt['base_resolutions'],'original-seven ancestry changed')
            _same(context,receipt['original_release_context'],'original qualified context changed')
            reader=readers.BoundReader()
            for row in archive.parse_json(self._files)['files']:reader.read(row)
            source=Path(archive.parse_json(self._paths)['source'])
            _same(sorted(_native_names(source)),receipt['current_native_sources'],'current source closure changed')
            reader.finish()
            return receipt
        except BaseException:
            self.failed=True
            raise


def verify(*,base_validation,plan_sha256,original_bundle,source_root,release_root,codegen_report,
        allow_inspection_mirror=False):
    """Verify actual bytes; signatures/replay/current hardware remain external."""
    archive.sha(plan_sha256,'exact pilot plan')
    require(type(allow_inspection_mirror) is bool,'explicit inspection classification required')
    rules=_review();base,context=_ancestry(base_validation,rules)
    old=_root(original_bundle);source=_root(source_root);build=_root(release_root)
    mirror=str(old)!=context['archive_bundle_root']
    require(not mirror or allow_inspection_mirror,'explicit inspection mirror required')
    reader=readers.BoundReader();files=[]
    def read(root,row):
        binding=dict(row,path=readers._member(root,row['path']))
        raw=reader.read(binding);files.append(binding);return raw
    inv=readers._json(read(old,rules['original_inventory']))
    require(inv['source_revision']==rules['original_source_revision'],'original inventory source differs')
    index=_inventory(inv,old)
    _same(index[rules['original_worker']['path']],rules['original_worker'],'original worker inventory differs')
    read(old,rules['original_worker']);read(build,rules['current_worker'])
    changes={r['path']:r for r in rules['changed_native_sources']}
    require(len(changes)==len(rules['changed_native_sources']),'reviewed source coverage differs')
    original_names=readers._source_names(index)
    new_names={n for n,r in changes.items() if r['original_sha256'] is None}
    supplemental={r['path']:r for r in rules['original_unbundled_native_sources']}
    require(len(supplemental)==len(rules['original_unbundled_native_sources'])
        and not set(supplemental)&(set(index)|set(changes)),'supplemental source coverage differs')
    native={n for n in original_names if n.startswith(('include/','src/'))}|new_names|set(supplemental)
    _same(sorted(_native_names(source)),sorted(native),'current native source closure differs')
    for name in sorted(original_names|new_names):
        before=None if name in new_names else read(old,index[name])
        path=source/name
        if name in changes:
            row=changes[name]
            require((None if before is None else hashlib.sha256(before).hexdigest())==row['original_sha256'],
                'reviewed original source differs')
            read(source,dict(path=name,size_bytes=path.stat().st_size,sha256=row['current_sha256']))
        else:
            # The old inventory is the authoritative expected digest/size.
            try:after=read(source,index[name])
            except readers.AdmissionError as error:raise CompatibilityError('shared source differs: '+name) from error
            require(after==before,'shared source differs: '+name)
    for row in supplemental.values():read(source,row)
    for row in rules['libraries']:
        _same(index[row['original']['path']],row['original'],'original library inventory differs')
        before=read(old,row['original']);after=read(build,row['current'])
        require((before==after) is row['identical'],'reviewed library identity differs')
    old_report=readers._json(read(old,index['build-provenance/formal_codegen_report.json']))
    metadata=readers._json(read(build,rules['current_build_metadata']))
    require(metadata['source_revision']==rules['current_source_revision'] and metadata['source_dirty'] is False
        and metadata['build_type']=='Release','clean frozen native provenance differs')
    path=Path(codegen_report)
    report_row=dict(rules['current_codegen'],path=path.name)
    current_report=readers._json(read(path.parent,report_row))
    _codegen(old_report,current_report,original_bundle=old,source_root=source,worker=build/rules['current_worker']['path'])
    # Retain actual rule inputs so completed proofs detect verifier/source drift.
    for name in ('tools/check_s180_codegen.py','tools/check_formal_codegen.py','tools/check_discovery_codegen.py'):
        path=ROOT/name;raw=path.read_bytes();read(ROOT,dict(path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    _same(sorted(_native_names(source)),sorted(native),'current native source closure changed during verification')
    reader.finish()
    receipt=dict(schema_version=SCHEMA,plan_sha256=plan_sha256,base_resolutions=base,
        original_release_context=context,original_source_revision=rules['original_source_revision'],
        current_source_revision=rules['current_source_revision'],review_sha256=REVIEW_SHA,
        original_bundle_physical_path=str(old),inspection_mirror=mirror,
        current_native_sources=sorted(native),reviewed_shared_changes=sorted(set(changes)-new_names),
        new_native_sources=sorted(new_names),calibration_scope=CALIBRATION_SCOPE,
        calibration_freeze_sha256=rules['calibration_freeze_sha256'],software_compatibility_verified=True,
        legacy_statistical_freeze_satisfied=False,full_ext008_admission=False,
        execution_authority=False,phase18_authority=False,files=files)
    return _VerifiedCompatibility(token=_TOKEN,receipt=receipt,files=files,paths=dict(source=source))
