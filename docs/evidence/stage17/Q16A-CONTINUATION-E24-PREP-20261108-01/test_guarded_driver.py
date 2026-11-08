"""Bounded operator checks; no stand, hardware, signing or subprocess execution."""
import contextlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import run_qualification_v24_guarded as driver


class DriverTests(unittest.TestCase):
    def test_publication_between_read_and_exit_is_accepted(self):
        path = Mock()
        path.read_bytes.side_effect = [FileNotFoundError(), b'{"complete":true}']
        process = Mock()
        process.poll.return_value = 0
        self.assertEqual(driver.wait_result(path, process, driver.time.monotonic()+2),
                         {'complete': True})
        self.assertEqual(path.read_bytes.call_count, 2)

    def test_incomplete_json_waits_only_while_producer_alive(self):
        path = Mock()
        path.read_bytes.side_effect = [b'{', b'{"complete":true}']
        process = Mock()
        process.poll.return_value = None
        with patch.object(driver.time, 'sleep') as sleep:
            self.assertEqual(driver.wait_result(path, process, driver.time.monotonic()+2),
                             {'complete': True})
        sleep.assert_called_once()

    def test_missing_or_malformed_final_result_fails(self):
        for failure in (FileNotFoundError(), b'{'):
            path = Mock()
            if isinstance(failure, Exception):
                path.read_bytes.side_effect = failure
            else:
                path.read_bytes.return_value = failure
            process = Mock()
            process.poll.return_value = 1
            with self.assertRaisesRegex(RuntimeError, 'without a complete result'):
                driver.wait_result(path, process, driver.time.monotonic()+2)

    def test_deadline_precedes_result_wait(self):
        path = Mock()
        with self.assertRaisesRegex(RuntimeError, 'deadline expired'):
            driver.wait_result(path, Mock(), driver.time.monotonic()-1)
        path.read_bytes.assert_not_called()

    def packet(self):
        packet = driver.Packet({'files': []}, {'qualification_budget_seconds': 1,
                                              'q15_quiescence_seconds': 2100})
        packet.deadline = driver.time.monotonic()-1
        packet.argv = Mock(return_value=['NEVER_EXECUTE'])
        return packet

    def test_expired_step_never_spawns(self):
        with tempfile.TemporaryDirectory() as temporary:
            with (patch.object(driver, 'E', Path(temporary)),
                  patch.object(driver, 'retain'),
                  patch.object(driver.subprocess, 'Popen') as spawn):
                with self.assertRaisesRegex(RuntimeError, 'deadline expired'):
                    self.packet().step('fixture')
                spawn.assert_not_called()

    def test_expired_persistent_session_never_spawns(self):
        packet = self.packet()
        packet.step = Mock()
        isolation = types.SimpleNamespace(qualification_guard=lambda **kw: contextlib.nullcontext())
        with tempfile.TemporaryDirectory() as temporary:
            with (patch.object(driver, 'E', Path(temporary)),
                  patch.object(driver, 'retain'),
                  patch.object(driver.subprocess, 'Popen') as spawn):
                with self.assertRaisesRegex(RuntimeError, 'deadline expired'):
                    packet.qualify(isolation)
                spawn.assert_not_called()
                self.assertEqual(packet.step.call_count, 3)


if __name__ == '__main__':
    unittest.main()
