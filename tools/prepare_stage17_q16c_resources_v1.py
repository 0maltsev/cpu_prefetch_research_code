"""D274 pure native Q16c sizing from retained originals; no experiment authority.

The caller authenticates this cold packet, its config and the exact standalone
query binary/library provenance. Historical hardware prestate is an input for
software arithmetic only; current hardware qualification remains separate.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import stage17_q16c_plan_builder_v1 as builder
import stage17_formal_archive_v1 as archive
import stage17_fixed_action_executor_v2 as snapshots
import stage17_q16a_continuation_admission_v1 as metadata


def require(ok,message):
    if not ok:raise ValueError('Q16c sizing: '+message)


def read(binding,maximum=32*1024**2):
    path=Path(binding['path']);size=binding['size_bytes']
    require(path.is_absolute() and path.resolve(strict=True)==path and type(size) is int and 0<=size<=maximum,'canonical finite bound source')
    with archive.open_regular(path) as f:
        before=archive.file_stamp(os.fstat(f.fileno()));raw=f.read(size+1)
        require(before==archive.file_stamp(os.fstat(f.fileno()))==archive.file_stamp(path.lstat()),'bound source changed during read')
    require(len(raw)==size and hashlib.sha256(raw).hexdigest()==binding['sha256'],'bound source size/hash differs')
    return raw


def save(path,value):
    raw=archive.canonical(value)
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


@contextlib.contextmanager
def source_pair(bindings):
    with contextlib.ExitStack() as stack:
        rows=[]
        for source in bindings:
            require(set(source)=={'artifact_id','path','size_bytes','sha256'},'exact original binary binding')
            raw=read({k:source[k] for k in ('path','size_bytes','sha256')},128*1024**2)
            pinned=snapshots._pin_generated(raw,'Q16C_SOFTWARE_SIZING_SOURCE')
            stack.callback(pinned.close)
            fd=os.open('/proc/self/fd/'+str(pinned.descriptor),os.O_RDONLY|os.O_CLOEXEC);stack.callback(os.close,fd)
            rows.append(dict(artifact_id=source['artifact_id'],size_bytes=len(raw),sha256=source['sha256'],descriptor=fd))
        yield rows


def sizing_source_context(sources,deadline_ns):
    require(len(sources)==2,'two original phase sources required')
    sizes=[s['size_bytes'] for s in sources]
    # Match D271: owned arrays plus the largest simultaneous decode copy and
    # its finite I/O block. The pure descriptor query uses this same loader.
    return dict(bindings=sources,maximum_vector_bytes=sum(sizes)+max(sizes)+8192,
                deadline_monotonic_ns=deadline_ns)


def prepare(configuration):
    require(set(configuration)=={'schema_version','bundle_root','identities','source_completion','parent_plan','historical_request',
        'query_binary','loader_path','output_root','cpuset_prefix','execution_authority','phase18_authority'},'closed sizing configuration')
    require(configuration['schema_version']=='cpu-prefetch-stage17-q16c-sizing-configuration/1'
        and configuration['execution_authority'] is False and configuration['phase18_authority'] is False,'software sizing scope')
    started=time.monotonic_ns();deadline=started+900*10**9
    out=Path(configuration['output_root']);require(out.is_absolute() and out.parent.resolve(strict=True)==out.parent and not out.exists(),'exclusive canonical output')
    identities=metadata._json(read(configuration['identities']));completion=metadata._json(read(configuration['source_completion']))
    source_record=metadata._json(read(completion['manifest']))
    require(source_record['all_workers_reaped'] is True and len(source_record['sources'])==360,'complete original source preparation')
    require(source_record['source_setup']['sha256']==hashlib.sha256(archive.canonical(identities['source_setup'])).hexdigest(),'exact audited original setup')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==source_record['boot_id'],'same actual boot')
    parent=metadata._json(read(configuration['parent_plan']));old_request=metadata._json(read(configuration['historical_request']))
    hardware=old_request['action_inputs']['hardware_control'];q16a=old_request['action_inputs']['prerequisite_bindings']['q16a_validation']
    rows=builder.capture_inputs(parent,identities,source_record['sources'],cpuset_prefix=configuration['cpuset_prefix'],
                                q16a_handoff_sha256=q16a['sha256'])
    query=Path(configuration['query_binary']['path']);read(configuration['query_binary'])
    bundle=Path(configuration['bundle_root']);require(str(bundle)==identities['source_setup']['bundle_root'],'actual frozen source bundle')
    profile_path=bundle/'config/stage17/formal-archive-implementation-profile-v1.json';profile_raw=profile_path.read_bytes();profile=metadata._json(profile_raw)
    zstd=profile['zstd_library'];require(zstd['location']=='bundle','qualified bundled zstd required')
    compress=builder.bounds.zstd_bounder(bundle/zstd['path'])
    require(hashlib.sha256((bundle/zstd['path']).read_bytes()).hexdigest()==zstd['sha256'],'exact accepted zstd bytes')
    prestate=[dict(cpu=row['cpu'],value=int(row['complete_value_hex'],16)) for row in hardware['prestate']]
    loader=Path(configuration['loader_path']);require(loader.is_absolute() and loader.is_file(),'actual explicit ELF loader required')
    out.mkdir(mode=0o700);(out/'layouts').mkdir();answers=[]
    for ordinal,item in enumerate(rows):
        require(time.monotonic_ns()<deadline,'whole software-sizing deadline')
        bindings=[dict(artifact_id=s['source_artifact']['artifact_id'],**source_record['sources'][2*ordinal+i]['binary'])
                  for i,s in enumerate(item['capture']['schedules'])]
        with source_pair(bindings) as sources:
            context=sizing_source_context(sources,min(deadline,time.monotonic_ns()+30*10**9))
            payload=dict(**item,hardware_prestate=prestate,schedule_source_context=context)
            path=out/'layouts'/f'capture-{ordinal:03d}.input.json';save(path,payload)
            result=subprocess.run([str(loader),'--library-path',str(bundle/'release/runtime/lib'),str(query),'--describe',str(path)],pass_fds=tuple(s['descriptor'] for s in sources),
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=35,check=False)
            (out/'layouts'/f'capture-{ordinal:03d}.stderr').write_bytes(result.stderr)
            require(result.returncode==0,'actual native description failed: '+result.stderr.decode(errors='replace')[:2048])
            answer=metadata._json(result.stdout);answers.append(answer);save(out/'layouts'/f'capture-{ordinal:03d}.layout.json',answer)
        print('SOFTWARE_NATIVE_LAYOUT',ordinal+1,180,flush=True)
    plan,proof=builder.assemble(parent,identities,rows,answers,profile_sha256=hashlib.sha256(profile_raw).hexdigest(),compress_bound=compress)
    final=save(out/'plan-preview.json',plan);sizing=save(out/'native-sizing-proof.json',proof)
    require(time.monotonic_ns()<deadline,'software-sizing completion deadline')
    return save(out/'complete.json',dict(schema_version='cpu-prefetch-stage17-q16c-software-sizing-completion/1',
        status='ALL_180_ACTUAL_ORIGINAL_SOURCE_LAYOUTS_VERIFIED',plan_preview=final,sizing_proof=sizing,
        archive_profile_binding_is_provisional=True,hardware_prestate_scope='HISTORICAL_REQUEST_INPUT_FOR_SOFTWARE_SIZING_ONLY',
        current_hardware_verified=False,elapsed_ns=time.monotonic_ns()-started,execution_authority=False,phase18_authority=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--configuration',type=Path,required=True)
    parser.add_argument('--configuration-sha256',required=True);args=parser.parse_args()
    raw=read(dict(path=str(args.configuration),size_bytes=args.configuration.stat().st_size,sha256=args.configuration_sha256),131072)
    result=prepare(metadata._json(raw));print(json.dumps(result),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
