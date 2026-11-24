"""Real owned processes/IPC; original reader and UID0 are software boundaries.

The private runner's UID0 fixture works inside a one-ID user namespace.
Production always requests1000 and must additionally pass actual stand replay.
"""
import os
import hashlib
from pathlib import Path
import signal
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_owner_replay_v1 as replay


def fixture():
    value=SimpleNamespace(current_state='READY_FOR_STAGE17_PHASE_AUTHORIZATION',pilot_ready=False,
        resolved_input_ids=tuple(f'S17-EXT-{i:03d}' for i in range(1,8)),missing_input_ids=('S17-EXT-008',),
        resolution_count=7,transition_count=3,latest_journal_sha256='a'*64,action_ready=False,stand_status='SOFTWARE',
        resolutions={f'S17-EXT-{i:03d}':SimpleNamespace(input_id=f'S17-EXT-{i:03d}',resolution_id=f'SOFTWARE-{i}',
            sha256=str(i)*64,semantic_context=dict(software_fixture_only=True)) for i in range(1,8)})
    value.resolutions['S17-EXT-002'].semantic_context['stand_id']='SOFTWARE-STAND'
    value.resolutions['S17-EXT-003'].semantic_context['trust']={'measurements':{'allowed_signers_path':Path('/SOFTWARE/signers')}}
    value.resolutions['S17-EXT-006'].semantic_context.update(source_revision='a'*40,inventory_sha256='b'*64,
        release_artifact_sha256='c'*64,release_artifact_size_bytes=1,
        archive_bundle_root=Path('/SOFTWARE/bundle'),release_artifact_path=Path('/SOFTWARE/bundle/worker'))
    value.resolutions['S17-EXT-007'].semantic_context.update(calibration_scope='STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY',
        data_provenance_accepted=True,legacy_statistical_freeze_satisfied=False)
    return value


