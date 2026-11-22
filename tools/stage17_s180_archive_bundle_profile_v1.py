"""Fixed S180 archive package; byte verification is not live admission.

Preserve the historical D233 profile and codec contract. This separate package
adds the actual S180 broker closure, with explicit runtime roots and no worker,
hardware, schedule-generation or experiment entry point.
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time

import stage17_archive_bundle_profile_v1 as base
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as archive
from stage17_s180_checkpoint_v1 import APPROVAL_SHA256, BLUEPRINT_SHA256

PROFILE_PATH='config/stage17/s180-archive-implementation-profile-v1.json'
MANIFEST_PATH='S180_ARCHIVE_PACKAGE.json'
ROOT_MODULES=('stage17_formal_archive_runtime_v1','stage17_s180_archive_broker_v1')
PACKAGING_MODULES=('stage17_s180_archive_bundle_profile_v1','stage17_archive_bundle_profile_v1')
SCHEMA='cpu-prefetch-stage17-s180-archive-package/1'
SOURCE_LIMIT=2*1024**2
TOTAL_SOURCE_LIMIT=64*1024**2
ProfileError=base.ProfileError


def require(value,message):
    if not value:raise ProfileError('S180 archive package: '+message)


def source_closure(tools_root):
    """Both fixed entry roots, every flat local import and no missing stage17 import."""
    pending=list(ROOT_MODULES);found=set();total=0
    while pending:
        name=pending.pop()
        if name in found:continue
        require(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name),'invalid module name')
        path=base.regular(tools_root,name+'.py')
        size=path.stat().st_size;total+=size
        require(0<size<=SOURCE_LIMIT and total<=TOTAL_SOURCE_LIMIT,'source closure byte ceiling')
        raw=path.read_bytes();require(len(raw)==size,'source size changed')
        found.add(name)
        for node in ast.walk(ast.parse(raw,filename=str(path))):
            if isinstance(node,ast.Import):names=[n.name.split('.')[0] for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                require(not node.level,'relative imports outside fixed flat closure')
                names=[(node.module or '').split('.')[0]]
            else:continue
            for dep in names:
                if (Path(tools_root)/(dep+'.py')).exists():pending.append(dep)
                elif dep.startswith('stage17_'):raise ProfileError('missing local dependency: '+dep)
    return tuple(sorted(found))


def build_profile(*,bundle_root,runtime_root,window_log):
    bundle_root=base.explicit_root(bundle_root);runtime_root=base.explicit_root(runtime_root)
    require(type(window_log) is int and 10<=window_log<=31,'explicit accepted window_log required')
    def image(location,path):
        return dict(location=location,**base.binding(bundle_root if location=='bundle' else runtime_root,path))
    return dict(schema_version=base.SCHEMA_VERSION,policy_id=base.POLICY_ID,
        encoder=image('bundle',base.ENCODER_PATH),python=image('runtime',base.PYTHON_PATH),
        zstd_library=image('bundle',base.ZSTD_PATH),
        source_closure=[dict(module=name,image=image('bundle','tools/'+name+'.py'))
            for name in source_closure(bundle_root/'tools')],options=dict(base.OPTIONS,window_log=window_log))


def verify_profile(*,bundle_root,runtime_root):
    """Rebuild the exact fixed projection from actual files, never trust its list."""
    root=base.explicit_root(bundle_root)
    path=base.regular(root,PROFILE_PATH)
    require(path.stat().st_size<=16*1024**2,'profile byte ceiling')
    try:
        raw=path.read_bytes();document=archive.parse_json(raw)
        expected=build_profile(bundle_root=root,runtime_root=runtime_root,window_log=document['options']['window_log'])
        require(raw==base.canonical(document)==base.canonical(expected),'profile fields, membership or actual bytes differ')
    except (KeyError,TypeError,ValueError) as error:
        raise ProfileError('S180 profile rejected: '+str(error)) from error
    return document


def load_profile(*,bundle_root,runtime_root,expected,deadline_ns):
    """Caller must authenticate expected externally; this emits no admission."""
    require(type(deadline_ns) is int and time.monotonic_ns()<deadline_ns,'profile loading deadline expired')
    verify_profile(bundle_root=bundle_root,runtime_root=runtime_root)
    require(time.monotonic_ns()<deadline_ns,'profile loading deadline expired')
    return runtime.load_runtime_profile(Path(bundle_root)/PROFILE_PATH,expected=expected,
        bundle_root=Path(bundle_root),runtime_root=Path(runtime_root),max_profile_bytes=16*1024**2,deadline_ns=deadline_ns)


def _copy_exclusive(source,target):
    """An interrupted package is retained, never overwritten or adopted."""
    original=base.binding(source.parent,source.name)
    target.parent.mkdir(parents=True,exist_ok=True)
    require(not any(p.is_symlink() for p in (target,*target.parents)),'copy destination contains symlink')
    with source.open('rb') as src,target.open('xb') as dst:
        while block:=src.read(1024**2):dst.write(block)
        dst.flush();os.fsync(dst.fileno())
    os.chmod(target,0o444)
    require(base.binding(target.parent,target.name)==dict(original,path=target.name),'copied bytes differ')


def materialize(*,repository_root,bundle_root,runtime_root,window_log):
    """Cold component assembly into a fresh directory; encoder already supplied.

    The caller owns clean-source/release provenance. Tests may supply software
    images here; only create_package records a clean actual source revision.
    """
    repository_root=base.explicit_root(repository_root)
    bundle_root=base.explicit_root(bundle_root);runtime_root=base.explicit_root(runtime_root)
    require(type(window_log) is int and 10<=window_log<=31,'explicit accepted window_log required')
    require(not any(p.is_symlink() for p in (bundle_root/PROFILE_PATH,*(bundle_root/PROFILE_PATH).parents)),
        'profile destination contains symlink')
    require(not (bundle_root/PROFILE_PATH).exists() and not (bundle_root/MANIFEST_PATH).exists(),
        'package/profile already exists; no adoption')
    library=base.regular(runtime_root,'usr/lib/libzstd.so.1.5.7')
    codec=ctypes.CDLL(str(library));codec.ZSTD_versionNumber.restype=ctypes.c_uint
    require(codec.ZSTD_versionNumber()==10507,'exact zstd1.5.7 required')
    names=tuple(sorted(set((*source_closure(repository_root/'tools'),*PACKAGING_MODULES))))
    sources=[(base.regular(repository_root,'tools/'+n+'.py'),bundle_root/'tools'/(n+'.py')) for n in names]
    sources.extend(((library,bundle_root/base.ZSTD_PATH),
        (base.regular(runtime_root,'usr/share/licenses/zstd/LICENSE'),bundle_root/'licenses/zstd/LICENSE')))
    require(all(not p.exists() and not p.is_symlink() for _,p in sources),'destination conflicts; no overwrite')
    for source,target in sources:_copy_exclusive(source,target)
    document=build_profile(bundle_root=bundle_root,runtime_root=runtime_root,window_log=window_log)
    profile=bundle_root/PROFILE_PATH;profile.parent.mkdir(parents=True,exist_ok=True)
    with profile.open('xb') as stream:
        stream.write(base.canonical(document));stream.flush();os.fsync(stream.fileno())
    os.chmod(profile,0o444)
    verify_profile(bundle_root=bundle_root,runtime_root=runtime_root)
    return document


def _git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],timeout=30)


def create_package(*,repository_root,bundle_root,runtime_root,encoder,window_log):
    """Clean current Python source and independently bound existing encoder.

    No rebuild, native measurement, source generation or operational window.
    An incomplete output is retained on failure and cannot be reused.
    """
    root=base.explicit_root(repository_root);destination=Path(bundle_root)
    require(destination.is_absolute() and destination.parent.resolve(strict=True)==destination.parent,
        'absolute nonsymlink output parent required')
    revision=_git(root,'rev-parse','HEAD').decode().strip()
    require(re.fullmatch('[0-9a-f]{40}',revision) and not _git(root,'status','--porcelain'),
        'clean exact operator source required')
    destination.mkdir(mode=0o700)
    _copy_exclusive(base.regular(Path(encoder).parent,Path(encoder).name),destination/base.ENCODER_PATH)
    document=materialize(repository_root=root,bundle_root=destination,runtime_root=runtime_root,window_log=window_log)
    names=tuple(sorted(set((*source_closure(root/'tools'),*PACKAGING_MODULES))))
    for name in names:
        relative='tools/'+name+'.py'
        require(_git(root,'show',revision+':'+relative)==(destination/relative).read_bytes(),
            'package source differs from clean commit: '+name)
    require(_git(root,'rev-parse','HEAD').decode().strip()==revision and not _git(root,'status','--porcelain'),
        'source revision changed during assembly')
    files=sorted(p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file())
    manifest=dict(schema_version=SCHEMA,source_revision=revision,source_dirty=False,
        blueprint_sha256=BLUEPRINT_SHA256,approval_sha256=APPROVAL_SHA256,
        archive_profile=base.binding(destination,PROFILE_PATH),runtime_python=document['python'],
        files=[base.binding(destination,p) for p in files],
        scope='COLD_S180_ARCHIVE_COMPONENT_ONLY',native_worker_included=False,
        stand_qualification_performed=False,operational_window_started=False,
        execution_authority=False,phase18_authority=False)
    with (destination/MANIFEST_PATH).open('xb') as stream:
        stream.write(base.canonical(manifest));stream.flush();os.fsync(stream.fileno())
    os.chmod(destination/MANIFEST_PATH,0o444)
    return manifest


def verify_package(*,bundle_root,runtime_root,expected_manifest):
    root=base.explicit_root(bundle_root)
    require(base.binding(root,MANIFEST_PATH)==expected_manifest,'externally pinned manifest differs')
    manifest=archive.parse_json((root/MANIFEST_PATH).read_bytes())
    required=set(('schema_version source_revision source_dirty blueprint_sha256 approval_sha256 archive_profile '
        'runtime_python files scope native_worker_included stand_qualification_performed operational_window_started '
        'execution_authority phase18_authority').split())
    require(type(manifest) is dict and set(manifest)==required and manifest['schema_version']==SCHEMA
        and re.fullmatch('[0-9a-f]{40}',manifest['source_revision']) and manifest['source_dirty'] is False
        and manifest['scope']=='COLD_S180_ARCHIVE_COMPONENT_ONLY'
        and manifest['blueprint_sha256']==BLUEPRINT_SHA256 and manifest['approval_sha256']==APPROVAL_SHA256,
        'manifest scope/fields/source differs')
    require(all(manifest[k] is False for k in ('native_worker_included','stand_qualification_performed',
        'operational_window_started','execution_authority','phase18_authority')),'component cannot claim authority')
    paths=[r['path'] for r in manifest['files']]
    observed=[]
    for path in root.rglob('*'):
        require(not path.is_symlink(),'symlink package member')
        if path.is_file() and path!=root/MANIFEST_PATH:observed.append(path.relative_to(root).as_posix())
    require(paths==sorted(set(observed)),'exact package membership differs')
    require(manifest['files']==[base.binding(root,p) for p in paths],'package actual file bytes differ')
    profile=verify_profile(bundle_root=root,runtime_root=runtime_root)
    require(manifest['archive_profile']==base.binding(root,PROFILE_PATH)
        and manifest['runtime_python']==profile['python'],'profile/runtime manifest binding differs')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--encoder',type=Path,required=True)
    parser.add_argument('--window-log',type=int,required=True)
    args=parser.parse_args()
    manifest=create_package(repository_root=args.repository_root,bundle_root=args.output,
        runtime_root=args.runtime_root,encoder=args.encoder,window_log=args.window_log)
    verify_package(bundle_root=args.output,runtime_root=args.runtime_root,
        expected_manifest=base.binding(args.output,MANIFEST_PATH))
    print(base.canonical(dict(manifest=base.binding(args.output,MANIFEST_PATH),
        archive_profile=manifest['archive_profile'],operational_window_started=False,execution_authority=False)).decode())


if __name__=='__main__':main()
