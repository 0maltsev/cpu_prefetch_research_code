"""D273 cold archive overlay admission for the approved D270 Q16c /3 screen.

The caller supplies a descriptor from an authenticated administrative packet
and an already authenticated EXT006 validation context. This module confers no
authority, qualifies no native worker, and never launches an experiment.
The actual qualified source/worker and original archive profile remain bound
to EXT006; only a copy of the request's selected profile SHA is substituted
when invoking v26's original archive qualification.

Descriptor /1 has explicit source_revision (packet provenance),
qualified_source_revision, qualified_worker_sha256, baseline_bundle_root,
runtime_root, overlay_bundle_root, baseline_profile, overlay_profile,
native_image, inventory_native_image, and sources. Each profile/source binding
is {path,size_bytes,sha256}; native bindings are {size_bytes,sha256}. sources
maps exactly EXTRA_MODULES to files directly under packet_root. Both
execution_authority and measurement_changes must be false. No revision or
worker hash is inferred from the development checkout or historical overlay.
"""
from __future__ import annotations

import ast
import base64
import hashlib
from pathlib import Path
import re
import time

import stage17_archive_inventory_bundle_v1 as inventory_bundle
import stage17_archive_overlay_v1 as oldv1
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as archive
import stage17_formal_scheduled_descriptive_v1 as daycap
import stage17_phase_controller_v26 as qualified

SCHEMA = 'cpu-prefetch-stage17-cold-archive-q16c-descriptive-overlay/1'
PROFILE_MEMBER = oldv1.PROFILE_MEMBER
NATIVE_MODULE = oldv1.NATIVE_MODULE
IMAGE_MODULE = oldv1.IMAGE_MODULE
INVENTORY_MODULE = 'stage17_archive_inventory_native_v1'
INVENTORY_IMAGE_MODULE = 'stage17_archive_inventory_image_v1'
EXTRA_MODULES = frozenset((NATIVE_MODULE, IMAGE_MODULE, oldv1.CANONICAL_MODULE,
    oldv1.METADATA_MODULE, *inventory_bundle.MODULES, INVENTORY_IMAGE_MODULE))
canonical = oldv1.canonical
binding = oldv1.binding
_CONFIG = None


def require(condition, message):
    if not condition:
        raise ValueError('cold archive daycap overlay: ' + message)


def _root(value):
    require(type(value) is str, 'explicit root string required')
    path = Path(value)
    require(path.is_absolute() and str(path) == value and '..' not in path.parts
            and path.is_dir() and all(not p.is_symlink() for p in (path, *path.parents)),
            'explicit absolute canonical nonsymlink root required')
    return path


def _physical(value, *, with_path):
    require(type(value) is dict and set(value) == ({'path', 'size_bytes', 'sha256'} if with_path
                                                  else {'size_bytes', 'sha256'}), 'binding fields')
    maximum = 16 * 1024**2 if with_path else 1024**2
    require(type(value['size_bytes']) is int and 0 < value['size_bytes'] <= maximum
            and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
            'binding size/hash values')
    if with_path:
        require(type(value['path']) is str, 'binding path string required')


def _source(value):
    """Read packet bytes with the same bounded, fresh identity checks as runtime."""
    return runtime._image_bytes(runtime.ImageBinding(Path(value['path']), value['size_bytes'], value['sha256']),
                                time.monotonic_ns() + 60_000_000_000)


def _inventory_image(raw):
    # Evaluate literals only. The inventory generator's docstring differs from
    # the old inverse generator; exact regeneration admits only its own syntax.
    require(len(raw) <= 2 * 1024**2, 'inventory image source bound')
    try:
        tree = ast.parse(raw)
        require(len(tree.body) == 4 and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant), 'inventory generated image grammar')
        values = {}
        for statement, name in zip(tree.body[1:], ('IMAGE_SIZE_BYTES', 'IMAGE_SHA256', 'IMAGE_B85')):
            require(isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == name,
                    'inventory generated image assignments')
            values[name] = ast.literal_eval(statement.value)
        _physical({key: values[name] for key, name in
                   (('size_bytes', 'IMAGE_SIZE_BYTES'), ('sha256', 'IMAGE_SHA256'))}, with_path=False)
        require(type(values['IMAGE_B85']) is bytes and len(values['IMAGE_B85']) <= 2 * 1024**2,
                'inventory image payload bound')
        image = base64.b85decode(values['IMAGE_B85'])
        require(len(image) == values['IMAGE_SIZE_BYTES']
                and hashlib.sha256(image).hexdigest() == values['IMAGE_SHA256'], 'inventory native image differs')
        require(inventory_bundle.image_source(image) == raw, 'inventory generated image source differs')
        return image
    except (SyntaxError, TypeError, KeyError) as error:
        raise ValueError('cold archive daycap overlay: invalid inventory image literals') from error


