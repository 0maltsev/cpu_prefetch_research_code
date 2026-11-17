"""The actual qualification terminal tuple is mandatory; no retry handoff."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import launch_stage17_q16c_after_qualification_v1 as current


class HandoffTests(unittest.TestCase):
    def test_only_successful_retained_unconsumed_qualification_can_finalize(self):
        good=dict(success=True,formal_capture_started=False,isolation_retained_for_formal=True)
        self.assertTrue(current.finalized(dict(files={}),good))
        for change in (dict(success=False),dict(formal_capture_started=True),dict(isolation_retained_for_formal=False)):
            with self.assertRaisesRegex(ValueError,'successful retained'):current.finalized(dict(files={}),dict(good,**change))
        with self.assertRaisesRegex(ValueError,'already finalized'):
            current.finalized(dict(files=dict(qualification_complete={})),good)


if __name__=='__main__':unittest.main()
