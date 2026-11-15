"""Offline admission/receipt/supervisor regressions; no stand or measurements."""
import copy
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import formal_launch_q16b as launch
import isolation_core as core
import q16b_contract as fixed
import reapply_isolation_q16b as setup

HERE = Path(__file__).resolve().parent


class SignatureWrapperLayout(unittest.TestCase):
    def test_latest_journal_uses_formal_namespace_without_previous_module_layout(self):
        journal = object()
        calls = []
        base = types.SimpleNamespace(latest_journal=lambda root: journal)
        cli = types.SimpleNamespace(previous=object(), formal_functions=lambda: {'base': base},
            verify_formal_signature=lambda **arguments: calls.append(arguments) or 'admitted')
        c = dict(repository_root='/tmp/repository', evidence_root='/tmp/evidence',
            archive='/tmp/archive', sidecar='/tmp/sidecar',
            files={'authorization': {'path': '/tmp/authorization'}, 'signature': {'path': '/tmp/signature'}})
        with patch.object(launch, 'admin', return_value=cli):
            self.assertEqual(launch.prepare_signature(c), 'admitted')
        self.assertIs(calls[0]['journal'], journal)
        self.assertEqual(calls[0]['authorization_path'], Path('/tmp/authorization'))


class ExactCandidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (HERE.parent / 'restart-prep/restart-candidate-3/plan.json').read_bytes()
        cls.plan = json.loads(cls.raw)
        cls.proof = json.loads((HERE.parent / 'restart-prep/restart-candidate-3/preparation.json').read_bytes())

    def test_actual_preparation_shape_and_exact_limits(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), fixed.PLAN_SHA)
        requested = launch.limits(self.plan, self.proof, 240518168576, 30709854208)
        self.assertEqual(requested['operational_memory_reserve_bytes'], 8589934592)
        self.assertEqual(requested['required_available_memory_bytes'], 255550554112)
        self.assertEqual(requested['native_max_control_bytes'], 1058469140)
        self.assertEqual(requested['controller_address_space_bytes'], 2147483648)

    def test_wrong_ceiling_and_insufficient_memlock_fail(self):
        for as_bytes, memlock in ((246960619520, 30709854208), (240518168576, 30709854207)):
            with self.assertRaises(ValueError):
                launch.limits(self.plan, self.proof, as_bytes, memlock)

    def test_mismatched_proof_and_missing_cell_fail(self):
        for key, value in (('required_family_as_bytes', 1), ('native_cells', self.proof['native_cells'][:-1]),
                           ('archive_staging_bytes', 1)):
            bad = dict(self.proof, **{key: value})
            with self.assertRaises(ValueError):
                launch.limits(self.plan, bad, 240518168576, 30709854208)

    def test_keeper_exact_unit_core_and_all_five_frozen_monitors(self):
        c = fixed.isolation_config(self.plan)
        core.configure({'operator_config': c})
        self.assertEqual(str(core.CG), str(fixed.PARTITION))
        self.assertEqual(core.CONFIG['lifecycle_seconds'], 13996800)
        self.assertEqual(core.CONFIG['protected_work_ns'], 13827600000000000)
        self.assertEqual(hashlib.sha256((HERE / 'isolation_core.py').read_bytes()).hexdigest(), fixed.CORE_SHA)
        wanted = {str(fixed.PARTITION / name) for name in core.MONITORED}
        for row in self.plan['captures']:
            actual = {s['path'] for s in row['monitoring']['environment_sources'] if s['path'].startswith('/sys/fs/cgroup/')}
            self.assertEqual(actual, wanted)

    def test_remaining_lifetime_strict_boundary_and_old_config_rejected(self):
        core.configure({'operator_config': fixed.isolation_config(self.plan)})
        required = fixed.WATCHDOG_NS + fixed.CLEANUP_NS + 120 * 10**9
        with patch.object(core.time, 'monotonic_ns', return_value=77):
            with self.assertRaises(ValueError):
                core.verify_remaining_lifetime({'keeper_deadline_monotonic_ns': 77 + required}, fixed.WATCHDOG_NS, fixed.CLEANUP_NS)
            core.verify_remaining_lifetime({'keeper_deadline_monotonic_ns': 78 + required}, fixed.WATCHDOG_NS, fixed.CLEANUP_NS)
        old = dict(fixed.isolation_config(self.plan), lifecycle_seconds=2937600)
        with self.assertRaises(ValueError):
            core.configure({'operator_config': old})


