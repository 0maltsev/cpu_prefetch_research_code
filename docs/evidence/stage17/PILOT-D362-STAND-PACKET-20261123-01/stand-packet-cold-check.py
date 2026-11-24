from pathlib import Path
import sys,json,time,hashlib,ctypes
sys.path.insert(0,str(Path.cwd()/'tools'))
import stage17_s180_plan_prepare_v1 as planning
import stage17_s180_resource_plan_v1 as bounds
import stage17_s180_source_author_v1 as author
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as archive
out=Path('build/stage17-s180-operator-integration-prep')
sizing=archive.parse_json(Path(author.SIZING_PATH).read_bytes())
old=archive.parse_json(Path('docs/evidence/stage17/PILOT-D334-COMPACTION-INTEGRATION-20261123-01/d333-sizing-v3.json').read_bytes())
assert old['storage']['implementation_profile_sha256']!=sizing['storage']['implementation_profile_sha256']
old['storage']['implementation_profile_sha256']=sizing['storage']['implementation_profile_sha256']
assert old==sizing
worker=runtime.ImageBinding(Path('build/stage17-s180-release-34247ce/cpu_prefetch_runner').resolve(),6151832,'7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc')
started=time.monotonic_ns();report=planning.native_layouts(sizing,worker=worker,deadline_ns=started+120*10**9)
lib=ctypes.CDLL(str(Path('build/stage17-s180-stand-runtime-prefix/usr/lib/libzstd.so.1.5.7').resolve()))
lib.ZSTD_compressBound.argtypes=[ctypes.c_size_t];lib.ZSTD_compressBound.restype=ctypes.c_size_t
bounded,envelope=bounds.bound_packet(sizing,report,compress_bound=lib.ZSTD_compressBound)
assert bounded==sizing
source=author.requirements(sizing)
process=bounds.process_envelope(sizing,report,envelope);timing=bounds.time_envelope(sizing,report)
for name,value in [('stand-packet-native-description.json',report),('stand-packet-resource-envelope.json',envelope),('stand-packet-process-envelope.json',process),('stand-packet-time-envelope.json',timing)]:
 with (out/name).open('xb') as f:f.write(archive.canonical(value))
print(json.dumps(dict(status='COLD_STAND_RUNTIME_PACKET_PASS',elapsed_ns=time.monotonic_ns()-started,sizing_sha256=planning.sha(sizing),archive_profile_sha256=sizing['storage']['implementation_profile_sha256'],only_changed_field='storage.implementation_profile_sha256',native_sha256=worker.sha256,source_bank_upper_bytes=source['source_bank_upper_bytes'],native_source_or_arrays_prepared=False,qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True,indent=2))
