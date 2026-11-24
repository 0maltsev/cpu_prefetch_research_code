#!/usr/bin/env python3
"""Copy a bounded qualification metadata closure. No network, commands or captures.

Retains original bytes/relative locators for prepare_r3.read_snapshot. Q15 *_RAW
roles here are small qualification summaries, never observation/event streams.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from author_fresh_qualification_records import read, write, require, utc

SEEDS = ('release_contract', 'stand_anchor', 'trust_anchor', 'qualification_manifest',
         'write_manifest', 'platform_facts', 'platform_inventory', 'q15w_inputs')
DERIVED = {'platform_manifest':('qualification_manifest','PLATFORM_MANIFEST'),
           'q15r_output':('qualification_manifest','Q15_R_READ_ONLY_PRESTATE'),
           'q15w_request':('write_manifest','Q15_W_REQUEST'),
           'q15w_result':('write_manifest','Q15_W_RESULT')}
KEYS = set(SEEDS) | set(DERIVED) | {'resolutions'}
QUALIFICATION_ROLES = {
    'Q15_R_REQUEST','Q15_R_AUTHORIZATION','Q15_R_SIGNATURE','Q15_R_ATTEMPT','Q15_R_RESULT',
    'Q15_R_SESSION_WAITING','Q15_R_READ_ONLY_PRESTATE','Q15_R_ATOMIC_LAYOUT_RAW',
    'Q15_R_ADDRESS_RESIDENCY_RAW','Q15_R_SOFTWARE_PREFETCH_RAW','Q15_R_CPU_MIGRATION_RAW',
    'PLATFORM_MANIFEST','HARDWARE_PREFETCH_QUALIFICATION','PILOT_PLATFORM_MEASUREMENTS',
    'QUALIFICATION_EVIDENCE', 'Q15_W_REQUEST','Q15_W_AUTHORIZATION','Q15_W_SIGNATURE',
    'Q15_W_ATTEMPT','Q15_W_RESULT','Q15_W_COMPLETION','Q15_W_TRANSACTION'}
MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_FILES = 128


def sha(data):
    return hashlib.sha256(data).hexdigest()


def loads(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def local(root, relative):
    require(isinstance(relative, str) and bool(relative), 'missing relative metadata path')
    path = PurePosixPath(relative)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == relative,
            'unsafe metadata locator')
    require(relative.endswith(('.json', '.json.sig')), 'raw/binary/archive input prohibited')
    current = root
    for part in path.parts:
        current = current / part
        require(not current.is_symlink(), 'metadata symlink prohibited')
    require(current.is_file(), 'missing metadata file: ' + relative)
    return current


def payload(root, relative):
    data = read(local(root, relative), maximum=MAX_FILE)
    if relative.endswith('.sig'):
        require(data.startswith(b'-----BEGIN SSH SIGNATURE-----\n'), 'not a public SSH signature')
    else:
        require(isinstance(loads(data), dict), 'metadata must be a JSON object')
    return data


def document(root, relative):
    return loads(payload(root, relative))


def bound(data, expected):
    require(type(expected['size_bytes']) is int and
            (len(data), sha(data)) == (expected['size_bytes'], expected['sha256']),
            'metadata size/SHA256 binding differs')


def make_index(root, seeds):
    require(set(seeds) == set(SEEDS), 'exact eight seed paths required')
    index = dict(seeds)
    for value in seeds.values(): payload(root, value)
    for key, (manifest_key, role) in DERIVED.items():
        manifest = document(root, index[manifest_key])
        found = [a for a in manifest['artifacts'] if a['role'] == role]
        require(len(found) == 1, 'required artifact role missing/duplicated: ' + role)
        index[key] = found[0]['locator']
        bound(payload(root, index[key]), found[0])
    records = {}
    for path in sorted((root / 'records').glob('resolution-*.json')):
        relative = path.relative_to(root).as_posix()
        data = document(root, relative)
        require(data['verification_result'] == 'PASS' and data['input_id'] not in records,
                'nonpassing/duplicate resolution')
        records[data['input_id']] = relative
    expected = [f'S17-EXT-{i:03d}' for i in range(1,7)]
    require(set(records) == set(expected), 'exact admitted EXT001..006 required')
    index['resolutions'] = [records[key] for key in expected]
    return index


def collect(root, index, destination, source_revision):
    root = root.resolve(strict=True)
    require(not destination.exists() and not destination.is_symlink(), 'snapshot output already exists')
    require(set(index) == KEYS and len(index['resolutions']) == 6, 'qualification index field set differs')
    files = {}
    def add(relative, expected=None):
        data = payload(root, relative)
        if expected is not None: bound(data, expected)
        if relative in files:
            require(files[relative] == data, 'source changed during collection')
        else:
            files[relative] = data
        require(len(files) <= MAX_FILES and sum(map(len, files.values())) <= MAX_TOTAL,
                'metadata snapshot budget exceeded')
        return loads(data) if relative.endswith('.json') else None
    docs = {key:add(value) for key,value in index.items() if key != 'resolutions'}
    release = docs['release_contract']
    require(release['source_revision'] == source_revision and len(source_revision) == 40,
            'fresh qualified revision differs')
    require(release['manifest']['bundle_profile'] == 'STAGE17-PILOT-CANDIDATE-BUNDLE-v26',
            'fresh D207 release profile required')
    for key in ('qualification_manifest','write_manifest'):
        manifest = docs[key]
        require(manifest['synthetic_test_only'] is False, 'synthetic qualification cannot be collected')
        for artifact in manifest['artifacts']:
            require(artifact['role'] in QUALIFICATION_ROLES, 'non-qualification/raw-data role prohibited')
            add(artifact['locator'], artifact)
    for key,(manifest_key,role) in DERIVED.items():
        roles = [a for a in docs[manifest_key]['artifacts'] if a['role'] == role]
        require(len(roles) == 1 and roles[0]['locator'] == index[key], 'indexed role differs from manifest')
    records = {}
    for relative in index['resolutions']:
        record = add(relative);number = record['input_id']
        require(number not in records and record['verification_result'] == 'PASS', 'resolution duplicate/nonpass')
        records[number] = record
        matches = 0
        target_key = {'S17-EXT-004':'qualification_manifest','S17-EXT-005':'write_manifest',
                      'S17-EXT-006':'release_contract'}.get(number)
        for entry in record['evidence']:
            if entry['kind'] == 'EXTERNAL_CUSTODY_RECEIPT':
                receipt = add(entry['receipt_path'], dict(size_bytes=entry['receipt_size_bytes'],sha256=entry['receipt_sha256']))
                if target_key and (receipt['artifact_size_bytes'],receipt['artifact_sha256']) == (
                        len(files[index[target_key]]),sha(files[index[target_key]])):
                    require(receipt['verification_result'] == 'PASS', 'custody receipt not passing')
                    matches += 1
            elif entry['kind'] == 'REPOSITORY_FILE':
                add('admission-root/' + entry['path'], entry)
            else:
                raise ValueError('unsupported resolution evidence kind')
        if target_key: require(matches == 1, 'manifest/contract not bound by exact custody receipt')
    require(set(records) == {f'S17-EXT-{i:03d}' for i in range(1,7)}, 'wrong dependency set')
    bound(files[index['stand_anchor']], dict(size_bytes=len(files[index['stand_anchor']]),
          sha256=docs['trust_anchor']['measurements']['stand_anchor_sha256']))
    for key in ('topology_evidence','cache_capacity_evidence'):
        bound(files[index['platform_inventory']], docs['platform_facts'][key]['snapshot'])
    request,result = docs['q15w_request'],docs['q15w_result']
    require(result['terminal_state'] == 'Q15_W_RESTORED_COMPLETE' and result['restoration_verified'] is True
            and result['quarantined'] is False and result['synthetic_test_only'] is False,
            'Q15W not actual restored completion')
    require(result['request_sha256'] == sha(files[index['q15w_request']])
            and request['action_inputs'] == docs['q15w_inputs'], 'Q15W inputs/request mismatch')
    require(docs['q15r_output']['prestate'] == docs['q15w_inputs']['prestate'], 'Q15R/W prestate differs')
    for relative,data in files.items():
        require(payload(root,relative) == data, 'source changed before snapshot publication')
    # Complete validation before creating any output. Never rewrite source bytes.
    destination.mkdir(mode=0o700, parents=True)
    for relative,data in sorted(files.items()):
        target = destination / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write(target,data)
        require(read(target,maximum=MAX_FILE) == data, 'copied metadata readback differs')
    write(destination/'qualification-inputs.json',index)
    inventory = dict(schema_version='cpu-prefetch-d207-qualification-snapshot/1',
        source_root=str(root), source_revision=source_revision, observed_at_utc=utc(),
        scope='R3 input metadata closure only; no event/observation streams, archives, binaries or keys',
        execution_authority=False, files=[dict(path=key,size_bytes=len(data),sha256=sha(data))
            for key,data in sorted(files.items())])
    write(destination/'snapshot-manifest.json',inventory)
    all_files = list(inventory['files'])
    for name in ('qualification-inputs.json','snapshot-manifest.json'):
        data=read(destination/name,maximum=MAX_FILE)
        all_files.append(dict(path=name,size_bytes=len(data),sha256=sha(data)))
    write(destination/'SHA256SUMS',''.join(row['sha256']+'  '+row['path']+'\n'
        for row in sorted(all_files,key=lambda row:row['path'])).encode('ascii'))
    return inventory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='mode',required=True)
    idx=sub.add_parser('index')
    idx.add_argument('--evidence-root',type=Path,required=True)
    for key in SEEDS:idx.add_argument('--'+key.replace('_','-'),required=True)
    idx.add_argument('--output',type=Path,required=True)
    cp=sub.add_parser('collect')
    cp.add_argument('--evidence-root',type=Path,required=True)
    cp.add_argument('--qualification-inputs',type=Path,required=True)
    cp.add_argument('--output-directory',type=Path,required=True)
    cp.add_argument('--source-revision',required=True)
    args=parser.parse_args()
    if args.mode=='index':
        index=make_index(args.evidence_root.resolve(strict=True),{key:getattr(args,key) for key in SEEDS})
        write(args.output,index)
    else:
        result=collect(args.evidence_root,loads(read(args.qualification_inputs,maximum=MAX_FILE)),
                       args.output_directory,args.source_revision)
        print('METADATA_SNAPSHOT_PASS files='+str(len(result['files']))+' execution_authority=false')


if __name__=='__main__':main()
