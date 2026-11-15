"""Build a separate cold timing candidate; grants no experiment authority."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import shutil

import stage17_archive_bundle_profile_v1 as profiles
from stage17_archive_overlay_v1 import canonical

PATCH = (b'\n\n# D253: full fresh native inventory and bounded metadata reads.\n'
         b'from stage17_archive_inventory_native_v1 import make_store_class as _d253_inventory_store\n'
         b'ProgramStore = _d253_inventory_store(base=ProgramStore)\n')
MODULES = ('stage17_archive_metadata_fast_v2', 'stage17_archive_inventory_native_v1')


def image_source(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 1024**2 or raw[:4] != b'\x7fELF':
        raise ValueError('finite inventory ELF required')
    encoded = base64.b85encode(raw)
    lines = [b'"""Generated exact sealed cold inventory image; no execution authority."""',
             ('IMAGE_SIZE_BYTES = ' + str(len(raw))).encode(),
             ('IMAGE_SHA256 = ' + repr(hashlib.sha256(raw).hexdigest())).encode(), b'IMAGE_B85 = (']
    lines.extend(b'    ' + repr(encoded[i:i + 100]).encode() for i in range(0, len(encoded), 100))
    return b'\n'.join([*lines, b')', b''])


def build_candidate(*, baseline_bundle_root, runtime_root, destination, native_library, source_root):
    baseline, destination = Path(baseline_bundle_root), Path(destination)
    original = profiles.verify_profile(bundle_root=baseline, runtime_root=Path(runtime_root))
    if destination.exists():
        raise ValueError('new cold candidate namespace required')
    destination.mkdir(mode=0o700, parents=True)
    members = [original['encoder'], original['zstd_library'], *(m['image'] for m in original['source_closure'])]
    for item in members:
        if item['location'] != 'bundle':
            raise ValueError('original cold member is not bundle-local')
        source = profiles.regular(baseline, item['path'])
        target = destination / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(source.stat().st_mode & 0o777)
        if profiles.binding(destination, item['path']) != {k: item[k] for k in ('path', 'size_bytes', 'sha256')}:
            raise ValueError('copied cold member changed')
    tools = destination / 'tools'
    custody = tools / 'stage17_formal_archive_custody_v1.py'
    custody.write_bytes(custody.read_bytes() + PATCH)
    for name in MODULES:
        source = Path(source_root) / (name + '.py')
        shutil.copyfile(source, tools / source.name)
    raw = Path(native_library).read_bytes()
    (tools / 'stage17_archive_inventory_image_v1.py').write_bytes(image_source(raw))
    profile = profiles.build_profile(bundle_root=destination, runtime_root=Path(runtime_root),
                                     window_log=original['options']['window_log'])
    path = destination / profiles.PROFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(profile)
    path.write_bytes(payload)
    profiles.verify_profile(bundle_root=destination, runtime_root=Path(runtime_root))
    return dict(schema_version='cpu-prefetch-stage17-cold-inventory-candidate/1', execution_authority=False,
                measurement_changes=False, baseline_profile_sha256=hashlib.sha256(
                    (baseline / profiles.PROFILE_PATH).read_bytes()).hexdigest(),
                profile=dict(path=str(path), size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest()),
                native_image=dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
