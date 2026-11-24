import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import isolation_core as core


def states():
    return {name: dict(ActiveState="active" if name.endswith(".timer") else "inactive",
                       SubState="waiting" if name.endswith(".timer") else "dead",
                       UnitFileState="enabled" if name.endswith(".timer") else "static")
            for name in (*core.TIMER_SERVICES, *core.TIMER_SERVICES.values())}


class LifecycleTests(unittest.TestCase):
    def test_cgroup_failure_still_restores_owned_maintenance_and_retains_error(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            pre = dict(operator_config={"unit_name": "cpu-prefetch-recovery-test.service"},
                       root={"unchanged": True}, owned_masks={"apt-daily.timer": [1, 2], "apt-daily.service": [1, 3]},
                       maintenance_before=states(), maintenance_plan=core.maintenance_plan(states()))
            receipts = []
            with patch.object(core, "CONFIG", pre["operator_config"]), patch.object(core, "CG", Path(tmp)/"absent"), \
                 patch.object(core, "Q", Path(tmp)), patch.object(core, "BOOT", "boot"), \
                 patch.object(core.os, "geteuid", return_value=0), patch.object(core, "read", return_value="boot"), \
                 patch.object(core, "_restore_owned_unit", side_effect=PermissionError(13, "denied", "/owned/control")), \
                 patch.object(core, "mask_identity", side_effect=[[1, 2], [1, 3]]), \
                 patch.object(core, "command") as command, patch.object(core, "root_state", return_value=pre["root"]), \
                 patch.object(core, "systemd_state", side_effect=lambda name: states()[name]), \
                 patch.object(core, "retain", side_effect=lambda path,value: receipts.append(value)):
                with self.assertRaisesRegex(ValueError, "restoration incomplete"):
                    core.restore(pre)
            self.assertEqual(command.call_count, 4)
            command.assert_any_call("systemctl", "unmask", "--runtime", "apt-daily.timer")
            command.assert_any_call("systemctl", "unmask", "--runtime", "apt-daily.service")
            command.assert_any_call("systemctl", "start", "apt-daily.timer")
            command.assert_any_call("systemctl", "start", "apt-daily-upgrade.timer")
            self.assertTrue(receipts[0]["maintenance_restoration_verified"])
            self.assertFalse(receipts[0]["verified"])
            self.assertEqual(receipts[0]["errors"][0]["errno"], 13)

    def test_remaining_keeper_time_covers_actual_family_not_just_original_duration(self):
        with patch.object(core, "CONFIG", {"protected_work_ns": 150, "stop_seconds": 1}), \
             patch.object(core.time, "monotonic_ns", return_value=100):
            core.verify_remaining_lifetime({"keeper_deadline_monotonic_ns": 10**9 + 251}, 100, 50)
            with self.assertRaises(ValueError):
                core.verify_remaining_lifetime({"keeper_deadline_monotonic_ns": 10**9 + 250}, 100, 50)
            with self.assertRaises(ValueError):
                core.verify_remaining_lifetime({"keeper_deadline_monotonic_ns": 10**12}, 151, 1)

    def test_supported_unit_has_delegate_and_no_unsupported_partition_property(self):
        text = core.unit_text("cpu-prefetch-recovery-v23.service", "/opt/recovery/isolation_core.py", 1000, 120)
        for row in ("Slice=-.slice", "Delegate=cpuset", "DelegateSubgroup=supervisor", "CPUAffinity=3", "Restart=no"):
            self.assertIn(row, text)
        self.assertNotIn("CPUSetPartition=", text)
        with self.assertRaises(ValueError):
            core.unit_text("evil\n.service", "/x", 100, 10)

    def test_active_apt_service_blocks_before_mutations(self):
        original = states()
        original["apt-daily.service"]["ActiveState"] = "activating"
        with self.assertRaisesRegex(ValueError, "maintenance"):
            core.maintenance_plan(original)

    def test_original_disabled_masked_states_are_not_enabled_or_unmasked(self):
        original = states()
        original["apt-daily.timer"].update(ActiveState="inactive", SubState="dead", UnitFileState="masked")
        plan = core.maintenance_plan(original)
        self.assertNotIn("apt-daily.timer", plan["add_runtime_masks"])
        self.assertEqual(plan["restart_timers"], ["apt-daily-upgrade.timer"])
        commands = core.restore_maintenance_commands(plan)
        self.assertEqual(commands[-1], ["systemctl", "start", "apt-daily-upgrade.timer"])
        self.assertFalse(any("enable" in c or "disable" in c for c in commands))

    def test_missing_control_is_not_created(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            path = Path(tmp) / "cpuset.cpus.partition"
            with self.assertRaises(FileNotFoundError):
                core.write_control(path, "member")
            self.assertFalse(path.exists())

    def cleanup_fixture(self, *, missing=False, enabled=False, populated=False, denied=False):
        tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "reserved"
        path.mkdir()
        st = path.stat()
        values = {path / "cgroup.procs": "7" if populated else "",
                  path / "cgroup.events": "populated 1" if populated else "populated 0",
                  path.parent / "cgroup.subtree_control": "cpuset" if enabled else "",
                  path / "cpuset.cpus.partition": "isolated"}
        writes, removed = [], []
        def read(p):
            if p.name == "cpuset.cpus.partition":
                if denied:
                    raise PermissionError(13, "denied", str(p))
                if missing:
                    raise FileNotFoundError(2, "missing", str(p))
            return values[p]
        def write(p, value):
            writes.append((p, value))
            values[p] = value
        return path, (st.st_dev, st.st_ino), dict(reader=read, writer=write, remove=removed.append), writes, removed

    def test_missing_controller_empty_owned_partition_removed_without_write(self):
        path, identity, ops, writes, removed = self.cleanup_fixture(missing=True)
        result = core.remove_empty_partition(path, identity, **ops)
        self.assertTrue(result["controller_already_absent"])
        self.assertEqual(writes, [])
        self.assertEqual(removed, [path])

    def test_present_control_demoted_before_remove(self):
        path, identity, ops, writes, removed = self.cleanup_fixture(enabled=True)
        core.remove_empty_partition(path, identity, **ops)
        self.assertEqual(writes, [(path / "cpuset.cpus.partition", "member")])
        self.assertEqual(removed, [path])

    def test_live_tasks_replaced_inode_and_permission_failure_reject(self):
        for kind in ("populated", "denied", "identity", "enabled_missing"):
            with self.subTest(kind=kind):
                path, identity, ops, writes, removed = self.cleanup_fixture(
                    populated=kind == "populated", denied=kind == "denied",
                    enabled=kind == "enabled_missing", missing=kind == "enabled_missing")
                if kind == "identity":
                    identity = (identity[0], identity[1] + 1)
                with self.assertRaises((ValueError, PermissionError)):
                    core.remove_empty_partition(path, identity, **ops)
                self.assertEqual(writes, [])
                self.assertEqual(removed, [])

    def test_reload_requires_same_inode_and_real_isolation(self):
        before = dict(partition="isolated", cpus=core.CPU_LIST, effective=core.CPU_LIST,
                      exclusive=core.CPU_LIST, exclusive_effective=core.CPU_LIST,
                      root_isolated=core.CPU_LIST, mems_effective="0-1",
                      root_effective="3-7,9-15,19-23,25-31", root_subtree_control="cpu cpuset memory pids",
                      unit_subtree_control="cpuset", supervisor_affinity=[3],
                      outside_effective={"init.scope": "3-7,9-15,19-23,25-31"},
                      boot_id="boot", control_identities={"x": [1, 2]}, partition_path="/owned/reserved")
        core.verify_reload(before, copy.deepcopy(before))
        for field, value in (("control_identities", {"x": [1, 3]}), ("partition", "isolated invalid"),
                             ("root_subtree_control", "cpu memory pids"), ("boot_id", "other")):
            after = copy.deepcopy(before)
            after[field] = value
            with self.assertRaises(ValueError):
                core.verify_reload(before, after)


if __name__ == "__main__":
    unittest.main()
