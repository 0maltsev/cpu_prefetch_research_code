"""D301 readiness preserves science; expired approval never becomes a launch."""
import ast
import copy
import datetime as dt
import hashlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_saved_request_v1 as current
import stage17_q16c_qualified_continuation_v1 as previous


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'docs/evidence/stage17/Q16C-D298-AUTHORIZATION-STOP-20261119-01/d300-authorization-draft.json'
        self.raw=p.read_bytes();self.template=json.loads(self.raw)
        self.schema=json.loads((ROOT/'config/schemas/stage17-phase-action-authorization-v6.schema.json').read_bytes())

    def test_actual_template_refresh_changes_only_two_times_and_obeys_schema(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),current.TEMPLATE_SHA)
        before=copy.deepcopy(self.template);now=dt.datetime(2026,11,20,0,30,1,999999,tzinfo=dt.timezone.utc)
        out=current.finalize_template(self.template,now,self.schema,now+dt.timedelta(hours=8))
        self.assertEqual(self.template,before)
        self.assertEqual({k for k in out if out[k]!=before[k]},{'issued_at_utc','expires_at_utc'})
        issued=dt.datetime.fromisoformat(out['issued_at_utc']);expires=dt.datetime.fromisoformat(out['expires_at_utc'])
        self.assertEqual((expires-issued).total_seconds(),24860)
        self.assertLessEqual(expires,now+dt.timedelta(seconds=24860))

    def test_template_never_extends_deadline_or_weakens_one_attempt(self):
        now=dt.datetime(2026,11,20,0,30,tzinfo=dt.timezone.utc)
        with self.assertRaises(ValueError):current.finalize_template(self.template,now,self.schema,now+dt.timedelta(seconds=24859))
        for key in ('one_attempt','retry_allowed','stop_first','retain_partial','stage18_authority'):
            bad=copy.deepcopy(self.template);bad[key]=not bad[key]
            with self.subTest(key=key),self.assertRaises(ValueError):current.finalize_template(bad,now,self.schema,now+dt.timedelta(hours=8))
        with self.assertRaises(ValueError):current.finalize_template(self.template,now.replace(tzinfo=None),self.schema,now+dt.timedelta(hours=8))

    def test_approval_retains_actual_word_and_expired_gate(self):
        p=ROOT/'docs/evidence/stage17/Q16C-D301-ACCEPTED-EXPIRED-20261120-01/owner-acceptance.json'
        approval=json.loads(p.read_bytes());current.validate_acceptance(approval)
        self.assertEqual(approval['owner_message'],'approve');self.assertFalse(approval['launch_permitted_at_acceptance'])
        with self.assertRaises(ValueError):current.check_time(1560080250000000)
        with self.assertRaises(ValueError):current.check_time(current.DEADLINE-current.ENVELOPE)

    def test_collect_has_no_authoring_registration_or_second_signature(self):
        raw=(ROOT/'tools/stage17_q16c_continuation_operator_v1.py').read_bytes()
        out=current.render('stage17_q16c_continuation_operator_v1.py',raw).decode()
        functions={n.name:n for n in ast.parse(out).body if isinstance(n,ast.FunctionDef)}
        collect=ast.get_source_segment(out,functions['sign_collect'])
        self.assertNotIn('author_formal',collect);self.assertNotIn('prepare_family',collect);self.assertNotIn('ssh-keygen',collect)
        self.assertIn('cli.execute_formal',collect);self.assertIn('24560*NS',collect)
        original=previous.render('stage17_q16c_continuation_operator_v1.py',raw).decode()
        marker='    import stage17_q16c_compaction_integration_v2 as guarded'
        a=original.index(marker,original.index('def sign_collect('));b=original.index('\n\ndef report_records',a)
        x=out.index(marker,out.index('def sign_collect('));y=out.index('\n\ndef report_records',x)
        self.assertEqual(original[a:b].replace('d298-','d301-'),out[x:y])

    def test_actual_root_orders_authorize_before_collection_inside_readiness_budget(self):
        out=current.render('stage17_q16c_continuation_study_v1.py',
                           (ROOT/'tools/stage17_q16c_continuation_study_v1.py').read_bytes()).decode()
        run=next(n for n in ast.parse(out).body if isinstance(n,ast.FunctionDef) and n.name=='run')
        text=ast.get_source_segment(out,run)
        self.assertLess(text.index("command('authorize'"),text.index("command('sign-collect'"))
        self.assertIn("command('authorize',min(start+600*NS",text)
        self.assertIn("native=args.role in ('construct','authorize','sign-collect')",out)
        self.assertNotIn('command(\'prefix\'',text);self.assertNotIn('command(\'construct\'',text)

    def test_software_metadata_result_can_never_authorize_runtime(self):
        self.assertIn('launch_permitted=not args.software_check',Path(current.__file__).read_text())
        self.assertIn("require(accepted['launch_permitted'] is (not software_check)",Path(current.__file__).read_text())

    def test_runtime_rejects_a_software_only_child_before_hardware_readback(self):
        import subprocess
        import stage17_hardware_recovery_v1 as hardware
        args=types.SimpleNamespace(configuration=Path('/software-only/configuration.json'),configuration_sha256='a'*64)
        response=types.SimpleNamespace(returncode=0,stderr='',stdout=json.dumps(dict(
            configuration_sha256='a'*64,verified_uid=1000,launch_permitted=False)))
        with patch.object(current.os,'geteuid',return_value=0),patch.object(current,'check_time'), \
                patch.object(subprocess,'run',return_value=response) as child,patch.object(hardware,'verify') as verify:
            with self.assertRaisesRegex(ValueError,'software admission grants no launch'):
                current.admit(args,dict(repository_root=str(ROOT)))
            self.assertIn('--owner-journal',child.call_args.args[0]);verify.assert_not_called()