def _check_sources(document, *, closure=None, deadline_ns=None):
    for name, expected in document['sources'].items():
        require(binding(expected['path']) == expected, 'packet source changed: ' + name)
        if closure is not None:
            source = closure[name][1]
            require((len(source), hashlib.sha256(source).hexdigest()) ==
                    (expected['size_bytes'], expected['sha256']), 'sealed packet source differs: ' + name)
        elif name in (IMAGE_MODULE, INVENTORY_IMAGE_MODULE):
            source = _source(expected)
        else:
            continue
        if name == IMAGE_MODULE:
            image, field = oldv1.image_from_source(source), 'native_image'
        elif name == INVENTORY_IMAGE_MODULE:
            image, field = _inventory_image(source), 'inventory_native_image'
        else:
            continue
        require(dict(size_bytes=len(image), sha256=hashlib.sha256(image).hexdigest()) == document[field],
                'native image differs: ' + name)
    if deadline_ns is not None:
        require(time.monotonic_ns() < deadline_ns, 'qualification deadline expired')


def configure_verified_descriptor(raw, packet_root):
    """Pin one canonical, packet-bound descriptor per admitted interpreter.

    Authentication of raw/packet_root belongs to the caller. Successful shape,
    byte and namespace checks here grant no release or execution authority.
    """
    global _CONFIG
    require(type(raw) is bytes and 0 < len(raw) <= 131072, 'finite verified descriptor required')
    document = archive.parse_json(raw)
    require(type(document) is dict and canonical(document) == raw, 'canonical descriptor required')
    require(set(document) == {'schema_version', 'source_revision', 'qualified_source_revision',
        'qualified_worker_sha256', 'baseline_bundle_root', 'runtime_root', 'overlay_bundle_root',
        'baseline_profile', 'overlay_profile', 'native_image', 'inventory_native_image', 'sources',
        'execution_authority', 'measurement_changes'}, 'descriptor fields')
    require(document['schema_version'] == SCHEMA, 'descriptor schema')
    require(document['execution_authority'] is False and document['measurement_changes'] is False,
            'cold-only descriptor required')
    for key in ('source_revision', 'qualified_source_revision', 'qualified_worker_sha256'):
        require(type(document[key]) is str and re.fullmatch(
            '[0-9a-f]{64}' if key == 'qualified_worker_sha256' else '[0-9a-f]{40}', document[key]),
            'explicit source/worker binding required')
    root = _root(str(packet_root))
    roots = {key: _root(document[key]) for key in ('baseline_bundle_root', 'runtime_root', 'overlay_bundle_root')}
    require(roots['baseline_bundle_root'] != roots['overlay_bundle_root'], 'historical bundle must remain separate')
    for key, bundle_key in (('baseline_profile', 'baseline_bundle_root'), ('overlay_profile', 'overlay_bundle_root')):
        expected = document[key]
        _physical(expected, with_path=True)
        require(expected['path'] == str(roots[bundle_key] / PROFILE_MEMBER), 'profile namespace differs')
        require(binding(expected['path']) == expected, 'descriptor profile binding differs')
    for key in ('native_image', 'inventory_native_image'):
        _physical(document[key], with_path=False)
    require(type(document['sources']) is dict and set(document['sources']) == EXTRA_MODULES,
            'packet source membership differs')
    for name, expected in document['sources'].items():
        _physical(expected, with_path=True)
        require(expected['path'] == str(root / (name + '.py')), 'packet source namespace differs')
    _check_sources(document)
    value = (bytes(raw), root, document)
    require(_CONFIG is None or _CONFIG == value, 'descriptor changed in admitted interpreter')
    _CONFIG = value
    return document


