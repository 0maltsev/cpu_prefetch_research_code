"""Native queue geometry provenance for D240's two preserved sources.

The fixed retained query calls storage_requirements only. Cache-line values
come from admitted EXT004 evidence. No performance/hardware experiment runs.
"""
from __future__ import annotations
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess

import stage17_q16a_continuation_admission_v1 as admission

QUERY_SHA='5a881f2c14960ea32cc3ca9e39222f109344ee480752a5cc89a919012b39cf84'
QUERY_SOURCE_SHA='5425e2e00226565beb225eb3c5ed06a69ac392a80ba81544ce9c91d6528595f2'
OUTPUT_SHA='ef00e2b07a2dc0ad3d6032caf646320d090d147461c81e93cdadbea435caf9ce'
require,same=admission.require,admission.same


def layout_records(native,original,suffix,cache_line,output_binding):
    same(native['schema_version'],'software-native-ring-slot-geometry/1','native output version')
    same(native['source_revision'],original['source_revision'],'original native output source')
    same(native['source_dirty'],False,'native output clean source')
    same(native['api'],'RingSpscQueue::storage_requirements','native query API')
    same(native['hardware_observation'],False,'software-only query')
    same(native['execution_authority'],False,'query authority')
    require(type(native['records']) is list and len(native['records'])==6,'six native contexts')
    records=[]
    for i,row in enumerate(native['records']):
        same(row['context_ordinal'],i,'native context order')
        same(row['cache_line_bytes'],cache_line,'admitted hardware cache line')
        for plan in (original,suffix):
            for item in plan['captures']:
                c=item['capture']
                if c['context_ordinal']%6==i:
                    same(c['geometry']['capacity'],row['capacity'],'native capacity against original plan')
                    same(c['geometry']['cache_line_bytes'],cache_line,'prospective cache line against admission')
        require(type(row['slot_storage_bytes']) is int and row['slot_storage_bytes']>0,'actual native slot bytes required')
        records.append(dict(context_ordinal=i,capacity=row['capacity'],cache_line_bytes=cache_line,
            slot_storage_bytes=row['slot_storage_bytes'],source_binding=dict(artifact_id='D240-RETAINED-NATIVE-GEOMETRY',
                size_bytes=output_binding['size_bytes'],sha256=output_binding['sha256'])))
    admission.calibration._geometry(records,original)
    admission.calibration._geometry(records,suffix)
    return records


