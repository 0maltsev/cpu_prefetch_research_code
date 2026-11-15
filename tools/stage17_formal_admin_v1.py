"""D250 bound administrative entrypoint over the original qualified release.

The explicit packet hash comes from the caller's recorded command/configuration.
It authenticates administrative source only and never substitutes for phase
authority, the qualified journal, native release or archive profile admission.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys

EVIDENCE = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
BOOTSTRAP_SHA = 'b1feb13f9cbcfa9ec6c41d11662c64f1b8f11d591f311f75a2d166f6fe94be23'
CONFIG_SHA = '5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93'
SCHEMA = 'cpu-prefetch-stage17-formal-admin-packet/1'
MAX_FILE = 2 * 1024**2
MAX_TOTAL = 16 * 1024**2
REQUIRED = frozenset(('stage17_formal_admin_v1.py', 'stage17_operational_cli_v20.py',
                      'stage17_phase_controller_v27.py', 'stage17_q16a_handoff_v1.py'))


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
    require(type(rows) is list and 4 <= len(rows) <= 64, 'finite packet member list required')
    seen = set()
    total = len(raw)
    for row in rows:
        require(type(row) is dict and set(row) == {'name', 'size_bytes', 'sha256'}, 'packet member shape')
        name = row['name']
        require(type(name) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*', name) and name != 'manifest.json' and name not in seen, 'flat unique packet member required')
        seen.add(name)
        require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= MAX_FILE, 'source size bound')
        total += row['size_bytes']
        require(total <= MAX_TOTAL, 'aggregate packet source bound')
        data = bounded_bytes(root / name)
        require(len(data) == row['size_bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], 'packet source differs: ' + name)
    require(REQUIRED <= seen, 'complete formal administrative closure required')
    return document


def activate_packet(expected_sha256):
    require(os.getuid() == os.geteuid() == 1000, 'trusted owner credentials required')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'stand boot changed')
    here = Path(__file__).resolve().parent
    verify_packet(here, expected_sha256)
    original = EVIDENCE / 'offline-suffix-operators-1'
    require(hashlib.sha256(bounded_bytes(original / 'validate_suffix.py')).hexdigest() == BOOTSTRAP_SHA, 'original qualified bootstrap changed')
    sys.path.insert(0, str(original))
    bootstrap = importlib.import_module('validate_suffix')
    require(Path(bootstrap.__file__).resolve() == original / 'validate_suffix.py', 'bootstrap import path differs')
    config = bootstrap.config(EVIDENCE / 'offline-suffix-preparation-1/inputs/analysis-config.json', CONFIG_SHA)
    # Authenticate the original source/policy/module closure and original D242
    # adapter. New formal commands perform their own current journal admission.
    bootstrap.modules(config)
    sys.path.insert(0, str(here))
    cli = importlib.import_module('stage17_operational_cli_v20')
    for module in (cli, cli.controller, cli.controller.handoff):
        require(Path(module.__file__).resolve().parent == here, 'administrative module loaded outside bound packet')
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


if __name__ == '__main__':
    raise SystemExit(main())
