"""Verified-source cold archive administration over the original qualified release.

The explicit packet hash comes from the caller's recorded command/configuration.
It authenticates administrative source only and never substitutes for phase
authority, the qualified journal, native release or archive profile admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

EVIDENCE = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
BOOTSTRAP_SHA = 'b1feb13f9cbcfa9ec6c41d11662c64f1b8f11d591f311f75a2d166f6fe94be23'
CONFIG_SHA = '5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93'
SCHEMA = 'cpu-prefetch-stage17-formal-admin-packet/3'
MAX_FILE = 2 * 1024**2
MAX_TOTAL = 16 * 1024**2
MAX_DESCRIPTOR = 131072
DESCRIPTOR = 'archive-overlay.json'
DEPENDENCIES = ('stage17_q16a_handoff_v1', 'stage17_phase_controller_v27',
                'stage17_operational_cli_v20', 'stage17_archive_overlay_v1',
                'stage17_phase_controller_v28', 'stage17_operational_cli_v21')
REQUIRED = frozenset((*[name + '.py' for name in DEPENDENCIES],
                      'stage17_formal_admin_v3.py',
                      'stage17_archive_inverse_native_v1.py', DESCRIPTOR))
_ACTIVE = None
_LOADED = {}


def require(condition, message):
    if not condition:
        raise ValueError('formal administration: ' + message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('noninteger JSON: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def bounded_bytes(path):
    path = Path(path)
    require(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'absolute nonsymlink metadata path')
    def stamp(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_FILE, 'bounded regular source required')
        data = stream.read(MAX_FILE + 1)
        require(len(data) == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.stat(follow_symlinks=False)), 'source changed during read')
    return data


def verify_packet(root, expected_sha256):
    require(type(expected_sha256) is str and re.fullmatch('[0-9a-f]{64}', expected_sha256), 'explicit packet SHA256 required')
    root = Path(root)
    raw = bounded_bytes(root / 'manifest.json')
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'packet manifest differs')
    document = strict_json(raw)
    require(document['schema_version'] == SCHEMA, 'packet schema differs')
    require(document['qualified_worker_unchanged'] is True and document['execution_authority'] is False, 'packet authority/release declaration differs')
    require(type(document['source_revision']) is str and re.fullmatch('[0-9a-f]{40}', document['source_revision']), 'source revision required')
    rows = document['files']
    require(type(rows) is list and len(REQUIRED) <= len(rows) <= 64, 'finite packet member list required')
    seen = set()
    total = len(raw)
    for row in rows:
        require(type(row) is dict and set(row) == {'name', 'size_bytes', 'sha256'}, 'packet member shape')
        name = row['name']
        require(type(name) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*', name) and name != 'manifest.json' and name not in seen, 'flat unique packet member required')
        seen.add(name)
        require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= MAX_FILE, 'source size bound')
        if name == DESCRIPTOR:
            require(row['size_bytes'] <= MAX_DESCRIPTOR, 'descriptor size bound')
        total += row['size_bytes']
        require(total <= MAX_TOTAL, 'aggregate packet source bound')
        data = bounded_bytes(root / name)
        require(len(data) == row['size_bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], 'packet source differs: ' + name)
    require(REQUIRED <= seen, 'complete formal administrative closure required')
    return document


def load_verified_source(name, path, raw):
    """Execute the already hash-verified bytes, never a path/pyc cache lookup."""
    require(name not in sys.modules, 'unverified cached module: ' + name)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition('.')[0]
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    except BaseException:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise
    functions = {key: (value, value.__code__) for key, value in vars(module).items()
                 if isinstance(value, types.FunctionType)}
    modules = {key: value for key, value in vars(module).items() if isinstance(value, types.ModuleType)}
    _LOADED[name] = (module, str(path), functions, modules)
    return module


def check_verified_modules():
    for name, (module, path, functions, modules) in _LOADED.items():
        require(sys.modules.get(name) is module and module.__file__ == path, 'verified module replaced: ' + name)
        for key, (function, code) in functions.items():
            require(vars(module).get(key) is function and function.__code__ is code, 'verified function replaced: ' + name + '.' + key)
        for key, value in modules.items():
            require(vars(module).get(key) is value, 'verified import replaced: ' + name + '.' + key)


def reject_foreign_cache(bootstrap_directory):
    names = {p.stem for p in bootstrap_directory.glob('*.py')}
    for name, module in tuple(sys.modules.items()):
        if name in names or name.startswith('stage17_'):
            require(name == __name__ and vars(module) is globals(), 'unverified project cache before activation: ' + name)


def verified_member(root, manifest, name):
    """Rebind a read to its exact manifest row immediately before consuming it."""
    row = next(row for row in manifest['files'] if row['name'] == name)
    raw = bounded_bytes(root / name)
    require(len(raw) == row['size_bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
            'source changed before use: ' + name)
    return raw


def configure_descriptor(root, manifest):
    # Pass bytes, not a pathname: the overlay must never reopen an unchecked
    # descriptor. Repeat this on trusted reentry as well as first activation.
    raw = verified_member(root, manifest, DESCRIPTOR)
    descriptor = strict_json(raw)
    require(type(descriptor) is dict and descriptor.get('source_revision') == manifest['source_revision'],
            'descriptor source revision differs from packet')
    sys.modules['stage17_archive_overlay_v1'].configure_verified_descriptor(raw, root)


def check_entrypoint():
    for key, (function, code) in _ENTRY_FUNCTIONS.items():
        require(globals().get(key) is function and function.__code__ is code,
                'administrative entrypoint function replaced: ' + key)
    for key, module in _ENTRY_MODULES.items():
        require(globals().get(key) is module, 'administrative entrypoint import replaced: ' + key)


def activate_packet(expected_sha256):
    global _ACTIVE
    check_entrypoint()
    require(os.getuid() == os.geteuid() == 1000, 'trusted owner credentials required')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'stand boot changed')
    here = Path(__file__).resolve().parent
    manifest = verify_packet(here, expected_sha256)
    if _ACTIVE is not None:
        require(_ACTIVE[0] == expected_sha256 and _ACTIVE[1] == here, 'different packet in admitted interpreter')
        check_verified_modules()
        configure_descriptor(here, manifest)
        check_verified_modules()
        return _ACTIVE[2]
    original = EVIDENCE / 'offline-suffix-operators-1'
    reject_foreign_cache(original)
    bootstrap_raw = bounded_bytes(original / 'validate_suffix.py')
    require(hashlib.sha256(bootstrap_raw).hexdigest() == BOOTSTRAP_SHA, 'original qualified bootstrap changed')
    sys.path.insert(0, str(original))
    bootstrap = load_verified_source('validate_suffix', original / 'validate_suffix.py', bootstrap_raw)
    config = bootstrap.config(EVIDENCE / 'offline-suffix-preparation-1/inputs/analysis-config.json', CONFIG_SHA)
    # Authenticate the original source/policy/module closure and original D242
    # adapter. New formal commands perform their own current journal admission.
    bootstrap.modules(config)
    sys.path.insert(0, str(here))
    # Dependency order is explicit. No preloaded new module or cached bytecode
    # can substitute for the packet bytes authenticated above.
    for name in DEPENDENCIES:
        path = here / (name + '.py')
        raw = verified_member(here, manifest, path.name)
        load_verified_source(name, path, raw)
    cli = sys.modules['stage17_operational_cli_v21']
    check_verified_modules()
    configure_descriptor(here, manifest)
    check_verified_modules()
    _ACTIVE = (expected_sha256, here, cli)
    return cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet-manifest-sha256', required=True)
    args, remaining = parser.parse_known_args()
    require(bool(remaining) and remaining[0] in ('author-formal-request', 'author-formal-authorization',
        'verify-formal-signature', 'execute-formal', 'admit-formal-retention'), 'explicit formal command required')
    cli = activate_packet(args.packet_manifest_sha256)
    sys.argv = [str(Path(cli.__file__)), *remaining]
    return cli.main()


_ENTRY_FUNCTIONS = {key: (value, value.__code__) for key, value in tuple(globals().items())
                    if isinstance(value, types.FunctionType) and value.__module__ == __name__}
_ENTRY_MODULES = {key: value for key, value in tuple(globals().items())
                  if isinstance(value, types.ModuleType)}


if __name__ == '__main__':
    raise SystemExit(main())
