from pathlib import Path
from dataclasses import replace
import os,sys,tarfile,hashlib,json,time,resource,shutil,datetime
base=Path('/tmp/cpu-prefetch-s180-metadata-software-1');base.mkdir(mode=0o700)
transport=Path('/tmp/cpu-prefetch-s180-metadata-software-tests-1.tar')
assert transport.stat().st_size==3880960 and hashlib.sha256(transport.read_bytes()).hexdigest()=='f6822acbffaff13a9d8fdd981a9d9fe0a618bc4b0442e8683dfe8ecbd7ffb9c8'
with tarfile.open(transport) as t:
 members=t.getmembers();assert all(m.isdir() or m.isfile() for m in members)
 t.extractall(base,filter='data')
common=Path('/opt/cpu-prefetch-s180-common-0919b87-1');component=Path('/home/omaltsev/stage17-owner-evidence/s180-archive-component-877271c-stand-1')
(base/'tools').symlink_to(common/'tools',target_is_directory=True)
(base/'config').symlink_to(common/'config',target_is_directory=True)
(base/'build').mkdir(mode=0o700)
sys.path[:0]=[str(base/'tests'),str(base/'tools')]
os.environ['STAGE17_TEST_ZSTD_LIBRARY']=str(component/'release/runtime/lib/libzstd.so.1')
os.sched_setaffinity(0,{3});assert os.sched_getaffinity(0)=={3}
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,64*1024**3))
import test_stage17_s180_family_analysis_v1 as originals
import test_stage17_s180_family_validation_v1 as families
import stage17_s180_family_analysis_v1 as analysis
import stage17_formal_archive_v1 as archive
encoder=component/'release/bin/cpu_prefetch_stage17_archive_encoder'
assert encoder.stat().st_size==291424 and hashlib.sha256(encoder.read_bytes()).hexdigest()=='c34056b6059c3936499fca3156b981ecfe7903b80153a917f76e9193987988ea'
assert not Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/s180-d310-1').exists()
started=time.monotonic_ns();fixture=originals.OriginalTests();fixture.encoder=encoder
try:
 fixture.setUp();prepared=time.monotonic_ns();owner=fixture.software_phase()
 decoder=archive.DecodeLimits(32768,4*1024**2,4*1024**2,8*1024**2,4*1024**2,100,1<<22,fixture.f.deadline)
 with fixture.f.store() as store:
  begin=time.monotonic_ns()
  for i in range(180):
   record=analysis._capture(store,fixture.request,fixture.native,0,fixture.f.profile,decoder,phase_owner=owner)
   assert record['registry_proof']['physical_sha256_verification_pending'] is True
  metadata_ns=time.monotonic_ns()-begin
finally:fixture.doCleanups()
# This metadata-only expansion is not180 scientific validations. Its input
# template is the existing software-only original-byte capture fixture.
begin=time.monotonic_ns();data=families.family_fixture(families.template());family_preparation_ns=time.monotonic_ns()-begin
begin=time.monotonic_ns();encoded=archive.canonical(data);decoded=archive.parse_json(encoded);roundtrip_ns=time.monotonic_ns()-begin
begin=time.monotonic_ns();result=families.v.validate_family(**decoded,deadline_ns=time.monotonic_ns()+120*10**9);family_ns=time.monotonic_ns()-begin
assert result['status']=='PASSED' and result['captures_verified']==180
assert result['original_archive_custody_verified'] is False and result['analysis_supervision_verified'] is False
report=dict(status='SOFTWARE_METADATA_TIMING_PASS',utc=datetime.datetime.now(datetime.UTC).isoformat(),cpu=3,
 fixture_preparation_ns=prepared-started,original_header_receipt_metadata_180_repeated_same_capture_ns=metadata_ns,
 synthetic_family_preparation_ns=family_preparation_ns,synthetic_family_canonical_json_bytes=len(encoded),
 synthetic_family_roundtrip_ns=roundtrip_ns,synthetic_complete_family_consistency_ns=family_ns,
 total_measured_metadata_components_ns=metadata_ns+roundtrip_ns+family_ns,
 fixture_boundaries='EXPLICIT_SOFTWARE_PHASE_AND_SYNTHETIC_NATIVE_PARENT_FAMILY_METADATA',
 original_research_raw_bytes_read=0,scientific_captures_collected=0,source_preparation_performed=False,
 qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False)
# Only generated SOFTWARE fixtures are removed; source packages are untouched.
shutil.rmtree(base);transport.unlink()
print(json.dumps(report,sort_keys=True,indent=2))
