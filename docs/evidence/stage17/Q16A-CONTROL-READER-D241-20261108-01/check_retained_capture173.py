"""One bounded offline check of already reconstructed original capture173.

No extraction, experiment, original write, prefix acceptance or release authority.
"""
from pathlib import Path
import json
import resource
import time
import validate_prefix as v

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-23')
ROOT=E/'continuation-prefix-1'
OUT=ROOT/'reader-check4-1'
SOURCE=ROOT/'analysis3/scratch/104954-capture-173'


def main():
    resource.setrlimit(resource.RLIMIT_AS,(8*v.GIB,8*v.GIB))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
    original=ROOT/'preparation3/analysis-config.json'
    raw=original.read_bytes()
    v.require(v.sha(raw)=='882d4ce20cf5cc511c71fa01375a07f6f159777f20a132ebbe782b7c9e1e0e3e','original configuration binding')
    c=v.parse(raw)
    c['parallel_adapter']={**c['parallel_adapter'],'path':str(v.HERE/'stage17_discovery_validation_parallel_v2.py')}
    modules,_=v.modules(c)
    plan=v.parse(v.read(c['files']['parent_plan']))
    item=plan['captures'][173]
    custody=v.parse((ROOT/'analysis3/authenticated-prefix-custody.json').read_bytes())
    record=custody['captures'][173]
    v.require(record['capture_ordinal']==173,'original custody ordinal')
    control=record['artifacts'][-1]['logical']
    v.require(control['file_name']=='q16a-c173-control.json','original control role')
    request=v.parse(v.read(c['files']['REQUEST']))
    validator=modules.q16a_capture_validation_v1
    started=time.monotonic_ns()
    with v.formal_control_bounded(validator.common,SOURCE,control,item=item) as document:
        v.save(OUT/'reader-complete.json',dict(status='ORIGINAL_CONTROL_PARSED',
            packed_layout=v.packed_page_layout(item),control_binding=control,
            elapsed_ns=time.monotonic_ns()-started,execution_authority=False),65536)
        report=validator.validate_capture(SOURCE,document,record['native_result_after_cleanup'],
            item['capture'],item['resources'],item['monitoring'],request['action_inputs']['hardware_control'])
    binding=v.save(OUT/'capture-173-validation.json',report,1024**2)
    v.save(OUT/'check-complete.json',dict(status='ORIGINAL_CAPTURE_VALIDATED',report=binding,
        elapsed_ns=time.monotonic_ns()-started,prefix_accepted=False,execution_authority=False),65536)
    print(json.dumps({'status':'ORIGINAL_CAPTURE_VALIDATED','capture_ordinal':173,'execution_authority':False}))


if __name__=='__main__':main()
