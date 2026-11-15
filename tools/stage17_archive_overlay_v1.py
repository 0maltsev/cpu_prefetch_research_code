"""D252 separately admitted cold archive implementation over a qualified worker.

Only cold reconstruction, serialization and inventory traversal change. The
original encoder, interpreter, zstd, source bodies, framing and two custody
readbacks are authenticated and retained.
The signed new plan names the new profile hash; the verified administrative
packet supplies this overlay's exact descriptor. Neither is execution authority
by itself. Existing native-release and signature/journal admission still apply.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

import stage17_archive_bundle_profile_v1 as bundle_profile
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as archive
import stage17_phase_controller_v26 as qualified

SCHEMA = 'cpu-prefetch-stage17-cold-archive-overlay/1'
SOURCE = '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
WORKER_SHA256 = '7abf4cfac0051103f98b3f63f37efd1bde757d954c973460be6fe4d245f6a275'
PROFILE_MEMBER = 'config/stage17/formal-archive-implementation-profile-v1.json'
NATIVE_MODULE = 'stage17_archive_inverse_native_v1'
IMAGE_MODULE = 'stage17_archive_inverse_image_v1'
CANONICAL_MODULE = 'stage17_archive_canonical_fast_v1'
METADATA_MODULE = 'stage17_archive_metadata_fast_v1'
PATCH = (b'\n\n# D252: cold byte-exact native inverse; all verifier checks stay above.\n'
         b'from stage17_archive_inverse_native_v1 import inverse_columns as inverse_columns\n'
         b'from stage17_archive_canonical_fast_v1 import canonical as canonical\n')
CUSTODY_PATCH = (b'\n\n# D252: private cold metadata class; every quota observation remains live.\n'
                 b'from stage17_archive_metadata_fast_v1 import make_store_class as _d252_make_store_class\n'
                 b'ProgramStore = _d252_make_store_class(base=ProgramStore)\n')
_CONFIG = None


def require(condition, message):
    if not condition:
        raise ValueError('cold archive overlay: ' + message)


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def binding(path):
    path = Path(path)
    require(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'absolute nonsymlink path required')
    with archive.open_regular(path) as stream:
        before = archive.file_stamp(os.fstat(stream.fileno()))
        raw = stream.read(16 * 1024**2 + 1)
        require(0 < len(raw) <= 16 * 1024**2, 'finite implementation member required')
        require(before == archive.file_stamp(os.fstat(stream.fileno())) == archive.file_stamp(path.stat()), 'implementation member changed')
    return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def image_source(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 1024**2 and raw[:4] == b'\x7fELF', 'finite ELF image required')
    encoded = base64.b85encode(raw)
    lines = [b'"""Generated exact sealed cold inverse image; bound by the archive profile."""',
             ('IMAGE_SIZE_BYTES = ' + str(len(raw))).encode(),
             ('IMAGE_SHA256 = ' + repr(hashlib.sha256(raw).hexdigest())).encode(), b'IMAGE_B85 = (']
    lines.extend(b'    ' + repr(encoded[i:i + 100]).encode() for i in range(0, len(encoded), 100))
    return b'\n'.join([*lines, b')', b''])


def image_from_source(raw):
    require(len(raw) <= 2 * 1024**2, 'image source bound')
    tree = ast.parse(raw)
    require(len(tree.body) == 4 and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant), 'generated image grammar')
    values = {}
    for statement, name in zip(tree.body[1:], ('IMAGE_SIZE_BYTES', 'IMAGE_SHA256', 'IMAGE_B85')):
        require(isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == name, 'generated image assignments')
        values[name] = ast.literal_eval(statement.value)
    require(type(values['IMAGE_B85']) is bytes and len(values['IMAGE_B85']) <= 2 * 1024**2, 'generated image payload bound')
    image = base64.b85decode(values['IMAGE_B85'])
    require(type(values['IMAGE_SIZE_BYTES']) is int and len(image) == values['IMAGE_SIZE_BYTES']
            and hashlib.sha256(image).hexdigest() == values['IMAGE_SHA256'], 'generated image binding differs')
    require(image_source(image) == raw, 'generated image source differs')
    return image


def configure_verified_descriptor(raw, root):
    global _CONFIG
    require(type(raw) is bytes and 0 < len(raw) <= 131072, 'finite verified descriptor required')
    document = archive.parse_json(raw)
    require(canonical(document) == raw, 'canonical descriptor required')
    require(set(document) == {'schema_version', 'source_revision', 'qualified_release', 'qualified_worker_sha256',
            'baseline_bundle_root', 'runtime_root', 'overlay_bundle_root', 'baseline_profile', 'overlay_profile',
            'native_image', 'wrapper_source', 'canonical_source', 'metadata_source', 'execution_authority', 'measurement_changes'}, 'descriptor fields')
    require(document['schema_version'] == SCHEMA and document['qualified_release'] == SOURCE
            and document['qualified_worker_sha256'] == WORKER_SHA256, 'original qualified worker differs')
    require(document['execution_authority'] is False and document['measurement_changes'] is False, 'cold-only descriptor required')
    require(type(document['source_revision']) is str and re.fullmatch('[0-9a-f]{40}', document['source_revision']), 'clean source revision required')
    root = Path(root)
    require(root.is_absolute() and all(not p.is_symlink() for p in (root, *root.parents)), 'absolute packet root required')
    for key in ('baseline_bundle_root', 'runtime_root', 'overlay_bundle_root'):
        p = Path(document[key])
        require(p.is_absolute() and p.is_dir() and all(not q.is_symlink() for q in (p, *p.parents)), 'explicit implementation root required')
    for key in ('baseline_profile', 'overlay_profile', 'wrapper_source', 'canonical_source', 'metadata_source'):
        value = document[key]
        require(type(value) is dict and set(value) == {'path', 'size_bytes', 'sha256'}, 'implementation binding fields')
        require(type(value['size_bytes']) is int and value['size_bytes'] > 0
                and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'implementation binding values')
    native = document['native_image']
    require(type(native) is dict and set(native) == {'size_bytes', 'sha256'}
            and type(native['size_bytes']) is int and 0 < native['size_bytes'] <= 1024**2
            and type(native['sha256']) is str and re.fullmatch('[0-9a-f]{64}', native['sha256']), 'native image binding')
    require(Path(document['baseline_profile']['path']) == Path(document['baseline_bundle_root']) / PROFILE_MEMBER
            and Path(document['overlay_profile']['path']) == Path(document['overlay_bundle_root']) / PROFILE_MEMBER
            and Path(document['wrapper_source']['path']) == root / (NATIVE_MODULE + '.py')
            and Path(document['canonical_source']['path']) == root / (CANONICAL_MODULE + '.py')
            and Path(document['metadata_source']['path']) == root / (METADATA_MODULE + '.py'), 'implementation namespace differs')
    require(Path(document['baseline_bundle_root']) != Path(document['overlay_bundle_root']), 'historical bundle must remain separate')
    value = (bytes(raw), root, document)
    require(_CONFIG is None or _CONFIG == value, 'descriptor changed in admitted interpreter')
    _CONFIG = value
    return document


def qualified_profile(request, validation, *, deadline_ns):
    require(_CONFIG is not None, 'verified packet descriptor not configured')
    _, root, document = _CONFIG
    require(canonical(document) == _CONFIG[0], 'configured descriptor mutated')
    require(request['action_id'] in ('Q16b', 'Q16c'), 'cold overlay limited to future Q16b/Q16c')
    context = validation.resolutions['S17-EXT-006'].semantic_context
    baseline = document['baseline_profile']
    admitted = context['archive_profile_binding']
    require(context['archive_bundle_root'] == document['baseline_bundle_root']
            and context['archive_runtime_root'] == document['runtime_root']
            and admitted == dict(path=PROFILE_MEMBER, size_bytes=baseline['size_bytes'], sha256=baseline['sha256']), 'original EXT006 archive context differs')
    plan = request['action_inputs']['plan']
    require(plan['storage']['implementation_profile_sha256'] == document['overlay_profile']['sha256'], 'signed plan does not name exact overlay profile')
    original_request = {**request, 'action_inputs': {**request['action_inputs'], 'plan': {
        **plan, 'storage': {**plan['storage'], 'implementation_profile_sha256': baseline['sha256']}}}}
    original = qualified.qualified_archive_profile(original_request, validation, deadline_ns=deadline_ns)
    expected = document['overlay_profile']
    overlay = runtime.load_runtime_profile(Path(expected['path']),
        expected=archive.PhysicalBinding(expected['size_bytes'], expected['sha256']),
        bundle_root=Path(document['overlay_bundle_root']), runtime_root=Path(document['runtime_root']),
        max_profile_bytes=131072, deadline_ns=deadline_ns)
    # Root relocation is allowed only for identical implementation bytes.
    for key in ('encoder', 'python'):
        left, right = getattr(original, key), getattr(overlay, key)
        require((left.size_bytes, left.sha256) == (right.size_bytes, right.sha256), key + ' bytes changed')
    require(original.python.path == overlay.python.path
            and original.decoder.zstd_library_sha256 == overlay.decoder.zstd_library_sha256
            and original.decoder.window_log == overlay.decoder.window_log, 'runtime dependency/options changed')
    old = runtime._closure_bytes(original, deadline_ns)
    new = runtime._closure_bytes(overlay, deadline_ns)
    require(set(new) == set(old) | {NATIVE_MODULE, IMAGE_MODULE, CANONICAL_MODULE, METADATA_MODULE}, 'cold overlay source membership differs')
    for name, (_, source) in old.items():
        patch = PATCH if name == 'stage17_formal_archive_v1' else CUSTODY_PATCH if name == 'stage17_formal_archive_custody_v1' else b''
        expected_source = source + patch
        require(new[name][1] == expected_source, 'historical verifier body changed: ' + name)
    require(binding(root / (NATIVE_MODULE + '.py')) == document['wrapper_source'], 'packet wrapper changed')
    wrapper = new[NATIVE_MODULE][1]
    require(len(wrapper) == document['wrapper_source']['size_bytes']
            and hashlib.sha256(wrapper).hexdigest() == document['wrapper_source']['sha256'], 'sealed wrapper differs from admitted packet')
    require(binding(root / (CANONICAL_MODULE + '.py')) == document['canonical_source'], 'packet canonicalizer changed')
    source = new[CANONICAL_MODULE][1]
    require(len(source) == document['canonical_source']['size_bytes']
            and hashlib.sha256(source).hexdigest() == document['canonical_source']['sha256'], 'sealed canonicalizer differs from admitted packet')
    require(binding(root / (METADATA_MODULE + '.py')) == document['metadata_source'], 'packet metadata adapter changed')
    source = new[METADATA_MODULE][1]
    require(len(source) == document['metadata_source']['size_bytes']
            and hashlib.sha256(source).hexdigest() == document['metadata_source']['sha256'], 'sealed metadata adapter differs from admitted packet')
    image = image_from_source(new[IMAGE_MODULE][1])
    require(dict(size_bytes=len(image), sha256=hashlib.sha256(image).hexdigest()) == document['native_image'], 'sealed native image differs')
    return overlay


def build_overlay(*, baseline_bundle_root, runtime_root, destination, native_library, wrapper, source_revision):
    """Create a new immutable candidate directory; never rewrite the old bundle."""
    baseline_bundle_root = Path(baseline_bundle_root)
    runtime_root, destination, wrapper = Path(runtime_root), Path(destination), Path(wrapper)
    original = bundle_profile.verify_profile(bundle_root=baseline_bundle_root, runtime_root=runtime_root)
    require(not destination.exists(), 'new overlay directory required')
    destination.mkdir(parents=True, mode=0o700)
    members = [original['encoder'], original['zstd_library'], *(m['image'] for m in original['source_closure'])]
    for item in members:
        require(item['location'] == 'bundle', 'original cold member namespace differs')
        source = bundle_profile.regular(baseline_bundle_root, item['path'])
        target = destination / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(source.stat().st_mode & 0o777)
        require(bundle_profile.binding(destination, item['path']) == {k: item[k] for k in ('path', 'size_bytes', 'sha256')}, 'copied member differs')
    tools = destination / 'tools'
    p = tools / 'stage17_formal_archive_v1.py'
    p.write_bytes(p.read_bytes() + PATCH)
    p = tools / 'stage17_formal_archive_custody_v1.py'
    p.write_bytes(p.read_bytes() + CUSTODY_PATCH)
    shutil.copyfile(wrapper, tools / (NATIVE_MODULE + '.py'))
    canonical_source = wrapper.parent / (CANONICAL_MODULE + '.py')
    shutil.copyfile(canonical_source, tools / canonical_source.name)
    metadata_source = wrapper.parent / (METADATA_MODULE + '.py')
    shutil.copyfile(metadata_source, tools / metadata_source.name)
    native = Path(native_library).read_bytes()
    (tools / (IMAGE_MODULE + '.py')).write_bytes(image_source(native))
    document = bundle_profile.build_profile(bundle_root=destination, runtime_root=runtime_root, window_log=original['options']['window_log'])
    profile = destination / PROFILE_MEMBER
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_bytes(canonical(document))
    bundle_profile.verify_profile(bundle_root=destination, runtime_root=runtime_root)
    return dict(schema_version=SCHEMA, source_revision=source_revision,
        qualified_release=SOURCE, qualified_worker_sha256=WORKER_SHA256,
        baseline_bundle_root=str(baseline_bundle_root), runtime_root=str(runtime_root), overlay_bundle_root=str(destination),
        baseline_profile=binding(baseline_bundle_root / PROFILE_MEMBER), overlay_profile=binding(profile),
        wrapper_source=binding(wrapper), canonical_source=binding(canonical_source), metadata_source=binding(metadata_source),
        native_image=dict(size_bytes=len(native), sha256=hashlib.sha256(native).hexdigest()),
        execution_authority=False, measurement_changes=False)