class SequenceTests(unittest.TestCase):
    def scenario(self,failure=None):
        import test_stage17_q16c_qualified_continuation_v1 as baseline
        text=textwrap.dedent(inspect.getsource(baseline.SequenceTests.scenario)).replace('d298','d301')
        text=text.replace("patch.object(current,'DEADLINE',t+39380*10**9)",
                          "patch.object(current,'runtime_deadline',return_value=t+39380*10**9)")
        namespace={**baseline.SequenceTests.scenario.__globals__,'current':current}
        exec(compile(text,'D301-shared-sequence-fixture','exec'),namespace)
        return namespace['scenario'](self,failure)

    def test_success_prepares_authority_once_then_restores_before_analysis(self):
        events,result=self.scenario();self.assertTrue(result['success'],result)
        self.assertEqual(events,['admission','guard','isolation','authorize','sign-collect','hardware-restored',
                                 'isolation-restored','guard-restored','guard-unlocked','suffix'])

    def test_authorization_failure_stops_before_collection_and_restores(self):
        events,result=self.scenario('authorize');self.assertFalse(result['success'])
        self.assertNotIn('sign-collect',events);self.assertIn('guard-restored',events);self.assertNotIn('suffix',events)

    def test_collection_failure_restores_and_never_analyzes(self):
        events,result=self.scenario('sign-collect');self.assertFalse(result['success'])
        self.assertIn('isolation-restored',events);self.assertNotIn('suffix',events)


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);p=Path(self.tmp.name)
        self.proposal=(ROOT/'docs/decisions/0302-q16c-d301-total-deadline-supplement-proposal.md').read_bytes()
        self.approval=json.loads((ROOT/'docs/evidence/stage17/Q16C-D302-ACCEPTED-20261120-01/owner-acceptance.json').read_bytes())
        import prepare_stage17_q16c_saved_request_v1 as prepare
        self.c={'deadline_supplement':{}}
        for name,raw in [('proposal',self.proposal),('acceptance',json.dumps(self.approval).encode()),('signature',b'software-signature-fixture')]:
            f=p/name;f.write_bytes(raw);self.c['deadline_supplement'][name]=prepare.binding(f)
        w=ROOT/'docs/evidence/stage17/Q16C-D295-LAUNCH-20261119-01/startup/d295-execution-window-1/window.json'
        self.c['window_proof']={'manifest':prepare.binding(w)}

    def test_no_supplement_keeps_expired_gate_and_history_unchanged(self):
        self.assertEqual(current.runtime_deadline(),current.ORIGINAL_DEADLINE)
        with self.assertRaises(ValueError):current.check_time(1562011030000000)
        a=json.loads((ROOT/'docs/evidence/stage17/Q16C-D301-ACCEPTED-EXPIRED-20261120-01/owner-acceptance.json').read_bytes())
        current.validate_acceptance(a)
        self.assertEqual(a['original_deadline_monotonic_ns'],current.ORIGINAL_DEADLINE)

    def test_exact_supplement_only_allows_existing_day_and_full_envelope(self):
        current.validate_supplement(self.proposal,self.approval)
        self.assertEqual(current.runtime_deadline(self.c),1636624784571258)
        cutoff=1605164784571258
        current.check_time(cutoff-1,self.c)
        for now in [cutoff,cutoff+1,current.SIGNED_DAY_DEADLINE]:
            with self.subTest(now=now),self.assertRaises(ValueError):current.check_time(now,self.c)
        self.assertEqual(current.deadline_utc(self.c),dt.datetime(2026,11,20,18,41,30,487744,tzinfo=dt.timezone.utc))

    def test_extra_day_time_counts_or_changed_owner_word_are_rejected(self):
        for key,value in [('new_execution_windows',1),('additional_manual_continuations',1),
                          ('admitted_day_deadline_monotonic_ns',current.SIGNED_DAY_DEADLINE+1),
                          ('maximum_remaining_seconds',31461),('remaining_capture_count',93),
                          ('repeat_qualification',True),('owner_message','approve')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                current.validate_supplement(self.proposal,{**self.approval,key:value})
        with self.assertRaises(ValueError):current.validate_supplement(self.proposal+b'\n',self.approval)

    def test_signature_is_mandatory_in_actual_owner_trust_namespace(self):
        import stage17_phase_controller_v2 as controller
        trust={'actual':'admitted-owner-fixture'}
        with patch.object(controller,'_verify_signature',side_effect=ValueError('signature rejected')) as verify:
            with self.assertRaisesRegex(ValueError,'signature rejected'):current.verify_supplement(self.c,trust)
            self.assertEqual(verify.call_args.args[0],json.dumps(self.approval).encode())
            self.assertEqual(verify.call_args.args[2],trust)
        bad=copy.deepcopy(self.c);del bad['deadline_supplement']['signature']
        with self.assertRaises(ValueError):current.runtime_deadline(bad)


if __name__=='__main__':unittest.main()
