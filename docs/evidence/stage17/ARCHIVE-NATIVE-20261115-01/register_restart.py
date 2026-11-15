"""One authorized append after actual fresh admission and same-lock guards."""
import argparse,dataclasses,datetime,hashlib,importlib,json,os,pathlib,sys,time
from types import SimpleNamespace
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');N=E/'q16b-namespace-admission-2';P=N/'operators-v3'
parser=argparse.ArgumentParser();parser.add_argument('--local-audit-sha256',required=True);parser.add_argument('--stand-audit-sha256',required=True);args=parser.parse_args()
assert os.getuid()==os.geteuid()==1000
out=N/'family-registration-1.json';assert not out.exists()
sys.path.insert(0,str(P));import prepare_registration_q16b as prep
assert pathlib.Path(prep.__file__).parent==P
A=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a.tar.gz'
a=SimpleNamespace(repository_root=E/'admission-root',evidence_root=E,pilot_archive=A,pilot_sidecar=pathlib.Path(str(A)+'.sha256'),packet_root=E/'q16b-admission-operators-5',packet_manifest_sha256='6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919',plan=E/'formal-q16b-preparation-2/plan.json',identities=N/'planned-identities.json',identities_sha256='0b24944837d3a9d4a6c034d601444afb07657516a083213d5bfccebc5e8a9e22',local_audit=N/'local-audit-final.json',local_audit_sha256=args.local_audit_sha256,stand_audit=N/'stand-audit-final.json',stand_audit_sha256=args.stand_audit_sha256,action_inputs=E/'formal-q16b-preparation-2/action-inputs-proposal.json',action_inputs_sha256='4f8785e3a931cba0696c636c1a0c866322802293018efc57840b9df9386a636f',expected_program_state=None,expected_program_state_sha256=None,deadline_monotonic_ns=time.monotonic_ns()+1800*10**9)
def save(path,document):
 b=prep.audit.canonical(document)
 with path.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 return dict(path=str(path),size_bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
prepared=prep.prepare(a)
prepared_binding=save(N/'registration-preparation-1.json',prepared)
print('QUALIFIED_REGISTRATION_PREPARATION_PASS',flush=True)
import stage17_formal_archive_custody_v1 as custody
before=prepared['expected_program_state'];parameters=prepared['family_registration_arguments'];limits=custody.CustodyLimits(**parameters['limits'])
with custody.ProgramStore(pathlib.Path(parameters['root']),scope_sha256=parameters['scope_sha256'],family_id=parameters['family_id'],limits=limits) as store:
 prep.guard_existing_program(store,before)
 path=store.prepare_family(parameters['family_id'])
 tip=prep.guard_registered_program(store,before)
 facts=dict(store._families[parameters['family_id']])
receipt=dict(status='Q16B_FAMILY_REGISTERED_ONE_APPEND',registered_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),plan_sha256=parameters['family_id'],program_scope_sha256=parameters['scope_sha256'],program_root=parameters['root'],working_root=str(path),qualification=prepared['qualification'],namespace_reservation=prepared['namespace_reservation'],preparation=prepared_binding,old_program_state=before,new_family_facts=facts,new_ledger_tip=tip,registered_families=4,quota_reset=False,registered=True,signature_created=False,experiment_started=False,execution_authority=False,phase18_authority=False)
binding=save(out,receipt);print(json.dumps(dict(status=receipt['status'],receipt=binding,working_root=str(path),new_ledger_tip=tip,experiment_started=False)),flush=True)
