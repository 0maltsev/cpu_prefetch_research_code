from pathlib import Path
from dataclasses import asdict
import sys,json,time,hashlib
common=Path('/opt/cpu-prefetch-s180-common-0919b87-1')
source=Path('/tmp/cpu-prefetch-s180-execution-software-1/stage17_s180_execution_v1.py')
assert hashlib.sha256(source.read_bytes()).hexdigest()=='3e39fe0f3adac07bb112b184c86f7caa0f78218fea2734ccdbb1066b22daaa58'
sys.path[:0]=[str(source.parent),str(common/'tools')]
import stage17_s180_execution_v1 as execution
import stage17_s180_archive_bundle_profile_v1 as package
assert not execution.ROOT.exists()
component=Path('/home/omaltsev/stage17-owner-evidence/s180-archive-component-877271c-stand-1')
profile=package.load_profile(bundle_root=component,runtime_root=Path('/'),expected=execution.archive.PhysicalBinding(7058,'23fac285def38a913d4fbb2727eebdb4cda0a18a8f9352bfa9aafa6bee3ca9f6'),deadline_ns=time.monotonic_ns()+60*10**9)
packet=execution.archive.parse_json((common/execution.author.SIZING_PATH).read_bytes())
native,ledger,broker,decoder=execution._limits(packet,profile,time.monotonic_ns()+600*10**9)
native.validate();ledger.validate();decoder.validate()
blocked=False
try:execution.execute_once({})
except execution.ExecutionError:blocked=True
assert blocked and execution._CONSUMED is False and not execution.ROOT.exists()
print(json.dumps(dict(status='ACTUAL_STAND_COLD_COORDINATOR_IMPORT_AND_CONTRACT_PASS',source_sha256='3e39fe0f3adac07bb112b184c86f7caa0f78218fea2734ccdbb1066b22daaa58',archive_implementation_profile_sha256=profile.decoder.implementation_profile_sha256,native_requested_limits=asdict(native),decoder_requested_limits=asdict(decoder),broker_requested_caps={k:v for k,v in asdict(broker).items() if k not in ('deadline_ns','authority_expiry_monotonic_ns')},unqualified_report_input_blocked=True,controller_consumed=False,scientific_namespace_created=False,source_preparation_performed=False,qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True,indent=2))
