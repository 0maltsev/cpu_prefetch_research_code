from pathlib import Path
import ctypes,hashlib,json,time
import stage17_s180_resource_plan_v1 as r
import stage17_s180_environment_v1 as environment
import stage17_formal_archive_runtime_v1 as runtime
root=Path('build/stage17-s180-operator-prep')
blueprint=json.loads(Path('config/stage17/d310-s180-blueprint-v1.json').read_bytes())
identities=json.loads(Path('config/stage17/d310-s180-identities-v1.json').read_bytes())
hardware=json.loads(Path('docs/evidence/stage17/PILOT-D326-RESOURCES-20261122-01/stand-hardware-readonly.json').read_bytes())
control=Path('docs/evidence/stage17/PILOT-D326-RESOURCES-20261122-01/original-control-plan.json').read_bytes()
worker=Path('build/stage17-s180-release-34247ce/cpu_prefetch_runner').resolve();raw=worker.read_bytes()
image=runtime.ImageBinding(worker,len(raw),hashlib.sha256(raw).hexdigest())
assert image.sha256=='7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc'
initial=r.make_ceiling_packet(blueprint=blueprint,prospective_identities=identities,historical_plan_bytes=control,
    hardware_observation=hardware,source_revision=environment.NATIVE_REVISION,
    requested_cpuset_prefix=str(environment.CG),recovery_ns=60*10**9)
first=r.planning.native_layouts(initial,worker=image,deadline_ns=time.monotonic_ns()+60*10**9)
libpath=Path('build/ext007-runtime-20261101/root/usr/lib/libzstd.so.1.5.7').resolve()
zstd=ctypes.CDLL(str(libpath));zstd.ZSTD_versionNumber.restype=ctypes.c_uint
assert zstd.ZSTD_versionNumber()==10507
zstd.ZSTD_compressBound.argtypes=[ctypes.c_size_t];zstd.ZSTD_compressBound.restype=ctypes.c_size_t
bounded,envelope=r.bound_packet(initial,first,compress_bound=zstd.ZSTD_compressBound)
final=r.planning.native_layouts(bounded,worker=image,deadline_ns=time.monotonic_ns()+60*10**9)
for name,obj in [('managed-sizing-v2.json',bounded),('managed-native-description-v2.json',final),
    ('managed-resource-envelope-v2.json',envelope),('managed-process-envelope-v2.json',r.process_envelope(bounded,final,envelope)),
    ('managed-time-envelope-v2.json',r.time_envelope(bounded,final))]:
    (root/name).write_bytes(r.archive.canonical(obj))
summary=dict(requested_partition_path=str(environment.CG),native_sha256=image.sha256,
    bounded_sizing_sha256=r.planning.sha(bounded),archive_upper_bytes=envelope['archive_family_upper_bytes'],
    control_plan_sha256=hashlib.sha256(control).hexdigest(),zstd_version=10507,zstd_library_sha256=hashlib.sha256(libpath.read_bytes()).hexdigest(),
    hardware_observation_is_prior_unqualified_reference=True,source_count_basis='PROSPECTIVE_UPPER_CEILINGS',
    operational_window_started=False,source_generation_performed=False,resource_admission_performed=False,execution_authority=False)
(root/'managed-packet-summary.json').write_bytes(r.archive.canonical(summary))
print(json.dumps(summary))
