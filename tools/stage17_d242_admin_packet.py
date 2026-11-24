"""Build the separate D242 administrative closure without changing release42."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

OPERATORS = ('render_continuation.py', 'audit_namespaces_v25.py',
             'prepare_launch_inputs.py', 'formal_launch.py', 'register_family.py', 'render_config.py')
SOURCE = '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
BOOTSTRAP = '\nimport stage17_state_journal_v53 as d242\nd242.activate()\n'


def adapt(name, raw):
    text = raw.decode()
    tree = ast.parse(text)
    headers = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == '__future__']
    position = max((node.end_lineno for node in headers), default=0)
    if not position and tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        position = tree.body[0].end_lineno
    lines = text.splitlines(keepends=True)
    lines.insert(position, BOOTSTRAP)
    text = ''.join(lines)
    if name == 'formal_launch.py':
        old = "str(Path(c['repository_root'])/'tools/stage17_operational_cli_v18.py')"
        if text.count(old) != 1:
            raise ValueError('original CLI dispatch differs')
        text = text.replace(old, "str(Path(__file__).resolve().parent/'stage17_operational_cli_v19.py')")
    ast.parse(text)
    return text.encode()


def build(root, destination):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root):
        raise ValueError('administrative source must be clean')
    files = {}
    for name in ('stage17_state_journal_v53.py', 'stage17_operational_cli_v19.py'):
        files[name] = (root/'tools'/name).read_bytes()
    original = root/'docs/evidence/stage17/Q16A-PREFIX-VALIDATION-E25-20261108-01/operators'
    for name in OPERATORS:
        files[name] = adapt(name, (original/name).read_bytes())
    approval = root/'docs/evidence/stage17/D242-OWNER-ACCEPTANCE-20261109-01'
    for name in ('approved-proposal.md', 'owner-acceptance.json'):
        files[name] = (approval/name).read_bytes()
    files['decision.md'] = (root/'docs/decisions/0242-stage17-e25-transition-authority-recovery-proposal.md').read_bytes()
    manifest = dict(schema_version='cpu-prefetch-stage17-d242-admin-manifest/1',
        administrative_source_revision=revision, qualified_source_revision=SOURCE,
        files=[dict(name=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
               for name, raw in sorted(files.items())], execution_authority=False)
    destination.mkdir()
    for name, raw in files.items():
        with (destination/name).open('xb') as stream:
            stream.write(raw)
    (destination/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, separators=(',', ':'))+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(), args.destination.resolve()), sort_keys=True))
