"""Render fresh D289 policy63/preflight37 without rewriting predecessors."""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys

import author_stage17_policy_v62 as previous
import stage17_semantic_verifier_v63 as verifier
import stage17_read_only_preflight_semantic_verifier_v37 as preflight

_BASE = previous._BASE


def render_preflight(root):
    root = root.resolve()
    policy = json.loads((root/preflight.POLICY_V36_PATH).read_bytes())
    policy.update(schema_version='cpu-prefetch-stage17-read-only-preflight-evidence-admission-policy/37',
        policy_id='STAGE17-READ-ONLY-PREFLIGHT-EVIDENCE-ADMISSION-POLICY-v37', policy_version='37')
    policy['predecessor'].pop('policy_v35')
    policy['predecessor']['policy_v36'] = _BASE.binding(root, preflight.POLICY_V36_PATH)
    policy['implementations'] = {key:_BASE.binding(root,path) for key,path in preflight.IMPLEMENTATION_PATHS.items()}
    return policy


def render(root):
    root = root.resolve()
    historical = json.loads((root/verifier.predecessor.POLICY_PATH).read_bytes())
    policy = copy.deepcopy(historical)
    for group in ('bindings','runtime_closure'):
        for key,value in policy[group].items():
            if value['path'] in verifier.REBIND_PATHS:
                policy[group][key] = _BASE.binding(root,value['path'])
    verifier.audit_inherited_bindings(root, policy, historical)
    roots = list(dict.fromkeys((*historical['runtime_import_roots'],*verifier.NEW_ROOTS)))
    policy.update(schema_version='cpu-prefetch-stage17-operational-evidence-admission-policy/63',
        policy_id='STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v63',policy_version='63',
        predecessor=_BASE.binding(root,verifier.predecessor.POLICY_PATH.as_posix()),runtime_import_roots=roots,
        runtime_closure={pathlib.PurePosixPath(path).stem:_BASE.binding(root,path)
            for path in sorted(verifier.discover_python_closure(root,roots))},
        entries=[dict(input_id=key,status='IMPLEMENTED',verifier_id=verifier.VERIFIER_ID,
                      verifier_version=verifier.VERIFIER_VERSION) for key in verifier.INPUT_IDS])
    for path in sorted(set((*verifier.SUCCESSOR_BINDINGS,*verifier.FORMAL_DECISIONS))):
        policy['bindings'][path.replace('/','__').replace('.','_')] = _BASE.binding(root,path)
    verifier.verify_policy_v63(root=root,policy=policy,**{key:policy[key] for key in (
        'graph_sha256','catalog_sha256','genesis_record_sha256','resolution_schema_sha256')})
    return policy


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);p.add_argument('--preflight',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
    path=preflight.POLICY_PATH if a.preflight else verifier.POLICY_PATH
    raw=_BASE.canonical((render_preflight if a.preflight else render)(a.root))
    if a.check:
        if (a.root/path).read_bytes()!=raw:return 1
        print('stage17-policy-v63: PASS '+str(path));return 0
    sys.stdout.buffer.write(raw);return 0


if __name__=='__main__':raise SystemExit(main())
