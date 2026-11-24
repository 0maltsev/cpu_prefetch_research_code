"""Verify the completed original-byte second copy; grants no experiment authority."""
import datetime
import hashlib
import json
import os
from pathlib import Path

prep = Path(__file__).resolve().parent
manifest_path = prep / 'stopped-discovery-inventory.json'
manifest = json.loads(manifest_path.read_text())
root = prep.parent / 'stage17-discovery-v19-copy1/discovery-output-1'
files = [f for f in manifest['files'] if not f['path'].startswith('operator/')]
assert {f['path'] for f in files} == {p.name for p in root.iterdir()}
records = []
for f in files:
    path = root / f['path']
    assert path.is_file() and not path.is_symlink()
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    assert (before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    assert before.st_size == f['size_bytes'] and digest == f['sha256'], f['path']
    records.append({k: f[k] for k in ('path', 'size_bytes', 'sha256')})
report = dict(status='PASS_ORIGINAL_BYTE_SECOND_COPY', observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    stand_root=manifest['root'], pc_root=str(root), compression=False,
    stand_manifest_observed_at_utc=manifest['observed_at_utc'],
    stand_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    files=records, total_bytes=sum(f['size_bytes'] for f in files),
    execution_authority=False, scientific_validity_not_implied=True)
with (prep / 'stopped-copy-verification.json').open('x') as out:
    json.dump(report, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
print(json.dumps({'status': report['status'], 'files': len(files), 'bytes': report['total_bytes']}))
