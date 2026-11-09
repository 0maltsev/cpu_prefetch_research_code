import ast
import importlib.util
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch,MagicMock

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(HERE),str(HERE.parent/'d242-admin-1')]
import formal_launch_v2 as launcher


class AllowanceTests(unittest.TestCase):
    def setUp(self):
        self.config={'uid':1000,'gid':1000,'setpriv':'/usr/bin/setpriv','python':'/usr/bin/python3.14'}
        self.args=SimpleNamespace(config=Path('/software/config.json'),config_sha256='a'*64,
                                  address_space_bytes=240518168576,memlock_bytes=25769803776)

    def test_finite_allowance_and_original_credentials_preserved(self):
        process=MagicMock(pid=123,returncode=0)
        process.communicate.return_value=(b'{"execution_authority":false,"configuration_sha256":"'+b'a'*64+b'","owner_uid":1000}',b'')
        with patch.object(launcher.subprocess,'Popen',return_value=process) as popen:
            result=launcher.owner_check(self.config,self.args)
        process.communicate.assert_called_once_with(timeout=600)
        process.wait.assert_called_once_with(timeout=10)
        self.assertIn('--clear-groups',popen.call_args.args[0]);self.assertEqual(result['owner_uid'],1000)

    def test_timeout_kills_only_owned_group_and_reaps(self):
        process=MagicMock(pid=123,returncode=None)
        process.communicate.side_effect=subprocess.TimeoutExpired('software-only',600)
        with patch.object(launcher.subprocess,'Popen',return_value=process),patch.object(launcher.os,'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):launcher.owner_check(self.config,self.args)
        kill.assert_called_once_with(123,signal.SIGKILL);process.wait.assert_called_once_with(timeout=10)

    def test_original_measured_cli_destination_preserved(self):
        config=dict(self.config,repository_root='/original/repository',evidence_root='/original/evidence',
            files={'authorization':{'path':'/authority'},'signature':{'path':'/signature'}},archive='/archive',sidecar='/sidecar')
        argv=launcher.cli_command(config)
        self.assertEqual(argv[2],str(launcher.d242.ADMIN/'stage17_operational_cli_v19.py'))
        self.assertEqual(argv[3],'execute-formal')

    def test_only_intended_launcher_changes(self):
        original=(HERE.parent/'d242-admin-1/formal_launch.py').read_text()
        updated=(HERE/'formal_launch_v2.py').read_text()
        bootstrap="import sys\nfrom pathlib import Path\nsys.path.insert(0, '/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25/d242-admin-1')\nimport stage17_state_journal_v53 as d242"
        recovered=updated.replace(bootstrap,'import stage17_state_journal_v53 as d242',1)
        recovered=recovered.replace('process.communicate(timeout=600)','process.communicate(timeout=180)')
        recovered=recovered.replace("str(d242.ADMIN/'stage17_operational_cli_v19.py')","str(Path(__file__).resolve().parent/'stage17_operational_cli_v19.py')")
        self.assertEqual(recovered,original)
        for p in HERE.glob('*.py'):ast.parse(p.read_text())


if __name__=='__main__':unittest.main()