class Receipt(unittest.TestCase):
    def setUp(self):
        self.expected = [dict(cpu=c, complete_value_hex='0000000000000000') for c in (0, 1, 8)]
        self.receipt = dict(schema_version='cpu-prefetch-stage17-phase-action-completion/6',
                            action_id='Q16b', attempt_id='fresh', request_sha256='r', authorization_sha256='a',
                            quarantined=False, leader_reaped=True, process_group_gone=True, restoration_verified=True,
                            live_restoration_readback=[dict(cpu=c, expected_hex='0000000000000000',
                                observed_hex='0000000000000000', matches=True) for c in (0, 1, 8)])

    def check(self, receipt):
        return launch.restoration_status(receipt, attempt_id='fresh', request_sha256='r',
            authorization_sha256='a', expected_prestate=self.expected)

    def test_expected_hex_matches_actual_immutable_receipt(self):
        self.assertTrue(self.check(self.receipt)['hardware_restoration_verified'])

    def test_old_requested_hex_shape_rejected(self):
        for row in self.receipt['live_restoration_readback']:
            row['requested_hex'] = row.pop('expected_hex')
        with self.assertRaises(ValueError):
            self.check(self.receipt)

    def test_wrong_cpu_coverage_duplicates_and_matching_wrong_prestate_rejected(self):
        cases = []
        for rows in (self.receipt['live_restoration_readback'][:1], self.receipt['live_restoration_readback'] * 2):
            cases.append(dict(self.receipt, live_restoration_readback=rows))
        wrong = copy.deepcopy(self.receipt)
        wrong['live_restoration_readback'][0].update(expected_hex='000000000000000f', observed_hex='000000000000000f')
        cases.append(wrong)
        cases.append(dict(self.receipt, action_id='Q16a'))
        for value in cases:
            with self.assertRaises(ValueError):
                self.check(value)

    def test_failed_family_can_be_restored_without_completion_credit(self):
        receipt = dict(self.receipt, schema_version='cpu-prefetch-stage17-phase-action-failure/6',
                       quarantine_operation={'performed': False}, recovery_readback=[dict(cpu=r['cpu'], requested_hex=r['expected_hex'], observed_hex=r['observed_hex'], matches=r['matches']) for r in self.receipt['live_restoration_readback']])
        value = self.check(receipt)
        self.assertTrue(value['hardware_restoration_verified'])
        self.assertFalse(value['executor_completed'])

    def test_unreaped_quarantine_and_mismatch_never_success(self):
        for key, value in (('quarantined', True), ('leader_reaped', False), ('process_group_gone', False), ('restoration_verified', False)):
            self.assertFalse(self.check(dict(self.receipt, **{key: value}))['hardware_restoration_verified'])
        self.receipt['live_restoration_readback'][0]['observed_hex'] = '000000000000000f'
        with self.assertRaises(ValueError):
            self.check(self.receipt)


