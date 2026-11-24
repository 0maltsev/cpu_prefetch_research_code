"""Add metadata-only descriptive admission bindings; rewrite no predecessor."""
import argparse
import copy
import json
from pathlib import Path
import sys

import author_stage17_policy_v63 as previous
import stage17_semantic_verifier_v65 as verifier


def render(root):
    root = root.resolve(); old = json.loads((root/verifier.predecessor.POLICY_PATH).read_bytes())
    policy = copy.deepcopy(old); base = previous._BASE
    roots = list(dict.fromkeys((*old['runtime_import_roots'],*verifier.NEW_ROOTS)))
    policy.update(schema_version='cpu-prefetch-stage17-operational-evidence-admission-policy/65',
        policy_id='STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v65',policy_version='65',
        predecessor=base.binding(root,verifier.predecessor.POLICY_PATH.as_posix()),
        predecessor_status='SUPERSEDED_SCOPED_DESCRIPTIVE_ADMISSION',runtime_import_roots=roots,
        runtime_closure={Path(p).stem:base.binding(root,p) for p in sorted(verifier.discover_python_closure(root,roots))},
        entries=[dict(input_id=k,status='IMPLEMENTED',verifier_id=verifier.VERIFIER_ID,verifier_version='65') for k in verifier.INPUT_IDS])
    for path in sorted(set((*verifier.SUCCESSOR_BINDINGS,*verifier.FORMAL_DECISIONS))):
        policy['bindings'][path.replace('/','__').replace('.','_')] = base.binding(root,path)
    verifier.verify_policy_v65(root=root,policy=policy,**{k:policy[k] for k in
        ('graph_sha256','catalog_sha256','genesis_record_sha256','resolution_schema_sha256')})
    return policy


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--check',action='store_true')
    a = p.parse_args(); raw = previous._BASE.canonical(render(a.root))
    if a.check:
        if (a.root/verifier.POLICY_PATH).read_bytes() != raw: return 1
        print('stage17-policy-v65: PASS'); return 0
    sys.stdout.buffer.write(raw); return 0


if __name__ == '__main__': raise SystemExit(main())
