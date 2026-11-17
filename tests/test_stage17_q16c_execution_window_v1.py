"""Software-only prospective timing and private journal routing for D277/D278."""
import copy
from pathlib import Path
import sys
import unittest
import tempfile
import subprocess
import types
import hashlib
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_execution_window_v1 as window
import stage17_q16c_descriptive_administration_v2 as admin
import stage17_state_journal_v58 as journal


def record():
    return dict(schema_version=window.SCHEMA,execution_window_id=window.IDENTITY,decision_id='D277',
        source_revision=window.SOURCE,worker_sha256=window.WORKER,boot_id=window.BOOT,stand_id='software-only',
        started_monotonic_ns=10**15,global_deadline_ns=10**15+86400*10**9,started_at_utc='2026-11-17T20:00:00Z',
        bindings={k:{} for k in window.ROLES},qualification_seconds=7200,family_seconds=47820,
        analysis_seconds=5400,restoration_seconds=2400,automatic_retries=0,new_windows_allowed=0,
        execution_authority=False,phase18_authority=False)


class ExecutionWindowTests(unittest.TestCase):
    def test_complete_budget_is_17h27_without_source_regeneration(self):
        r=record();self.assertEqual(window.TOTAL,62820)
        self.assertEqual(window.validate(r,now=r['started_monotonic_ns'],qualification=True),86400*10**9)
        self.assertEqual(r,record())

    def test_full_envelope_strict_boundary(self):
        r=record();last=r['global_deadline_ns']-62820*10**9
        window.validate(r,now=last-1,qualification=True)
        with self.assertRaisesRegex(ValueError,'cannot fit'):window.validate(r,now=last,qualification=True)
        window.validate(r,now=last,qualification=False)

    def test_mutated_release_clock_duration_budget_or_scope_is_rejected(self):
        for key,value in [('source_revision','0'*40),('worker_sha256','0'*64),('boot_id','other'),
                ('global_deadline_ns',record()['global_deadline_ns']+1),('qualification_seconds',1800),
                ('family_seconds',47220),('analysis_seconds',0),('restoration_seconds',0),
                ('automatic_retries',True),('new_windows_allowed',1),('execution_authority',True),
                ('phase18_authority',True),('extra',False),('started_monotonic_ns',False)]:
            r=record();r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):window.validate(r,now=10**15,qualification=True)
        for key in window.ROLES:
            r=record();del r['bindings'][key]
            with self.subTest(missing=key),self.assertRaises(ValueError):window.validate(r,now=10**15)

    def test_new_window_does_not_accept_old_source_schema(self):
        with self.assertRaises(ValueError):window.validate(dict(started_monotonic_ns=10**15,global_deadline_ns=10**15+86400*10**9),now=10**15)

    def test_isolation_keeper_leaves_restore_reserve(self):
        r=record();c=dict(boot_id=window.BOOT,source_revision=window.SOURCE,lifecycle_seconds=63000,
            protected_work_ns=(7200+47820+120)*10**9,stop_seconds=120)
        window.infrastructure(r,c,now=10**15)
        for key,value in [('protected_work_ns',47820*10**9),('lifecycle_seconds',85000),('boot_id','other')]:
            bad=dict(c);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):window.infrastructure(r,bad,now=10**15)

    def test_real_signature_and_retained_bytes_are_required(self):
        bundles=list((ROOT/'build/stage17-q16c-prep/verified-919c486').glob('cpu-prefetch-*'))
        self.assertEqual(len(bundles),1,'actual qualified software fixture required')
        fixture=ROOT/'docs/evidence/stage17/Q16C-D274-SOURCE-SIZING-20261117-01'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'d277-execution-window-1';folder.mkdir()
            key=root/'software-only-key'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True,capture_output=True)
            allowed=root/'allowed';allowed.write_text('software-owner '+key.with_suffix('.pub').read_text())
            def bind(p):
                raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            def save(name,value):
                p=root/name;p.write_bytes(window.canonical(value));return bind(p)
            trust=dict(subject_id='CPU-PREFETCH-V5',measurements=dict(principal='software-owner',reviewer_role='OWNER',
                sshsig_namespace='stage17-owner-acceptance',allowed_signers_path=str(allowed),
                allowed_signers_size_bytes=allowed.stat().st_size,allowed_signers_sha256=bind(allowed)['sha256']))
            validation=types.SimpleNamespace(resolutions={
                'S17-EXT-003':types.SimpleNamespace(semantic_context={'trust':trust}),
                'S17-EXT-006':types.SimpleNamespace(semantic_context=dict(source_revision=window.SOURCE,release_artifact_sha256=window.WORKER))})
            plan=dict(source_revision=window.SOURCE,stand_id='CPU-PREFETCH-V5',captures=[{}]*180,budget=dict(watchdog_ns=47820*10**9))
            r=record();r.update(stand_id='CPU-PREFETCH-V5',started_monotonic_ns=2*10**15,global_deadline_ns=2*10**15+86400*10**9)
            r['bindings']=dict(source_manifest=bind(fixture/'source-preparation.json'),source_signature=bind(fixture/'source-preparation.json.sig'),
                sizing=bind(fixture/'native-sizing-proof.json'),
                clocks=bind(ROOT/'docs/evidence/stage17/Q16C-D275-LAUNCH-20261117-01/clocks-complete.json'),
                acceptance=bind(ROOT/'docs/evidence/stage17/Q16C-D277-ACCEPTED-20261117-01/owner-acceptance.json'),
                decision=bind(ROOT/'docs/decisions/0277-q16c-retained-setup-new-window-proposal.md'),plan=save('software-plan.json',plan),
                qualified_inventory=bind(bundles[0]/'BUNDLE_INVENTORY.json'),qualified_worker=bind(bundles[0]/'release/bin/cpu_prefetch_runner'),
                administrative_manifest=save('software-admin-manifest.json',dict(qualified_source_revision=window.SOURCE,qualified_worker_sha256=window.WORKER,
                    execution_authority=False,phase18_authority=False)))
            manifest=folder/'window.json';manifest.write_bytes(window.canonical(r))
            subprocess.run(['ssh-keygen','-Y','sign','-f',str(key),'-n','stage17-owner-acceptance',str(manifest)],check=True,capture_output=True)
            proof=dict(manifest=bind(manifest),signature=bind(Path(str(manifest)+'.sig')))
            original_read_text=Path.read_text
            def live_boot(p,*args,**kw):
                return window.BOOT if str(p)=='/proc/sys/kernel/random/boot_id' else original_read_text(p,*args,**kw)
            with patch.object(window,'EVIDENCE',root),patch.object(Path,'read_text',live_boot):
                out=window.authenticate(proof,validation=validation,plan=plan,now=r['started_monotonic_ns'])
                self.assertEqual(out,r)
                # Rehashing a modified manifest cannot repair the original signature.
                altered=copy.deepcopy(r);altered['stand_id']='different-stand';manifest.write_bytes(window.canonical(altered))
                bad=dict(proof,manifest=bind(manifest))
                with self.assertRaises(ValueError):window.authenticate(bad,validation=validation,plan=plan,now=r['started_monotonic_ns'])
                manifest.write_bytes(window.canonical(r));p=Path(r['bindings']['plan']['path']);raw=p.read_bytes();p.write_bytes(b' '+raw[1:])
                with self.assertRaisesRegex(ValueError,'bound bytes differ'):
                    window.authenticate(proof,validation=validation,plan=plan,now=r['started_monotonic_ns'])

    def test_private_cli_and_controller_use_recovery_without_mutating_old_journal(self):
        original=journal.predecessor.validate_operational_journal
        cli=admin.make_cli();controller=cli.controller
        self.assertIs(cli.journal,journal)
        self.assertIs(cli._validation.__globals__['journal'],journal)
        self.assertIs(cli.base.journal_runtime,journal)
        self.assertIs(controller.prepare_action.__globals__['journal_runtime'],journal)
        self.assertIs(controller._v25._prepare_action.__globals__['journal_runtime'],journal)
        self.assertIs(controller.activate.__globals__['journal_runtime'],journal)
        cli.activate()
        self.assertIs(cli.base.journal_runtime,journal)
        self.assertIs(journal.predecessor.validate_operational_journal,original)
        self.assertTrue(callable(controller.configure_execution_window))


if __name__=='__main__':unittest.main()