class LaunchBoundaries(unittest.TestCase):
    def setUp(self):
        self.config = dict(uid=1000, gid=1000, stage='launch', supervisor_cpu=3, controller_cpu=2, **fixed.paths())
        self.config.update(admin_bootstrap={'path': str(fixed.ADMIN / 'stage17_formal_admin_v3.py')},
                           packet_manifest={'sha256': 'a' * 64},
                           files={'authorization': {'path': str(fixed.AUTH / 'authorization.json')},
                                  'signature': {'path': str(fixed.AUTH / 'authorization.json.sig')}})
        self.args = types.SimpleNamespace(config=Path('/software/config.json'), config_sha256='b' * 64,
                                         address_space_bytes=240518168576, memlock_bytes=30709854208)

    def test_command_uses_authenticated_bootstrap_and_exact_new_authority(self):
        argv = launch.cli_command(self.config)
        self.assertEqual(argv[:6], ['/usr/bin/python3.14', '-B', str(fixed.E / 'q16b-admission-operators-5/stage17_formal_admin_v3.py'),
                                   '--packet-manifest-sha256', 'a' * 64, 'execute-formal'])
        self.assertIn(str(fixed.AUTH / 'authorization.json'), argv)
        self.assertNotIn('stage17_operational_cli_v18.py', ' '.join(argv))

    def test_owner_check_finite_timeout_kills_and_reaps_only_own_group(self):
        process = MagicMock(pid=123, returncode=None)
        process.communicate.side_effect = subprocess.TimeoutExpired('offline', 600)
        with patch.object(launch.subprocess, 'Popen', return_value=process), patch.object(launch.os, 'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                launch.owner_check(self.config, self.args)
        kill.assert_called_once_with(123, signal.SIGKILL)
        process.wait.assert_called_once_with(timeout=10)

    def test_consumed_namespace_never_spawns_or_restores(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            c = dict(self.config, launch_root=tmp)
            with patch.object(launch, 'cleanup_context') as cleanup, patch.object(launch.subprocess, 'Popen') as spawn:
                with self.assertRaises(ValueError):
                    launch.launch(c, self.args)
            cleanup.assert_not_called()
            spawn.assert_not_called()

    def test_prelaunch_config_cannot_launch(self):
        with self.assertRaises(ValueError):
            launch.launch(dict(self.config, stage='prelaunch'), self.args)

    def test_prelaunch_admission_failure_restores_without_child(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            c = dict(self.config, launch_root=str(Path(tmp) / 'launch'))
            with patch.object(launch, 'cleanup_context', return_value='snapshot'), patch.object(launch.os, 'chown'), \
                 patch.object(launch, 'checks', side_effect=ValueError('expired signature')), \
                 patch.object(launch, 'restore', return_value={'verified': True}) as restore, \
                 patch.object(launch.subprocess, 'Popen') as spawn, patch.object(launch, 'retain') as retain, patch.object(launch, 'handlers'):
                with self.assertRaisesRegex(ValueError, 'expired signature'):
                    launch.launch(c, self.args)
            spawn.assert_not_called()
            restore.assert_called_once_with(c, 'snapshot')
            self.assertEqual(retain.call_args.args[1], 'prelaunch-cleanup.json')

    def test_supervisor_failure_stops_without_child_then_restores(self):
        with patch.object(launch, 'require_intent'), patch.object(launch, 'cleanup_context', return_value='snapshot'), \
             patch.object(launch.os, 'sched_setaffinity'), patch.object(launch, 'documents', side_effect=ValueError('proof changed')), \
             patch.object(launch.subprocess, 'Popen') as spawn, patch.object(launch, 'restore', return_value={'verified': True}) as restore, \
             patch.object(launch, 'retain'), patch.object(launch, 'handlers'):
            result = launch.supervise(self.config, self.args)
        self.assertFalse(result['success'])
        spawn.assert_not_called()
        restore.assert_called_once()

    def test_supervisor_timeout_is_bounded_and_never_retries(self):
        child = MagicMock(pid=456)
        child.wait.side_effect = [subprocess.TimeoutExpired('offline', 1), 143]
        with patch.object(launch, 'require_intent'), patch.object(launch, 'cleanup_context', return_value='snapshot'), \
             patch.object(launch.os, 'sched_setaffinity'), patch.object(launch, 'documents', return_value=({}, None, {})), \
             patch.object(launch, 'checks', return_value={}), patch.object(launch.subprocess, 'Popen', return_value=child) as spawn, \
             patch.object(launch.os, 'killpg') as kill, patch.object(launch, 'restore', return_value={'verified': True}) as restore, \
             patch.object(launch, 'retain'), patch.object(launch, 'handlers'):
            result = launch.supervise(self.config, self.args)
        self.assertFalse(result['success'])
        self.assertTrue(result['child_reaped'])
        self.assertEqual(spawn.call_count, 1)
        kill.assert_called_once_with(456, signal.SIGTERM)
        self.assertEqual(child.wait.call_args_list[1].kwargs, {'timeout': 120.0})
        restore.assert_called_once()

    def test_supervisor_escalation_is_once_and_reaps_before_restoration(self):
        child = MagicMock(pid=456)
        child.wait.side_effect = [subprocess.TimeoutExpired('offline', 1), subprocess.TimeoutExpired('offline', 1), -9]
        with patch.object(launch, 'require_intent'), patch.object(launch, 'cleanup_context', return_value='snapshot'), \
             patch.object(launch.os, 'sched_setaffinity'), patch.object(launch, 'documents', return_value=({}, None, {})), \
             patch.object(launch, 'checks', return_value={}), patch.object(launch.subprocess, 'Popen', return_value=child) as spawn, \
             patch.object(launch.os, 'killpg') as kill, patch.object(launch, 'restore', return_value={'verified': True}) as restore, \
             patch.object(launch, 'retain'), patch.object(launch, 'handlers'):
            result = launch.supervise(self.config, self.args)
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual([call.args for call in kill.call_args_list], [(456, signal.SIGTERM), (456, signal.SIGKILL)])
        self.assertEqual(child.wait.call_args.kwargs, {'timeout': 10})
        self.assertTrue(result['child_reaped'])
        self.assertFalse(result['success'])
        restore.assert_called_once()

    def test_live_partition_tasks_block_restoration(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            iso = types.SimpleNamespace(CG=Path(tmp), read=lambda path: 'unrelated-live-process')
            iso.restore = MagicMock()
            with self.assertRaisesRegex(ValueError, 'live/unrelated'):
                launch.restore(self.config, (iso, {}))
            iso.restore.assert_not_called()


class HardwareAndSetup(unittest.TestCase):
    def setUp(self):
        self.topology = {str(c): f'{c % 16},{c % 16 + 16}' for c in fixed.RESERVED}
        self.expected = [dict(cpu=c, complete_value_hex='0000000000000000') for c in (0, 1, 8)]
        self.plan = {'captures': [dict(capture={'geometry': dict(producer_cpu=0, producer_node=0,
                           consumer_cpu=c, consumer_node=n)},
                           resources={'controller_stack': dict(owner_cpu=2, requested_node=0)}) for c, n in ((1, 0), (8, 1))]}
        self.enterContext(patch.object(setup.os, 'open', return_value=77))
        self.enterContext(patch.object(setup.os, 'close'))
        self.pread = self.enterContext(patch.object(setup.os, 'pread', return_value=b'\0' * 8))
        self.read = self.enterContext(patch.object(Path, 'read_text', autospec=True,
            side_effect=lambda path: self.topology[path.parts[-3][3:]]))
        self.glob = self.enterContext(patch.object(Path, 'glob', autospec=True,
            side_effect=lambda path, pattern: [Path('node1' if path.name == 'cpu8' else 'node0')]))

    def test_actual_readback_preserves_requested_observed_fields(self):
        actual = setup.hardware(self.plan, self.expected, self.topology)
        self.assertEqual(actual['topology']['8']['observed_numa_node'], 1)
        self.assertEqual({r['cpu'] for r in actual['msr_readback']}, {0, 1, 8})
        self.assertTrue(all(r['expected_hex'] == r['observed_hex'] for r in actual['msr_readback']))

    def test_wrong_topology_numa_msr_short_read_all_block(self):
        for raw in (b'\x01' + b'\0' * 7, b'\0' * 7):
            self.pread.return_value = raw
            with self.assertRaises(ValueError):
                setup.hardware(self.plan, self.expected, self.topology)
        self.pread.return_value = b'\0' * 8
        self.glob.side_effect = lambda path, pattern: [Path('node0')]
        with self.assertRaises(ValueError):
            setup.hardware(self.plan, self.expected, self.topology)
        self.read.side_effect = lambda path: '0'
        with self.assertRaises(ValueError):
            setup.hardware(self.plan, self.expected, self.topology)


class SetupCleanup(unittest.TestCase):
    def test_signature_failure_precedes_core_loading(self):
        with patch.object(setup.os, 'geteuid', return_value=0), patch.object(Path, 'exists', return_value=False), \
             patch.object(setup.os, 'sched_setaffinity'), patch.object(launch, 'checks', side_effect=ValueError('bad fresh signature')), \
             patch.object(launch, 'read_bound') as read:
            with self.assertRaisesRegex(ValueError, 'bad fresh signature'):
                setup.prepare(dict(stage='prelaunch', supervisor_cpu=3), None)
        read.assert_not_called()

    def test_post_setup_failure_restores_once_and_never_prepares_again(self):
        fake = MagicMock()
        fake.prepare.return_value = {'prestate': {'owned': 'new Q16b'}}
        fake.isolated_state.side_effect = ValueError('lost isolation')
        d = dict(plan={}, preparation={'hardware_control': {'prestate': []}}, clock_plan={'topology': {}}, isolation_config={})
        c = dict(stage='prelaunch', supervisor_cpu=3, files={'isolation_operator': {}})
        with patch.object(setup.os, 'geteuid', return_value=0), patch.object(Path, 'exists', return_value=False), \
             patch.object(setup.os, 'sched_setaffinity'), patch.object(launch, 'checks', return_value={}), \
             patch.object(launch, 'documents', return_value=(d, None, {})), patch.object(launch, 'read_bound', return_value=b'pass'), \
             patch.object(launch, 'digest', return_value=fixed.CORE_SHA), patch.object(setup.types, 'ModuleType', return_value=fake), \
             patch.object(setup, 'hardware', return_value={}), patch.object(setup.signal, 'signal'):
            with self.assertRaisesRegex(ValueError, 'lost isolation'):
                setup.prepare(c, None)
        fake.prepare.assert_called_once()
        fake.restore.assert_called_once_with({'owned': 'new Q16b'})


class FreshAdmission(unittest.TestCase):
    def exercise(self, *, families=None, reserved=0, memory=255550554112, isolated=True):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            family = Path(tmp)
            d = dict(plan={'budget': {'watchdog_ns': fixed.WATCHDOG_NS, 'cleanup_ns': fixed.CLEANUP_NS}},
                     request={}, authorization={}, preparation={'hardware_control': {'prestate': []}}, clock_plan={'topology': {}},
                     capacity_proof={'families': 2, 'physical_usage': {'quota_bytes': 12}}, isolation_prestate={'prestate': {}})
            config = dict(stage='launch', uid=1000, gid=1000, files={})
            args = types.SimpleNamespace(config_sha256='a' * 64)
            store = MagicMock()
            store.__enter__.return_value = store
            store._families = {k: {} for k in (families or (fixed.PLAN_SHA,
                'a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7',
                '91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2',
                'ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702'))}
            store.physical_accounting.return_value = types.SimpleNamespace(quota_bytes=12)
            store.ledger_binding.return_value = types.SimpleNamespace(file_name='current', sha256='l', size_bytes=1)
            store.reserved_bytes.return_value = reserved
            executor = types.SimpleNamespace(open_store=lambda *a: store,
                live_resources=lambda *a, **kw: {'memory_available_bytes': memory})
            plans = types.SimpleNamespace(validate_plan=lambda *a: types.SimpleNamespace(declared=types.SimpleNamespace(cleanup_ns=120000000000)))
            iso = MagicMock()
            iso.isolated_state.return_value = {'partition': {'cgroup.procs': '' if isolated else '12', 'cgroup.events': 'populated 0'}}
            with patch.object(launch.os, 'geteuid', return_value=1000), patch.object(launch.os, 'getresuid', return_value=(1000,) * 3), \
                 patch.object(launch.os, 'getresgid', return_value=(1000,) * 3), patch.object(launch.os, 'getgroups', return_value=[]), \
                 patch.object(launch, 'status', return_value={k: f'{launch.CAP_MASK:x}' for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')}), \
                 patch.object(launch, 'documents', return_value=(d, family, {'required_available_memory_bytes': 255550554112})), \
                 patch.object(launch, 'prepare_signature', return_value=types.SimpleNamespace(request={}, authorization={})) as signature, \
                 patch.object(Path, 'stat', return_value=types.SimpleNamespace(st_uid=1000)), \
                 patch.dict(sys.modules, stage17_fixed_action_executor_v11=executor, stage17_formal_plan_v2=plans), \
                 patch.object(setup, 'hardware', return_value={}), patch.object(launch, 'isolation', return_value=iso):
                value = launch.checks(config, args)
            self.assertEqual(signature.call_count, 2)
            return value

    def test_exact_fresh_admission_and_final_signature_recheck(self):
        result = self.exercise()
        self.assertEqual(result['resource_observation']['registered_families'], 4)
        self.assertIs(result['execution_authority'], False)

    def test_pending_reservation_missing_history_low_memory_or_live_tasks_block(self):
        for bad in ({'reserved': 1}, {'families': (fixed.PLAN_SHA,)}, {'memory': 255550554111}, {'isolated': False}):
            with self.assertRaises(ValueError):
                self.exercise(**bad)

    def test_family_ceiling_without_8gib_headroom_is_insufficient(self):
        with self.assertRaisesRegex(ValueError, '8GiB operational reserve'):
            self.exercise(memory=246960619520)


class BootstrapCache(unittest.TestCase):
    def setUp(self):
        self.c = dict(admin_bootstrap={'path': str(fixed.ADMIN / 'stage17_formal_admin_v3.py')},
                      packet_manifest={'path': str(fixed.ADMIN / 'manifest.json'), 'sha256': 'a' * 64})
        self.source = b'calls=[]\ndef activate_packet(sha):\n calls.append(sha)\n return len(calls)\n'
        self.packet = dict(schema_version=fixed.ADMIN_SCHEMA, files=[dict(name=fixed.ADMIN_MODULE+'.py',
            size_bytes=len(self.source),sha256=hashlib.sha256(self.source).hexdigest()),
            *[dict(name=name+'.py',size_bytes=1,sha256='b'*64) for name in
                ('stage17_operational_cli_v20','stage17_phase_controller_v27','stage17_q16a_handoff_v1')]])
        self.enterContext(patch.object(launch, '_ADMIN_CACHE', None))
        self.enterContext(patch.dict(sys.modules))
        sys.modules.pop(fixed.ADMIN_MODULE, None)
        self.read = self.enterContext(patch.object(launch, 'read_bound', side_effect=lambda b:
            self.source if b is self.c['admin_bootstrap'] else json.dumps(self.packet).encode()))

    def test_v2_reentry_reuses_verified_instance_and_rejects_foreign_cache(self):
        foreign = types.ModuleType(fixed.ADMIN_MODULE)
        foreign.__file__ = self.c['admin_bootstrap']['path']
        foreign.activate_packet = MagicMock()
        sys.modules[fixed.ADMIN_MODULE] = foreign
        with self.assertRaisesRegex(ValueError, 'unverified bootstrap already cached'):
            launch.admin(self.c)
        foreign.activate_packet.assert_not_called()
        del sys.modules[fixed.ADMIN_MODULE]
        self.assertEqual(launch.admin(self.c), 1)
        verified = sys.modules[fixed.ADMIN_MODULE]
        self.assertEqual(launch.admin(self.c), 2)
        self.assertIs(sys.modules[fixed.ADMIN_MODULE], verified)
        sys.modules[fixed.ADMIN_MODULE] = foreign
        with self.assertRaisesRegex(ValueError, 'module identity changed'):
            launch.admin(self.c)
        foreign.activate_packet.assert_not_called()
        self.assertEqual(verified.calls, ['a' * 64] * 2)

    def test_manifest_member_mismatch_rejected_before_source_exec(self):
        # This source raises if executed, proving the manifest gate precedes
        # compilation/execution even when config-level source reading succeeds.
        self.source = b'raise RuntimeError("unverified source executed")\n'
        with self.assertRaisesRegex(ValueError, 'bootstrap bytes differ from verified packet member'):
            launch.admin(self.c)
        self.assertNotIn(fixed.ADMIN_MODULE, sys.modules)

    def test_replaced_callback_and_mutated_code_rejected_before_invocation(self):
        self.assertEqual(launch.admin(self.c), 1)
        verified = sys.modules[fixed.ADMIN_MODULE]
        original = verified.activate_packet
        foreign = MagicMock()
        verified.activate_packet = foreign
        with self.assertRaisesRegex(ValueError, 'function/code identity changed'):
            launch.admin(self.c)
        foreign.assert_not_called()
        verified.activate_packet = original
        original.__code__ = (lambda sha: 999).__code__
        with self.assertRaisesRegex(ValueError, 'function/code identity changed'):
            launch.admin(self.c)
        self.assertEqual(verified.calls, ['a' * 64])

    def test_v1_schema_never_activates_or_creates_cached_bootstrap(self):
        self.read.side_effect = lambda b: self.source if b is self.c['admin_bootstrap'] else b'{"schema_version":"cpu-prefetch-stage17-formal-admin-packet/1"}'
        with self.assertRaisesRegex(ValueError, 'v2 packet schema required'):
            launch.admin(self.c)
        self.assertNotIn(fixed.ADMIN_MODULE, sys.modules)


if __name__ == '__main__':
    unittest.main()