def _profile_document(expected, deadline_ns):
    image = runtime.ImageBinding(Path(expected['path']), expected['size_bytes'], expected['sha256'])
    return archive.parse_json(runtime._image_bytes(image, deadline_ns))


def qualified_profile(request, validation, *, deadline_ns):
    """Admit the exact additive cold implementation after original qualification.

    Failures propagate; there is no qualification fallback or preparation bypass.
    The returned RuntimeProfile still requires the caller's ordinary signature,
    journal, hardware, namespace, deadline and execution admission gates.
    """
    require(_CONFIG is not None, 'verified packet descriptor not configured')
    raw, _, document = _CONFIG
    require(canonical(document) == raw, 'configured descriptor mutated')
    require(type(deadline_ns) is int and time.monotonic_ns() < deadline_ns, 'qualification deadline expired')
    require(type(request) is dict and request.get('action_id') == 'Q16c', 'D270 Q16c only')
    plan = request['action_inputs']['plan']
    require(plan.get('schema_version') == daycap.VERSION and plan.get('method_id') == daycap.METHOD,
            'D270 /3 plan and method required')
    daycap.validate_plan(plan)  # actual180 captures, complete bounds, <=24h; no projection
    require(plan['source_revision'] == document['qualified_source_revision'], 'plan qualified source differs')
    require(plan['storage']['implementation_profile_sha256'] == document['overlay_profile']['sha256'],
            'signed plan does not name exact overlay profile')
    context = validation.resolutions['S17-EXT-006'].semantic_context
    baseline = document['baseline_profile']
    require(context.get('source_revision') == document['qualified_source_revision']
            and context.get('release_artifact_sha256') == document['qualified_worker_sha256']
            and context.get('archive_bundle_root') == document['baseline_bundle_root']
            and context.get('archive_runtime_root') == document['runtime_root']
            and context.get('archive_profile_binding') == dict(path=PROFILE_MEMBER,
                size_bytes=baseline['size_bytes'], sha256=baseline['sha256']), 'original EXT006 source/worker/archive context differs')
    original_request = {**request, 'action_inputs': {**request['action_inputs'], 'plan': {
        **plan, 'storage': {**plan['storage'], 'implementation_profile_sha256': baseline['sha256']}}}}
    original = qualified.qualified_archive_profile(original_request, validation, deadline_ns=deadline_ns)
    expected = document['overlay_profile']
    overlay = runtime.load_runtime_profile(Path(expected['path']),
        expected=archive.PhysicalBinding(expected['size_bytes'], expected['sha256']),
        bundle_root=Path(document['overlay_bundle_root']), runtime_root=Path(document['runtime_root']),
        max_profile_bytes=131072, deadline_ns=deadline_ns)
    old_profile = _profile_document(baseline, deadline_ns)
    new_profile = _profile_document(expected, deadline_ns)
    # Identical image bindings permit bundle root relocation, while preserving
    # all encoder/Python/zstd bytes, relative namespaces and codec options.
    require(all(old_profile[key] == new_profile[key] for key in ('encoder', 'python', 'zstd_library', 'options')),
            'runtime dependency/options changed')
    old = runtime._closure_bytes(original, deadline_ns)
    new = runtime._closure_bytes(overlay, deadline_ns)
    require(not (set(old) & EXTRA_MODULES) and set(new) == set(old) | EXTRA_MODULES,
            'cold overlay source membership differs')
    require({'stage17_formal_archive_v1', 'stage17_formal_archive_custody_v1'} <= set(old),
            'baseline verifier bodies absent')
    for profile, root_key in ((old_profile, 'baseline_bundle_root'), (new_profile, 'overlay_bundle_root')):
        for member in profile['source_closure']:
            require(member['image']['location'] == 'bundle'
                    and member['image']['path'] == 'tools/' + member['module'] + '.py',
                    'source closure namespace differs: ' + root_key)
    for name, (_, source) in old.items():
        patch = (oldv1.PATCH if name == 'stage17_formal_archive_v1' else
                 oldv1.CUSTODY_PATCH + inventory_bundle.PATCH if name == 'stage17_formal_archive_custody_v1' else b'')
        require(new[name][1] == source + patch, 'historical verifier body changed: ' + name)
    _check_sources(document, closure=new, deadline_ns=deadline_ns)
    return overlay
