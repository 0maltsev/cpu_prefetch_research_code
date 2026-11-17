"""D277 exclusive owner-signed execution-day publication after cold readiness.

--check is read-only and creates no deadline. --start publishes the one approved
window once. Neither mode launches a native worker or changes hardware controls.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28')
P=E/'q16c-configuration-2'


def require(ok,message):
    if not ok:raise ValueError('D277 window author: '+message)


def binding(p):
    raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true');mode.add_argument('--start',action='store_true')
    p.add_argument('--packet-manifest-sha256',required=True);a=p.parse_args()
    require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
    require(Path(__file__).resolve()==P/'author_stage17_q16c_execution_window_v1.py','installed cold author')
    import stage17_q16c_packet_v2 as loader
    manifest,members=loader.verify_packet(P,a.packet_manifest_sha256)
    require(members[Path(__file__).name]==Path(__file__).read_bytes(),'actual author code binding')
    sys.path.insert(0,str(E/'admission-root/tools'))
    import stage17_operational_cli_daycap_v3 as cli
    import stage17_q16c_execution_window_v1 as window
    archive=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-919c486-clean-2dda11ec716e.tar.gz';sidecar=Path(str(archive)+'.sha256')
    cli.activate();validation=cli._validation(E/'admission-root',E,pilot_archive=archive,pilot_sidecar=sidecar)
    require(set(validation.resolutions)=={'S17-EXT-001','S17-EXT-002','S17-EXT-003','S17-EXT-006'},'exact retained pre-Q15 prefix')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==window.BOOT,'actual retained boot')
    trust=validation.resolutions['S17-EXT-003'].semantic_context['trust']
    source=E/'q16c-sources-1/source-preparation.json';signature=Path(str(source)+'.sig')
    cli.controller.support._verify_signature(source.read_bytes(),signature,trust)
    plan=window.parse((P/'plan.json').read_bytes())
    import stage17_formal_scheduled_descriptive_v1 as contract
    contract.validate_plan(plan)
    require(len(plan['captures'])==180 and plan['budget']['watchdog_ns']==window.FAMILY*window.NS,'complete frozen180 settings')
    paths=dict(source_manifest=source,source_signature=signature,sizing=E/'q16c-resources-2/complete.json',
        clocks=E/'clock-qualification-v28-1/complete.json',acceptance=P/'d277-owner-acceptance.json',
        decision=P/'d277-decision.md',plan=P/'plan.json',
        qualified_inventory=Path(validation.resolutions['S17-EXT-006'].semantic_context['archive_bundle_root'])/'BUNDLE_INVENTORY.json',
        qualified_worker=Path(validation.resolutions['S17-EXT-006'].semantic_context['release_artifact_path']),administrative_manifest=P/'manifest.json')
    bindings={k:binding(v) for k,v in paths.items()}
    for b in bindings.values():window.read(b)
    require(bindings['decision']['sha256']==window.DECISION_SHA,'exact accepted proposal')
    require(not (E/'d277-execution-window-1').exists() and not list(E.glob('stage17-q15*'))
        and not (E/'q16c-study-1').exists(),'new execution already attempted; no retry')
    readiness=dict(status='COLD_PACKET_SOURCE_SIGNATURE_PREFIX_PLAN_VERIFIED',native_worker_started=False,
        execution_window_started=False,bindings=bindings,estimated_ceiling_seconds=window.TOTAL,phase18_authority=False)
    if a.check:print(json.dumps(readiness),flush=True);return
    # Readiness is complete. Sampling this anchor starts the one new24h interval.
    start=time.monotonic_ns();stamp=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
    record=dict(schema_version=window.SCHEMA,execution_window_id=window.IDENTITY,decision_id='D277',
        source_revision=window.SOURCE,worker_sha256=window.WORKER,boot_id=window.BOOT,stand_id=plan['stand_id'],
        started_monotonic_ns=start,global_deadline_ns=start+86400*window.NS,started_at_utc=stamp,bindings=bindings,
        qualification_seconds=window.QUALIFICATION,family_seconds=window.FAMILY,analysis_seconds=window.ANALYSIS,
        restoration_seconds=window.RESTORATION,automatic_retries=0,new_windows_allowed=0,
        execution_authority=False,phase18_authority=False)
    window.validate(record,now=start,qualification=True)
    folder=E/'d277-execution-window-1';folder.mkdir(mode=0o700)
    path=folder/'window.json'
    def save(path,raw):
        with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    save(path,window.canonical(record))
    result=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(path)],
        stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    save(folder/'signing-result.json',window.canonical(dict(exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace'))))
    require(result.returncode==0,'actual owner signature failed; no retry')
    proof=dict(manifest=binding(path),signature=binding(Path(str(path)+'.sig')))
    window.authenticate(proof,validation=validation,plan=plan,now=time.monotonic_ns())
    save(folder/'complete.json',window.canonical(dict(status='OWNER_SIGNED_SEPARATE_EXECUTION_WINDOW',proof=proof,
        source_study_unchanged=True,execution_authority=False,phase18_authority=False)))
    print(json.dumps(dict(proof=proof,started_at_utc=stamp,global_deadline_ns=record['global_deadline_ns'],estimated_ceiling_seconds=window.TOTAL)),flush=True)


if __name__=='__main__':main()
