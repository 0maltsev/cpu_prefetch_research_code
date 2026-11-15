"""Prospective Q16b-only setup using unchanged reviewed isolation core.

This file authors no authority. --prepare requires an exact fresh signed Q16b
request, registered empty family, authenticated packet, and live resources.
"""
from pathlib import Path
import argparse
import json
import os
import signal
import types

import q16b_contract as fixed
import formal_launch_q16b as launch


def hardware(plan, expected, topology):
    """Requested NUMA/MSR state and actual readbacks remain separate."""
    observations = {}
    launch.require(set(map(int, topology)) == set(fixed.RESERVED), 'exact qualified reserved SMT inventory required')
    for cpu, siblings in topology.items():
        actual = (Path('/sys/devices/system/cpu') / ('cpu' + cpu) / 'topology/thread_siblings_list').read_text().strip()
        launch.require(actual == siblings, 'qualified SMT topology changed: ' + cpu)
        observations[cpu] = dict(requested_thread_siblings_list=siblings, observed_thread_siblings_list=actual)
    placements = set()
    for row in plan['captures']:
        g = row['capture']['geometry']
        placements.update((g[role + '_cpu'], g[role + '_node']) for role in ('producer', 'consumer'))
        s = row['resources']['controller_stack']
        placements.add((s['owner_cpu'], s['requested_node']))
    launch.require(placements == {(0, 0), (1, 0), (8, 1), (2, 0)}, 'frozen near0/1 far0/8 placements differ')
    for cpu, node in placements:
        p = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu))
        actual = sorted(v.name for v in p.glob('node*'))
        launch.require(actual == ['node' + str(node)], 'NUMA placement changed: ' + str(cpu))
        observations[str(cpu)].update(requested_numa_node=node, observed_numa_node=node)
    launch.require(len(expected) == 3 and {r['cpu'] for r in expected} == {0, 1, 8}, 'exact signed MSR CPU coverage required')
    msrs = []
    for row in expected:
        cpu = row['cpu']
        fd = os.open('/dev/cpu/' + str(cpu) + '/msr', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            raw = os.pread(fd, 8, 0x1a4)
        finally:
            os.close(fd)
        launch.require(len(raw) == 8, 'short MSR read')
        actual = f'{int.from_bytes(raw, "little"):016x}'
        launch.require(actual == row['complete_value_hex'], 'MSR prestate differs: ' + str(cpu))
        msrs.append(dict(cpu=cpu, expected_hex=row['complete_value_hex'], observed_hex=actual, matches=True))
    return dict(topology=observations, msr_readback=msrs)


def prepare(c, args):
    launch.require(os.geteuid() == 0 and c['stage'] == 'prelaunch', 'root and prelaunch-stage config required')
    launch.require(not fixed.ISOLATION.exists() and not fixed.LAUNCH.exists(), 'Q16b setup/launch namespace consumed; no retry')
    os.sched_setaffinity(0, {c['supervisor_cpu']})
    # Owner checks authenticate old source/D242 closure and the new packet, and
    # verify the NEW signature/journal, resources, topology, prestate and family.
    admitted = launch.checks(c, args)
    d, _, _ = launch.documents(c, args)
    raw = launch.read_bound(c['files']['isolation_operator'])
    launch.require(launch.digest(raw) == fixed.CORE_SHA, 'original core hash differs')
    core = types.ModuleType('q16b_unchanged_core')
    core.__file__ = str(fixed.CORE)
    exec(compile(raw, core.__file__, 'exec'), core.__dict__)
    before = hardware(d['plan'], d['preparation']['hardware_control']['prestate'], d['clock_plan']['topology'])
    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(signum, launch.interrupted)
    pre = None
    try:
        pre = core.prepare(d['isolation_config'])
        after = hardware(d['plan'], d['preparation']['hardware_control']['prestate'], d['clock_plan']['topology'])
        launch.require(before == after, 'hardware changed across Q16b isolation setup')
        observation = core.isolated_state()
        core.verify_remaining_lifetime(pre['prestate'], d['plan']['budget']['watchdog_ns'], d['plan']['budget']['cleanup_ns'])
        launch.require(observation['partition']['cgroup.procs'] == ''
                       and 'populated 0' in observation['partition']['cgroup.events'].splitlines(), 'new partition is not empty')
        core.retain(fixed.ISOLATION / 'q16b-reapplication-handoff.json', dict(
            utc=core.utc(), action_id='Q16b', plan_sha256=fixed.PLAN_SHA,
            setup_scope=c['setup_scope'], isolation_reapplied=True, qualification_repeated=False,
            source_revision=fixed.SOURCE, boot_id=fixed.BOOT, partition_path=str(core.CG),
            configuration_sha256=c['files']['isolation_config']['sha256'],
            isolation_prestate_sha256=launch.bound(fixed.ISOLATION / 'prospective-prestate.json')['sha256'],
            authority_binding=c['files']['authorization'], signature_binding=c['files']['signature'],
            packet_manifest=c['packet_manifest'], hardware_before=before, hardware_after=after,
            read_only_prelaunch_admission=admitted, observation=observation,
            operator_sha256=launch.bound(Path(__file__).resolve())['sha256']))
        return dict(status='Q16B_ISOLATION_REAPPLIED_VERIFIED', evidence_root=str(fixed.ISOLATION),
                    qualification_repeated=False, execution_authority=False)
    except BaseException:
        # core.prepare owns its partial-state cleanup if it raises before return.
        # Once it returned, this wrapper owns cleanup on any subsequent failure.
        if pre is not None:
            for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                signal.signal(signum, signal.SIG_IGN)
            core.restore(pre['prestate'])
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--address-space-bytes', type=int, required=True)
    parser.add_argument('--memlock-bytes', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(launch.read_config(args), args), sort_keys=True))


if __name__ == '__main__':
    main()
