"""D297 metadata-only correction/rehearsal inputs; never sign or execute a run.

The frozen D295 runtime and failed configuration remain unchanged. This tool
publishes separate inputs for its existing unsigned construction entry point.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

CONFIGURATION_SHA = '3359f96629594f46b7bd4b362a7ae5485c1480c7fb159cf40a5040ef633458d2'
SOURCE = '7b7c263cb850690cf333df0d196b18c875b4a53c'
EVIDENCE = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
ORIGINAL = EVIDENCE.with_name('local-authoring-cpuprefetchv5-29')
RESTORATION_SIZE = 842
RESTORATION_SHA = 'ad2eb45db7d7f8b11ed372a3a76816f551ac7ac0081dcdb6eeacc8d5646dd326'
MAX_BYTES = 32 * 1024**2


def require(value, message):
    if not value:
        raise ValueError('Q16c incident metadata: ' + message)


def read(path):
    path = Path(path)
    require(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)),
            'absolute nonsymlink metadata path')
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_BYTES, 'bounded regular metadata')
        raw = stream.read(MAX_BYTES + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.stat(follow_symlinks=False)),
                'metadata changed during read')
    require(len(raw) == before.st_size, 'complete metadata read')
    return raw


def binding(path):
    raw = read(path)
    return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def bound_bytes(value):
    require(type(value) is dict and set(value) == {'path', 'size_bytes', 'sha256'}, 'closed metadata binding')
    raw = read(value['path'])
    require(len(raw) == value['size_bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256'],
            'metadata binding differs')
    return raw


def corrected_seed(seed, original_root):
    """Select the original incident receipt, never the earlier clock receipt."""
    path = Path(original_root) / 'q16c-continuation-recovery-1/restoration.json'
    receipt = binding(path)
    require((receipt['size_bytes'], receipt['sha256']) == (RESTORATION_SIZE, RESTORATION_SHA),
            'immutable original incident restoration differs')
    value = json.loads(bound_bytes(receipt))
    require(value['verified'] is True and value['errors'] == []
            and value['maintenance_restoration_verified'] is True
            and value['root_restoration_verified'] is True, 'original incident restoration not verified')
    result = copy.deepcopy(seed)
    result['restoration'] = receipt
    return result


def save(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return binding(path)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def prepare(configuration, output_root):
    raw = read(configuration)
    require(hashlib.sha256(raw).hexdigest() == CONFIGURATION_SHA, 'exact stopped D295 configuration required')
    config = json.loads(raw)
    require(config['source_revision'] == SOURCE and config['evidence_root'] == str(EVIDENCE)
            and config['execution_authority'] is False and config['phase18_authority'] is False,
            'original qualified source and evidence scope')
    output_root = Path(output_root)
    require(output_root.parent == EVIDENCE and output_root.name.startswith('d297-software-preparation-'),
            'separate software-only output scope')
    require(not output_root.exists() and not output_root.is_symlink(), 'exclusive rehearsal output')
    old_seed = json.loads(bound_bytes(config['incident_reuse_inputs']))
    new_seed = corrected_seed(old_seed, ORIGINAL)
    # This administrative script changes no candidate bytes. Its full incident
    # contract is exercised separately by the existing unsigned constructor.
    inventory_raw = bound_bytes(config['candidate_inventory'])
    require(json.loads(inventory_raw)['source_revision'] == SOURCE, 'original candidate inventory')
    recovery = json.loads(read(EVIDENCE / 'd295-independent-recovery-1.json'))
    require(recovery['verified'] is True and recovery['errors'] == [], 'stopped attempt recovery required')
    overlay = json.loads(bound_bytes(config['overlay']))
    source_bytes = {}
    for name, expected in overlay['sources'].items():
        require(name.isidentifier(), 'archive source filename')
        source_bytes[name] = bound_bytes(expected)
    output_root.mkdir(mode=0o700)
    packet = output_root / 'packet'
    packet.mkdir(mode=0o700)
    incident = save(output_root / 'incident-reuse-inputs.json', encode(new_seed))
    for name, raw_source in source_bytes.items():
        overlay['sources'][name] = save(packet / (name + '.py'), raw_source)
    overlay_binding = save(packet / 'archive-overlay.json', encode(overlay))
    corrected = dict(config, incident_reuse_inputs=incident, packet_root=str(packet),
                     output_root=str(output_root / 'constructed-output'), overlay=overlay_binding)
    result = save(output_root / 'configuration.json', encode(corrected))
    return dict(status='UNSIGNED_REHEARSAL_INPUTS_ONLY', configuration=result,
                original_configuration_sha256=CONFIGURATION_SHA,
                changed_configuration_fields=['incident_reuse_inputs', 'output_root', 'overlay', 'packet_root'],
                changed_incident_fields=['restoration'], original_restoration=new_seed['restoration'],
                native_source_revision=SOURCE, experiments_started=0, raw_validations_started=0,
                execution_authority=False, phase18_authority=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    require(os.getresuid() == (1000,) * 3 and os.getresgid() == (1000,) * 3 and not os.getgroups(),
            'exact unprivileged evidence owner')
    print(json.dumps(prepare(args.configuration, args.output_root)), flush=True)


if __name__ == '__main__':
    main()
