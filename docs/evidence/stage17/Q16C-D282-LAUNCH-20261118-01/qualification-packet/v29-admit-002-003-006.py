import datetime,json,pathlib,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');R=E/'admission-root';P=E/'operator-preparation-v29';NAME='cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272';B=E/'local-bundle-extract'/NAME;A=E.parent/(NAME+'.tar.gz');S=pathlib.Path(str(A)+'.sha256');actor='maltsev.oiu@phystech.edu'
def utc():return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def op(*args):
 print('OPERATOR',utc(),json.dumps(list(map(str,args))),flush=True);subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True)
def cli(*args):op('python3','-B',R/'tools/stage17_operational_cli_daycap_v4.py','--repository-root',R,'--evidence-root',E,'--pilot-archive',A,'--pilot-sidecar',S,*args)
def author(kind,*args):op('python3','-B',P/'author_fresh_qualification_records_v2.py',kind,'--repository-root',R,'--evidence-root',E,'--bundle-root',B,'--pilot-archive',A,'--pilot-sidecar',S,'--id-prefix','CPU-PREFETCH-V5-V29','--archive-runtime-root','/',*args)
author('ext002','--trusted-record',E.parent/'local-authoring-cpuprefetchv5-12/ext002-authoring-1/ext002-trust-anchor.json')
cli('admit-resolution','--input-id','S17-EXT-002','--actor',actor,'--recorded-at-utc',utc(),'--receipt-evidence',E/'receipts/ext002-custody-receipt-1.json')
author('ext003')
cli('admit-resolution','--input-id','S17-EXT-003','--actor',actor,'--recorded-at-utc',utc(),'--repository-evidence',R/'evidence/ext003-fresh/ext003-manifest-1.json')
cli('append-transition','--actor',actor,'--timestamp-utc',utc())
author('ext006')
cli('admit-resolution','--input-id','S17-EXT-006','--actor',actor,'--recorded-at-utc',utc(),'--receipt-evidence',E/'receipts/ext006-custody-receipt-1.json')
