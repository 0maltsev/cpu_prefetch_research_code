"""Explicit D256 administrative command; no experimental execution entry point."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/admission-root')
POLICY = 'config/stage17/stage17-operational-evidence-admission-policy-v59.json'
POLICY_SHA = '53a030f3caf90fb426ea1a95cc2842cb4e2281375fec7952a4945f5e2ad07f6e'


def authenticate(root, admin, manifest_sha256):
    """Pin qualified and explicitly separate administrative bytes before import."""
    def read(path):
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('canonical nonsymlink file required')
        return path.read_bytes()
    raw = read(root/POLICY)
    if hashlib.sha256(raw).hexdigest() != POLICY_SHA:
        raise ValueError('qualified policy differs')
    policy = json.loads(raw)
    for group in ('bindings','runtime_closure'):
        for row in policy[group].values():
            payload = read(root/row['path'])
            if len(payload) != row['size_bytes'] or hashlib.sha256(payload).hexdigest() != row['sha256']:
                raise ValueError('qualified source differs: '+row['path'])
    payload = read(admin/'manifest.json')
    if hashlib.sha256(payload).hexdigest() != manifest_sha256:
        raise ValueError('administrative manifest differs')
    manifest = json.loads(payload)
    names = set()
    for row in manifest['files']:
        name = row['name']
        if Path(name).name != name or name in names:
            raise ValueError('invalid or duplicate administrative member')
        names.add(name)
        raw = read(admin/name)
        if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('administrative source differs: '+name)
    if {p.name for p in admin.iterdir()} != names | {'manifest.json'}:
        raise ValueError('expanded administrative directory')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check','author','commit','validate'))
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--pilot-archive', type=Path, required=True)
    parser.add_argument('--pilot-sidecar', type=Path, required=True)
    args = parser.parse_args()
    admin = Path(__file__).resolve().parent
    authenticate(ROOT, admin, args.manifest_sha256)
    sys.path.insert(0, str(ROOT/'tools'))
    sys.path.insert(1, str(admin))
    import stage17_state_journal_v55 as recovery
    if args.command == 'check':
        result = recovery.original_validation(args.pilot_archive, args.pilot_sidecar)
        recovery.template(result.resolutions)
        output = dict(status='PASS',current_state=result.current_state,resolutions=result.resolution_count)
    elif args.command == 'validate':
        import stage17_daycap_administration_v2 as administration
        cli = administration.make_cli()
        result = cli._validation(ROOT,recovery.EVIDENCE,args.pilot_archive,args.pilot_sidecar)
        output = dict(status='PASS',current_state=result.current_state,resolutions=result.resolution_count,
            transitions=result.transition_count,pilot_ready=result.pilot_ready,
            latest_journal_sha256=result.latest_journal_sha256)
    else:
        operation = recovery.author if args.command == 'author' else recovery.commit
        output = operation(args.pilot_archive,args.pilot_sidecar)
    print(json.dumps(dict(output,execution_authority=False,phase18_authority=False),sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
