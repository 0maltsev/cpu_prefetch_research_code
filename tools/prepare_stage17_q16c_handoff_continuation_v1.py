"""Publish approved D306 metadata under its actual owner; no native execution."""
import json
import os
from pathlib import Path
import re
import subprocess

import stage17_q16c_handoff_continuation_v1 as resume
from prepare_stage17_q16c_saved_request_v1 import binding, document, publish


def main():
    resume.parent_verified()
    resume.require(os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups(), 'actual evidence owner')
    ops = Path(__file__).resolve().parent; e = resume.E
    resume.require(ops == e/'d306-continuation-1', 'one distinct D306 administrative namespace')
    prior = e/'d301-continuation-2/launch-configuration.json'
    resume.require(binding(prior)['sha256'] == resume.STOPPED_CONFIGURATION_SHA, 'exact consumed D301 configuration')
    old = document(prior); c = dict(old)
    manifest = document(ops/'administrative-packet.json'); revision = manifest['administrative_source_revision']
    resume.require(re.fullmatch('[0-9a-f]{40}', revision) and revision != resume.NATIVE_SOURCE, 'separate administrative source commit')
    for row in manifest['files']:
        actual = binding(ops/row['path'])
        resume.require((actual['size_bytes'], actual['sha256']) == (row['size_bytes'], row['sha256']), 'actual installed packet bytes')
    sources = dict(old['operator_sources'])
    for path in sorted(ops.glob('*.py')):
        sources[path.name] = binding(path)
    iso = document(old['qualification_isolation_configuration']['path'])
    iso['evidence_root'] = str(e/'isolation-preparation-v32-d306-1')
    isob = publish(ops/'isolation-configuration.json', iso)
    authority = ops/'authority'; acceptance = authority/'owner-acceptance.json'
    resume.validate_acceptance(document(acceptance))
    resume.require(binding(authority/'proposal.md')['sha256'] == resume.PROPOSAL_SHA, 'exact approved D306 proposal')
    signed = subprocess.run(['ssh-keygen', '-Y', 'sign', '-f', '/home/omaltsev/.ssh/id_ed25519', '-n',
                             'stage17-owner-acceptance', str(acceptance)], capture_output=True, text=True, timeout=30)
    publish(ops/'acceptance-signing-result.json', dict(exit_code=signed.returncode, stdout=signed.stdout, stderr=signed.stderr))
    resume.require(signed.returncode == 0, 'actual D306 acceptance signing failed')
    out = ops/'runtime-output'; out.mkdir(mode=0o700)
    import stage17_q16c_continuation_operator_v1 as io
    raw = io.read(old['preconstruction'])
    resume.require(len(raw) == 572 and old['preconstruction']['sha256'] ==
        '5867405f24bb920ef684c9fbff296375d48f338f814137f0cb6ba2aa41719838', 'original exact constructor wrapper')
    with (out/'constructed.json').open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    prepared = binding(Path(old['output_root'])/'prepared.json'); p = io.document(prepared)
    inventory = publish(ops/'operator-sources.json', dict(schema_version='cpu-prefetch-d306-administrative-operators/1',
        administrative_source_revision=revision, qualified_native_source_revision=resume.NATIVE_SOURCE,
        sources=sources, execution_authority=False, phase18_authority=False))
    c.update(schema_version='cpu-prefetch-d306-handoff-continuation-inputs/1', continuation_decision='D306',
        administrative_source_revision=revision, operator_sources=sources, operator_inventory=inventory,
        supervisor_unit='cpu-prefetch-d306-v32-1.service', clock_adapter=binding(ops/'d306_rearm_isolation.py'),
        qualification_isolation_configuration=isob,
        continuation_authority=dict(proposal=binding(authority/'proposal.md'), acceptance=binding(acceptance),
                                    signature=binding(Path(str(acceptance)+'.sig'))),
        original_preconstruction=old['preconstruction'], preconstruction=binding(out/'constructed.json'),
        output_root=str(out), operational_authorization_path=str(ops/'authorization.json'),
        stopped_configuration=binding(prior), administrative_packet=binding(ops/'administrative-packet.json'),
        stopped_handoff=dict(prepared=prepared, authorization=p['authorization'], signature=p['signature'],
            result=binding(e/'d301-study-1/result.json'), recovery=binding(e/'d301-independent-recovery-1.json')))
    resume.validate_handoff(c)
    result = publish(ops/'launch-configuration.json', c)
    print(json.dumps(dict(status='D306_METADATA_PUBLISHED_NO_EXECUTION', configuration=result,
        administrative_source_revision=revision, qualified_native_source_revision=resume.NATIVE_SOURCE,
        launch_permitted=False, controls_rearmed=False, operational_authority_signed=False,
        new_execution_window=False, execution_authority=False)), flush=True)


if __name__ == '__main__':
    main()