def verify(*,prepared,suffix_plan,transport_binding,platform_binding,reader):
    manifest=reader.document(transport_binding);root=Path(transport_binding['path']).parent
    def transported(name):
        rows=[r for r in manifest['files'] if r['name']==name];require(len(rows)==1,'one transported original file')
        row=rows[0];require(Path(name).name==name,'flat transport name')
        b=dict(path=str(root/name),size_bytes=row['size_bytes'],sha256=row['sha256'])
        return reader.read(b),b,row
    source,_,_=transported('query.cpp');same(hashlib.sha256(source).hexdigest(),QUERY_SOURCE_SHA,'reviewed cold-query source')
    binary,binary_binding,binary_row=transported('query');same(binary_binding['sha256'],QUERY_SHA,'original fixed query image')
    output,output_binding,output_row=transported('native-output.json');same(output_binding['sha256'],OUTPUT_SHA,'original query output')
    provenance,provenance_binding,_=transported('query-provenance.json');provenance=admission._json(provenance)
    sizing,sizing_binding,_=transported('original-sizing-provenance.json');sizing=admission._json(sizing)
    same(provenance['binary'],dict(path=binary_row['original_path'],size_bytes=len(binary),sha256=QUERY_SHA),'original query binary provenance')
    same(provenance['output'],dict(path=output_row['original_path'],size_bytes=len(output),sha256=OUTPUT_SHA),'original query output provenance')
    same(provenance['original_sizer_provenance']['sha256'],sizing_binding['sha256'],'original linked-library provenance')
    parent=reader.document(suffix_plan['continuation']['parent_plan'])
    compatibility=reader.document(suffix_plan['continuation']['compatibility_manifest'])
    context=prepared.validation.resolutions['S17-EXT-006'].semantic_context
    same(compatibility['original']['worker']['sha256'],admission.ORIGINAL_WORKER_SHA,'original qualified worker')
    same(provenance['qualified_worker']['sha256'],admission.ORIGINAL_WORKER_SHA,'native query worker association')
    same(provenance['source_revision'],parent['source_revision'],'native provenance source')
    same(compatibility['continuation']['bundle_root'],context['archive_bundle_root'],'current admitted bundle')
    same(compatibility['continuation']['bundle_inventory']['sha256'],context['inventory_sha256'],'current admitted inventory')
    same(compatibility['original']['bundle_inventory']['sha256'],admission.ORIGINAL_INVENTORY_SHA,'original qualified inventory')
    inventories={side:admission._inventory(reader.document(compatibility[side]['bundle_inventory'])) for side in ('original','continuation')}
    def member(side,name):
        row=inventories[side][name]
        b=dict(path=str(Path(compatibility[side]['bundle_root'])/name),size_bytes=row['size_bytes'],sha256=row['sha256'])
        reader.read(b);return b
    queue={side:member(side,'release/lib/libcpu_prefetch_queue.a') for side in inventories}
    same({k:queue['original'][k] for k in ('size_bytes','sha256')},{k:queue['continuation'][k] for k in ('size_bytes','sha256')},'identical native queue library')
    for row in provenance['libraries']:
        original=member('original','release/lib/'+Path(row['path']).name)
        same([row['size_bytes'],row['sha256']],[original['size_bytes'],original['sha256']],'query linked original library')
        require(any(b==row for b in sizing['input_bindings']),'library absent from original qualified sizing inputs')
    dependencies,dependency_binding,_=transported('query-dependencies.d')
    dependency_names={x.split('/include/cpu_prefetch/',1)[1] for x in dependencies.decode().replace('\\\n',' ').split()
                      if '/include/cpu_prefetch/' in x}
    same(sorted(dependency_names),['foundation/repository_info.hpp','queue/common.hpp','queue/ring_spsc.hpp'],'reviewed native query header closure')
    headers=[]
    for row in sizing['input_bindings']:
        marker='/include/cpu_prefetch/'
        if marker not in row['path']:continue
        if row['path'].split(marker,1)[1] not in dependency_names:continue
        name='include/cpu_prefetch/'+row['path'].split(marker,1)[1]
        old=member('original',name);new=member('continuation',name)
        same([row['size_bytes'],row['sha256']],[old['size_bytes'],old['sha256']],'query original header input')
        same([new['size_bytes'],new['sha256']],[old['size_bytes'],old['sha256']],'unchanged query header across sources')
        headers.append(name)
    require('include/cpu_prefetch/queue/ring_spsc.hpp' in headers,'queue API header provenance')
    platform=reader.document(platform_binding)
    expected=prepared.validation.resolutions['S17-EXT-004'].semantic_context['pilot_platform_measurements']['platform_manifest_sha256']
    same(platform_binding['sha256'],expected,'admitted actual platform manifest')
    line=platform['cpu']['cache_line_bytes'];require(type(line) is int and line>0,'observed cache line required')
    native=admission._json(output)
    records=layout_records(native,parent,suffix_plan,line,output_binding)
    fd=os.memfd_create('retained-queue-layout-query',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        with os.fdopen(os.dup(fd),'wb') as f:f.write(binary);f.flush()
        seals=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,seals)
        argv=['/proc/self/fd/'+str(fd),str(line),*[str(r['capacity']) for r in records]]
        run=subprocess.run(argv,pass_fds=(fd,),capture_output=True,timeout=15,check=True,
            env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
        require(run.stdout==output,'native geometry reproduction differs')
        require(not run.stderr,'native query emitted an error')
    finally:os.close(fd)
    reader.finish()
    return dict(status='VERIFIED_SHARED_NATIVE_QUEUE_GEOMETRY',records=records,native_output=output_binding,native_provenance=provenance_binding,
        original_sizing_provenance=sizing_binding,query_binary=binary_binding,query_dependency_file=dependency_binding,shared_queue_libraries=queue,verified_headers=headers,
        platform_manifest=platform_binding,cache_line_bytes=line,original_source_revision=parent['source_revision'],
        continuation_source_revision=suffix_plan['source_revision'],native_query_hardware_observation=False,performance_measurement=False,
        reproduced_output_sha256=hashlib.sha256(run.stdout).hexdigest(),execution_authority=False,phase18_authority=False)
