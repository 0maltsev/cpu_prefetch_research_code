"""D282 all180 corrected native sizing checks; no clocks/MSRs/captures."""
import argparse
import json
from pathlib import Path
import subprocess
import time

import prepare_stage17_q16c_resources_v1 as previous
import stage17_q16c_empty_reuse_v1 as reuse


def run(c):
    previous.require(c['execution_authority'] is False and c['phase18_authority'] is False,
        'software-only sizing')
    plan = json.loads(previous.read(c['plan'])); proof = json.loads(previous.read(c['source_reuse']))
    reuse.inspect(proof, plan)
    record = json.loads(previous.read(c['source_manifest']))
    previous.require(len(record['sources']) == 360 and record['all_workers_reaped'] is True,
        'complete original bank')
    request = json.loads(previous.read(proof['original_request']))
    prestate = [dict(cpu=r['cpu'], value=int(r['complete_value_hex'],16))
        for r in request['action_inputs']['hardware_control']['prestate']]
    previous.read(c['query']); query = Path(c['query']['path'])
    bundle = Path(c['bundle_root']); loader = Path(c['loader'])
    previous.require(bundle.is_dir() and loader.is_file(), 'actual corrected bundle and explicit loader')
    out = Path(c['output_root']); out.mkdir(mode=0o700); (out/'layouts').mkdir()
    started = time.monotonic_ns(); deadline = started+900*10**9; answers = []
    for ordinal, item in enumerate(plan['captures']):
        previous.require(time.monotonic_ns()<deadline, 'finite complete sizing deadline')
        bindings = [dict(artifact_id=s['source_artifact']['artifact_id'],
            **record['sources'][2*ordinal+i]['binary']) for i,s in enumerate(item['capture']['schedules'])]
        with previous.source_pair(bindings) as sources:
            payload = {k:item[k] for k in ('capture','resources','monitoring')}
            payload.update(hardware_prestate=prestate,
                schedule_source_context=previous.sizing_source_context(sources,min(deadline,time.monotonic_ns()+30*10**9)))
            inp = out/'layouts'/f'{ordinal:03d}.input.json'; previous.save(inp,payload)
            cmd = [str(loader),'--library-path',str(bundle/'release/runtime/lib'),str(query),'--verify-declared',str(inp)]
            r = subprocess.run(cmd,pass_fds=tuple(s['descriptor'] for s in sources),stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=35)
            (out/'layouts'/f'{ordinal:03d}.stderr').write_bytes(r.stderr)
            previous.require(r.returncode==0, 'corrected native sizing rejected ordinal '+str(ordinal)+': '+r.stderr.decode()[:2048])
            answer = json.loads(r.stdout)
            previous.require(answer['source_revision']==reuse.SOURCE and answer['source_dirty'] is False
                and answer['declared_layout_rechecked'] is True, 'actual corrected query provenance')
            previous.save(out/'layouts'/f'{ordinal:03d}.layout.json',answer); answers.append(answer)
        print(json.dumps(dict(software_layouts_verified=ordinal+1,total=180)),flush=True)
    return previous.save(out/'complete.json',dict(schema_version='cpu-prefetch-stage17-d282-software-sizing/1',
        status='ALL_180_CORRECTED_NATIVE_LAYOUTS_VERIFIED',plan=c['plan'],query=c['query'],layouts=answers,
        source_manifest=c['source_manifest'],elapsed_ns=time.monotonic_ns()-started,
        execution_authority=False,phase18_authority=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--configuration',type=Path,required=True)
    p.add_argument('--configuration-sha256',required=True);a=p.parse_args()
    b=dict(path=str(a.configuration),size_bytes=a.configuration.stat().st_size,sha256=a.configuration_sha256)
    print(json.dumps(run(json.loads(previous.read(b)))),flush=True)
