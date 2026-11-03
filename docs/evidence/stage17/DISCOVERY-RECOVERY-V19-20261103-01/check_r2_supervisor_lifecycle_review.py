"""Local AST-branch lifecycle checks; never import or execute stand setup."""
import ast
import contextlib
import datetime
import hashlib
import io
import json
import pathlib
import tempfile
import types
import unittest

SOURCE = pathlib.Path(__file__).with_name('start-discovery-r2.py')
DATA = SOURCE.read_bytes()
TREE = ast.parse(DATA, filename=str(SOURCE))
BRANCH = next(n for n in TREE.body if isinstance(n, ast.If))
CODE = compile(ast.fix_missing_locations(ast.Module(body=[BRANCH], type_ignores=[])), str(SOURCE), 'exec')

class Lifecycle(unittest.TestCase):
    def run_case(self, mode='--supervise', failure=None):
        with tempfile.TemporaryDirectory(prefix='r2-supervisor-mock-') as temp:
            root = pathlib.Path(temp)
            output = root / 'output'; output.mkdir()
            cg = root / 'cg'; cg.mkdir(); (cg / 'cgroup.procs').write_text('')
            iso = root / 'isolation'; iso.mkdir()
            prestate = {'original': 'exact'}
            (iso / 'prestate.json').write_text(json.dumps({'prestate': prestate}))
            prep = root / 'preparation'; prep.mkdir()
            pc = {'available_bytes': 388544851990, 'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            (prep / 'pc-prelaunch-capacity-r2-1.json').write_text(json.dumps(pc))
            events = []; handlers = {}; retained = {}; counts = {'spawn': 0, 'wait': 0, 'restore': 0}
            class Child:
                pid = 123
                returncode = None
                def poll(self): return self.returncode
                def wait(self):
                    counts['wait'] += 1
                    events.append('wait')
                    if failure == 'signals' and counts['wait'] == 1:
                        handlers[15](15, None)
                    if failure == 'signals':
                        handlers[15](15, None); handlers[1](1, None)
                    self.returncode = 7 if failure == 'worker' else 0
                    if self.returncode == 0:
                        (output / 'mock-completion-v5.json').write_text('{}')
                    events.append('reaped')
                    return self.returncode
            child = Child()
            def spawn(*args, **kwargs):
                counts['spawn'] += 1
                events.append('spawn')
                if failure == 'popen': raise OSError('mock Popen failure')
                return child
            def checks():
                events.append('checks')
                if failure == 'checks': raise RuntimeError('mock checks failure')
                return {'pc_check': pc}
            def restore(value):
                self.assertEqual(value, prestate)
                if mode == '--supervise' and counts['spawn'] and failure != 'popen':
                    self.assertIsNotNone(child.returncode, 'restoration before child reaped')
                counts['restore'] += 1; events.append('restore')
                if failure == 'signals': handlers[2](2, None)
                (iso / 'restoration.json').write_text('{"verified":true}')
            def retain(path, value):
                self.assertNotIn(path.name, retained)
                retained[path.name] = json.loads(json.dumps(value))
            fake_signal = types.SimpleNamespace(SIGTERM=15, SIGHUP=1, SIGINT=2,
                signal=lambda number, handler: handlers.__setitem__(number, handler))
            env = dict(E=root, D=root, O=output, isolation=types.SimpleNamespace(Q=iso, CG=cg, restore=restore),
                pathlib=pathlib, json=json, datetime=datetime, signal=fake_signal,
                sys=types.SimpleNamespace(argv=['mock'] + ([mode] if mode else [])),
                os=types.SimpleNamespace(sched_setaffinity=lambda *args: events.append('affinity'), getpid=lambda: 99),
                subprocess=types.SimpleNamespace(Popen=spawn, DEVNULL=-1, STDOUT=-2),
                checks=checks, retain=retain, command=lambda: ['mock-command'], binding=lambda p: {},
                utc=lambda: '2026-11-03T00:00:00Z', __file__=str(SOURCE))
            error = None
            with contextlib.redirect_stdout(io.StringIO()):
                try: exec(CODE, env)
                except BaseException as exc: error = exc
            result = retained.get('discovery-supervisor-result-r2-1.json')
            return counts, result, error, events

    def test_success(self):
        c, r, e, _ = self.run_case()
        self.assertIsNone(e); self.assertEqual(c, {'spawn': 1, 'wait': 1, 'restore': 1})
        self.assertTrue(r['success']); self.assertTrue(r['partition_restoration']['verified'])

    def test_nonzero_worker(self):
        c, r, e, _ = self.run_case(failure='worker')
        self.assertIsNone(e); self.assertEqual(c['spawn'], 1); self.assertEqual(c['restore'], 1)
        self.assertFalse(r['success']); self.assertEqual(r['exit_code'], 7)

    def test_supervisor_prelaunch_check_failure(self):
        c, r, e, _ = self.run_case(failure='checks')
        self.assertIsNone(e); self.assertEqual(c['spawn'], 0); self.assertEqual(c['restore'], 1)
        self.assertFalse(r['success']); self.assertTrue(r['supervisor_errors'])

    def test_supervisor_popen_failure(self):
        c, r, e, _ = self.run_case(failure='popen')
        self.assertIsNone(e); self.assertEqual(c, {'spawn': 1, 'wait': 0, 'restore': 1})
        self.assertFalse(r['success'])

    def test_repeated_signals_during_cleanup(self):
        c, r, e, _ = self.run_case(failure='signals')
        self.assertIsNone(e); self.assertEqual(c, {'spawn': 1, 'wait': 2, 'restore': 1})
        self.assertFalse(r['success']); self.assertEqual(len(r['supervisor_errors']), 4)

    def test_outer_prelaunch_check_failure(self):
        c, r, e, _ = self.run_case(mode='', failure='checks')
        self.assertIsInstance(e, RuntimeError); self.assertEqual(c['spawn'], 0); self.assertEqual(c['restore'], 1)

    def test_outer_popen_failure(self):
        c, r, e, _ = self.run_case(mode='', failure='popen')
        self.assertIsInstance(e, OSError); self.assertEqual(c['spawn'], 1); self.assertEqual(c['restore'], 1)

    def test_outer_hands_cleanup_to_one_supervisor(self):
        c, r, e, _ = self.run_case(mode='')
        self.assertIsNone(e); self.assertEqual(c, {'spawn': 1, 'wait': 0, 'restore': 0})

if __name__ == '__main__':
    print('Reviewed source SHA256:', hashlib.sha256(DATA).hexdigest(), flush=True)
    unittest.main(verbosity=2)
