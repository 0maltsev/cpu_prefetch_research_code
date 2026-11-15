"""Bind concrete stand inputs only; does not sign/register/set up/launch."""
from pathlib import Path
import argparse
import json
import os

import formal_launch_q16b as launch
import q16b_contract as fixed


def exclusive(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def render(stage, packet_manifest_sha256):
    files = {name: launch.bound(path) for name, path in fixed.input_paths(stage).items()}
    plan = json.loads(launch.read_bound(files['plan']))
    proof = json.loads(launch.read_bound(files['preparation']))
    launch.require(files['plan']['sha256'] == fixed.PLAN_SHA, 'exact candidate-3 plan required')
    mapped = max(row['resources']['total_mapping_bytes'] for row in plan['captures'])
    requested = launch.limits(plan, proof, proof['required_worker_as_bytes'], mapped)
    manifest = launch.bound(fixed.ADMIN / 'manifest.json')
    launch.require(manifest['sha256'] == packet_manifest_sha256, 'explicit reviewed packet hash differs')
    launch.require(json.loads(launch.read_bound(manifest))['schema_version'] == fixed.ADMIN_SCHEMA, 'v2 packet schema required')
    bootstrap = launch.bound(fixed.ADMIN / (fixed.ADMIN_MODULE + '.py'))
    c = dict(fixed.paths(), schema_version='software-formal-q16b-launch/1', stage=stage,
             uid=1000, gid=1000, controller_cpu=2, supervisor_cpu=3,
             files=files, requested_limits=requested,
             setpriv_binding=launch.bound('/usr/bin/setpriv'), admin_root=str(fixed.ADMIN),
             admin_bootstrap=bootstrap, packet_manifest=manifest,
             launcher_sha256=launch.bound(Path(launch.__file__).resolve())['sha256'],
             contract_sha256=launch.bound(Path(fixed.__file__).resolve())['sha256'],
             setup_helper_sha256=launch.bound(Path(__file__).resolve().with_name('reapply_isolation_q16b.py'))['sha256'],
             setup_scope=dict(action_id='Q16b', plan_sha256=fixed.PLAN_SHA,
                              prior_D243_consumed=True, qualification_repeat=False, automatic_retry=False))
    # No runtime modules are activated during rendering; signature/journal and
    # hardware/resources are freshly verified by the owner entry immediately
    # before setup and again before launching the sole execution child.
    return c


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('prelaunch', 'launch'), required=True)
    parser.add_argument('--packet-manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    launch.require(args.output.parent == fixed.OPERATORS, 'configuration output must be in owned operator directory')
    launch.require(not fixed.LAUNCH.exists(), 'launch namespace already consumed')
    c = render(args.stage, args.packet_manifest_sha256)
    raw = launch.canonical(c)
    exclusive(args.output, raw)
    print(json.dumps(dict(launch.bound(args.output), requested_limits=c['requested_limits'],
                          execution_authority=False), sort_keys=True))


if __name__ == '__main__':
    main()
