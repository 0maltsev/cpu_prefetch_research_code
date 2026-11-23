from pathlib import Path
import ctypes,hashlib,json,time
import stage17_s180_compaction_v1 as compaction
import stage17_s180_resource_plan_v1 as r
import stage17_formal_archive_runtime_v1 as runtime
out=Path('build/stage17-s180-compaction-prep')
prior=Path('docs/evidence/stage17/PILOT-D329-ENVIRONMENT-20261123-01/managed-sizing-v2.json')
sizing=json.loads(prior.read_bytes());before=json.loads(prior.read_bytes())
profile=json.loads(Path('docs/evidence/stage17/PILOT-D330-ARCHIVE-PACKAGE-20261123-01/clean-component-verification.json').read_bytes())
sizing['storage']['implementation_profile_sha256']=profile['archive_profile']['sha256']
sizing=compaction.monitored_plan(sizing)
worker=Path('build/stage17-s180-release-34247ce/cpu_prefetch_runner').resolve();raw=worker.read_bytes()
image=runtime.ImageBinding(worker,len(raw),hashlib.sha256(raw).hexdigest());assert image.sha256==compaction.NATIVE_SHA
first=r.planning.native_layouts(sizing,worker=image,deadline_ns=time.monotonic_ns()+60*10**9)
library=Path('build/ext007-runtime-20261101/root/usr/lib/libzstd.so.1.5.7').resolve()
codec=ctypes.CDLL(str(library));codec.ZSTD_versionNumber.restype=ctypes.c_uint;assert codec.ZSTD_versionNumber()==10507
codec.ZSTD_compressBound.argtypes=[ctypes.c_size_t];codec.ZSTD_compressBound.restype=ctypes.c_size_t
bounded,envelope=r.bound_packet(sizing,first,compress_bound=codec.ZSTD_compressBound)
final=r.planning.native_layouts(bounded,worker=image,deadline_ns=time.monotonic_ns()+60*10**9)
process=r.process_envelope(bounded,final,envelope);timing=r.time_envelope(bounded,final)
assert before['blueprint']==bounded['blueprint']
assert [e['phases'] for e in before['captures']]==[e['phases'] for e in bounded['captures']]
for name,value in [('d333-sizing-v3.json',bounded),('d333-native-description-v3.json',final),
 ('d333-resource-envelope-v3.json',envelope),('d333-process-envelope-v3.json',process),('d333-time-envelope-v3.json',timing)]:
 (out/name).write_bytes(r.archive.canonical(value))
summary=dict(approval_sha256=compaction.APPROVAL_SHA,sizing_plan_sha256=r.planning.sha(bounded),
 native_sha256=image.sha256,archive_upper_bytes=envelope['archive_family_upper_bytes'],
 previous_archive_upper_bytes=584757218120,archive_upper_increase_bytes=envelope['archive_family_upper_bytes']-584757218120,
 conservative_process_page_bytes=process['conservative_total_bytes'],stage_caps_ns=timing['total_declared_stage_caps_ns'],
 external_guard_metadata_bytes=compaction.METADATA_RESERVE_BYTES,external_guard_metadata_inodes=compaction.METADATA_RESERVE_INODES,
 research_settings_and_source_coordinates_unchanged=True,source_count_basis='PROSPECTIVE_UPPER_CEILINGS',
 current_hardware_qualified=False,archive_profile_actual_package_bound=True,archive_profile_stand_qualified=False,
 resource_admission_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False)
(out/'d333-packet-summary.json').write_bytes(r.archive.canonical(summary));print(json.dumps(summary))