class ReplayTests(unittest.TestCase):
    def run_reader(self,body=None,seconds=125):
        before=os.getresuid()
        with mock.patch.object(replay.original,'validate_operational_journal',side_effect=body or (lambda **kwargs:fixture())):
            result=replay._run({},time.monotonic_ns()+int(seconds*10**9),uid=0,gid=0)
        self.assertEqual(os.getresuid(),before);return result

    def test_actual_private_reader_and_sealed_json_need_exit_and_reap(self):
        value,proof=self.run_reader()
        self.assertEqual(value['resolution_count'],7);self.assertFalse(value['pilot_ready'])
        self.assertTrue(proof['actual_owner_reader_completed']);self.assertTrue(proof['cleanup']['leader_reaped'])
        self.assertTrue(proof['cleanup']['process_group_gone']);self.assertEqual(proof['cleanup']['returncode'],0)
        self.assertTrue(proof['root_parent_credentials_preserved']);self.assertFalse(proof['execution_authority'])
        self.assertEqual(proof['observed_reader']['actual_uid_fields'],[0]*4)

    def test_original_reader_failure_cannot_become_a_success_view(self):
        def failed(**kwargs):raise ValueError('SOFTWARE legacy signature rejected')
        with self.assertRaises(replay.archive.ArchiveError) as caught:self.run_reader(failed)
        self.assertFalse(caught.exception.report['actual_owner_reader_completed'])
        self.assertIn('legacy signature rejected',caught.exception.report['console_prefix'])

    def test_legacy_snapshot_file_limit_is_separate_from_small_report_limit(self):
        def snapshot(**kwargs):
            fd=os.memfd_create('SOFTWARE-only-original-archive-snapshot',os.MFD_CLOEXEC)
            try:os.ftruncate(fd,replay.DATA_MAX+1)
            finally:os.close(fd)
            return fixture()
        value,proof=self.run_reader(snapshot)
        self.assertEqual(value['resolution_count'],7);self.assertTrue(proof['actual_owner_reader_completed'])
        self.assertEqual(proof['observed_reader']['file_size_bytes'],[replay.CHILD_FILE_BYTES]*2)

    def test_legacy_path_locators_cross_the_json_boundary_as_data(self):
        def with_paths(**kwargs):
            value=fixture()
            return value
        value,proof=self.run_reader(with_paths)
        self.assertEqual(value['resolutions']['S17-EXT-006']['semantic_context']['archive_bundle_root'],'/SOFTWARE/bundle')
        self.assertEqual(value['resolutions']['S17-EXT-003']['semantic_context']['trust']['measurements']['allowed_signers_path'],
            '/SOFTWARE/signers')
        self.assertTrue(proof['actual_owner_reader_completed'])

    def test_live_legacy_context_objects_do_not_cross_the_closed_fact_interface(self):
        def live(**kwargs):
            value=fixture();value.resolutions['S17-EXT-006'].semantic_context['legacy_bundle_context']=object()
            return value
        value,proof=self.run_reader(live)
        self.assertNotIn('legacy_bundle_context',value['resolutions']['S17-EXT-006']['semantic_context'])
        self.assertEqual(set(value['resolutions']['S17-EXT-006']['semantic_context']),set(replay.CONTEXT_FIELDS['S17-EXT-006']))
        self.assertTrue(proof['actual_owner_reader_completed'])

    def test_missing_required_legacy_fact_cannot_publish_a_partial_result(self):
        def missing(**kwargs):
            value=fixture();del value.resolutions['S17-EXT-006'].semantic_context['inventory_sha256'];return value
        with self.assertRaises(replay.archive.ArchiveError) as caught:self.run_reader(missing)
        self.assertFalse(caught.exception.report['actual_owner_reader_completed'])

    def test_large_console_prefix_is_bounded_and_invalidates_success(self):
        def loud(**kwargs):os.write(1,b'X'*(replay.CONSOLE_MAX+1000));return fixture()
        with self.assertRaises(replay.archive.ArchiveError) as caught:self.run_reader(loud)
        self.assertLessEqual(len(caught.exception.report['console_prefix']),replay.CONSOLE_MAX)
        self.assertFalse(caught.exception.report['actual_owner_reader_completed'])

    def test_escaped_descendant_is_reaped_and_invalidates_sealed_result(self):
        def escaped(**kwargs):
            pid=os.fork()
            if pid==0:
                os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60);os._exit(0)
            return fixture()
        with self.assertRaises(replay.archive.ArchiveError) as caught:self.run_reader(escaped)
        self.assertTrue(caught.exception.report['cleanup']['descendants_detected_after_leader_exit'])

    def test_signal_cannot_be_overridden_by_successful_child_exit(self):
        def interrupted(**kwargs):os.kill(os.getppid(),signal.SIGTERM);time.sleep(.1);return fixture()
        with self.assertRaises(replay.archive.ArchiveError) as caught:self.run_reader(interrupted)
        self.assertFalse(caught.exception.report['actual_owner_reader_completed'])

    def test_short_original_deadline_stops_and_reaps_reader(self):
        def slow(**kwargs):time.sleep(10);return fixture()
        with self.assertRaises(replay.archive.ArchiveError) as caught:self.run_reader(slow,seconds=120.15)
        self.assertTrue(caught.exception.report['cleanup']['leader_reaped'])

    def test_missing_cleanup_reserve_fails_before_fork(self):
        with mock.patch.object(os,'fork',side_effect=AssertionError('must not fork')):
            with self.assertRaisesRegex(ValueError,'deadline expired'):replay._run({},time.monotonic_ns()+1,uid=0,gid=0)

    def test_result_constructor_rejects_report_only_data(self):
        with self.assertRaisesRegex(ValueError,'only actual owner replay'):
            replay._VerifiedOriginal(token=object(),data={},report={},arguments={},anchors={})

    def anchored_fixture(self):
        temporary=tempfile.TemporaryDirectory(prefix='SOFTWARE-original-anchors-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);records=root/'records';records.mkdir();journals=root/'journal';journals.mkdir()
        refs=[];order=[1,2,3,6,4,5,7]
        for i in range(10):
            value=dict(software_fixture_only=True,ordinal=i)
            if i<7:value.update(input_id=f'S17-EXT-{order[i]:03d}',resolution_id=f'SOFTWARE-{order[i]}')
            path=records/f'record-{i}.json';raw=replay.archive.canonical(value)
            path.write_bytes(raw);refs.append(dict(path='records/'+path.name,sha256=hashlib.sha256(raw).hexdigest()))
        path=journals/'latest.json';raw=replay.archive.canonical(dict(resolution_records=refs[:7],transition_records=refs[7:]))+b'\n';path.write_bytes(raw)
        arguments=dict(latest_journal=path,journal_directory=journals,evidence_root=root)
        data=replay._project(fixture());data['latest_journal_sha256']=hashlib.sha256(raw).hexdigest()
        for i,ref in zip(order,refs[:7]):data['resolutions'][f'S17-EXT-{i:03d}']['sha256']=ref['sha256']
        anchors=replay._anchors(arguments,time.monotonic_ns()+5*10**9)
        return root,arguments,data,anchors

    def test_original_record_stamp_change_blocks_owned_view(self):
        root,args,data,anchors=self.anchored_fixture()
        # Constructor validation only, not a claim of original signature replay.
        owner=replay._VerifiedOriginal(token=replay._TOKEN,data=data,report={},arguments=args,anchors=anchors)
        self.assertFalse(owner.view().pilot_ready)
        path=root/'records/record-0.json';path.write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'changed after replay'):owner.view()

    def test_original_admission_order_can_put_ext006_before_ext004_and_ext005(self):
        root,args,data,anchors=self.anchored_fixture()
        owner=replay._VerifiedOriginal(token=replay._TOKEN,data=data,report={},arguments=args,anchors=anchors)
        self.assertEqual(owner.view().resolutions['S17-EXT-006'].sha256,data['resolutions']['S17-EXT-006']['sha256'])

    def test_original_resolution_identity_cannot_be_substituted_with_same_hash(self):
        root,args,data,anchors=self.anchored_fixture();data['resolutions']['S17-EXT-006']['resolution_id']='foreign'
        with self.assertRaisesRegex(ValueError,'resolution bytes'):
            replay._VerifiedOriginal(token=replay._TOKEN,data=data,report={},arguments=args,anchors=anchors)

    def test_changed_resolution_result_cannot_match_an_unchanged_original_journal(self):
        root,args,data,anchors=self.anchored_fixture();data['resolutions']['S17-EXT-001']['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'resolution bytes'):
            replay._VerifiedOriginal(token=replay._TOKEN,data=data,report={},arguments=args,anchors=anchors)

    def test_new_journal_file_blocks_previous_owned_view(self):
        root,args,data,anchors=self.anchored_fixture()
        owner=replay._VerifiedOriginal(token=replay._TOKEN,data=data,report={},arguments=args,anchors=anchors)
        (args['journal_directory']/'foreign.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'changed after replay'):owner.view()


if __name__=='__main__':unittest.main()
