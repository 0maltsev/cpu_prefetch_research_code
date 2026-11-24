from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import time

os.sched_setaffinity(0, {3})
e = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
out = e/'q16c-analysis-1'
intent = json.loads((out/'analysis-intent.json').read_bytes())
receipts = []
for p in sorted(out.glob('capture-*-process.json')):
    assert p.stat().st_size < 131072
    v = json.loads(p.read_bytes())
    receipts.append(dict(ordinal=v['ordinal'],status=v['status'],exit_code=v['exit_code'],
        leader_reaped=v['leader_reaped'],report_sha256=v.get('report',{}).get('sha256'),
        elapsed_ns=v.get('elapsed_ns'),error=v.get('error')))
now = time.monotonic_ns()
stamp = dt.datetime.now(dt.timezone.utc)
remaining = (intent['deadline_monotonic_ns']-now)/1e9
summary = dict(checked_at_utc=stamp.isoformat(),analysis_intent=intent,
    report_count=len(list((out/'reports').glob('capture-*.json'))),
    valid_reaped_process_count=sum(v['status']=='VALID' and v['exit_code']==0 and v['leader_reaped'] is True for v in receipts),
    failed_process_receipts=[v for v in receipts if v['status']!='VALID' or v['exit_code']!=0 or v['leader_reaped'] is not True],
    process_receipts=receipts,remaining_analysis_seconds=remaining,
    analysis_deadline_utc=(stamp+dt.timedelta(seconds=remaining)).isoformat(),
    scientific_completion_present=(out/'complete.json').exists(),
    composition_finalization_present=(out/'finalized.json').exists(),raw_data_transferred=False)
print(json.dumps(summary,sort_keys=True,indent=2),flush=True)
