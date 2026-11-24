"""Exact prospective Q16b operator contract; importing has no stand effects."""
from pathlib import Path

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
OLD = E.parent / 'local-authoring-cpuprefetchv5-23'
PROGRAM = OLD / 'formal-archive-program-1'
PREPARATION = E / 'formal-q16b-preparation-2'
OPERATORS = E / 'q16b-launch-admission-3'
ISOLATION = E / 'isolation-preparation-v25-q16b-3'
LAUNCH = E / 'formal-q16b-launch-3'
AUTH = E / 'admission-root/evidence/formal-q16b-2'
CORE = Path('/run/cpu-prefetch-recovery-v25-qualified-1/isolation_core.py')
ADMIN = E / 'q16b-admission-operators-5'
ADMIN_MODULE = 'stage17_formal_admin_v3'
ADMIN_SCHEMA = 'cpu-prefetch-stage17-formal-admin-packet/3'
CORE_SHA = '49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
PLAN_SHA = '6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
SOURCE = '42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
WORKER_SHA = '7abf4cfac0051103f98b3f63f37efd1bde757d954c973460be6fe4d245f6a275'
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
SCOPE_SHA = '4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2'
BUNDLE_NAME = 'cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a'
BUNDLE = E / 'local-bundle-extract' / BUNDLE_NAME
ARCHIVE = E.parent / (BUNDLE_NAME + '.tar.gz')
RESERVED = frozenset((0, 1, 2, 8, 16, 17, 18, 24))
UNIT = 'cpu-prefetch-recovery-v25-qualified-1.service'
PARTITION = Path('/sys/fs/cgroup') / UNIT / 'reserved'

# Requested engineering ceilings, not measured platform quantities. 162 days
# leaves finite preparation slack beyond the 160.0403-day family watchdog.
LIFECYCLE_SECONDS = 162 * 24 * 60 * 60
STOP_SECONDS = 120
WATCHDOG_NS = 13827480000000000
CLEANUP_NS = 120000000000
# Explicit prospective engineering guard accepted in the current task. This
# supplements the native plan; it does not alter any frozen plan bytes.
OPERATIONAL_MEMORY_RESERVE_BYTES = 8 * 1024**3


def isolation_config(plan):
    if plan['budget']['watchdog_ns'] != WATCHDOG_NS or plan['budget']['cleanup_ns'] != CLEANUP_NS:
        raise ValueError('candidate family watchdog/cleanup changed')
    return dict(unit_name=UNIT, source_revision=SOURCE, boot_id=BOOT,
                lifecycle_seconds=LIFECYCLE_SECONDS, stop_seconds=STOP_SECONDS,
                protected_work_ns=WATCHDOG_NS + CLEANUP_NS, evidence_root=str(ISOLATION))


def paths():
    """Every fixed locator is concrete; the separately supplied bridge is bound later."""
    return dict(repository_root=str(E / 'admission-root'), evidence_root=str(E),
                bundle_root=str(BUNDLE), program_root=str(PROGRAM), launch_root=str(LAUNCH),
                archive=str(ARCHIVE), sidecar=str(ARCHIVE) + '.sha256',
                python='/usr/bin/python3.14', setpriv='/usr/bin/setpriv')


def input_paths(stage):
    files = dict(plan=PREPARATION / 'plan.json', preparation=PREPARATION / 'preparation.json',
                 request=AUTH / 'request.json', authorization=AUTH / 'authorization.json',
                 signature=AUTH / 'authorization.json.sig',
                 admission=OLD / 'formal-program-storage-admission-1.json',
                 scope=PROGRAM / 'scope.json',
                 parent_plan=OLD / 'formal-q16a-authoring-v23-1/plan.json',
                 profile=E / 'q16b-native-archive-bundle-3/config/stage17/formal-archive-implementation-profile-v1.json',
                 manifest=BUNDLE / 'BUNDLE_MANIFEST.json',
                 isolation_operator=CORE, isolation_config=OPERATORS / 'isolation-config.json',
                 clock_complete=E / 'clock-qualification-v25-1/complete.json',
                 clock_plan=E / 'clock-qualification-v25-1/prospective-plan.json',
                 q15_result=E / 'stage17-q15-w-result-v4.json',
                 q15_completion=E / 'stage17-q15_w-completion-v4.json',
                 handoff=E / 'q16b-handoff-preparation-1/q16a-handoff.json',
                 capacity_proof=PREPARATION / 'stand-program-capacity.json',
                 upgrade_stop=E / 'q16b-archive-upgrade-stop-1/restoration-audit-2.json')
    if stage == 'launch':
        files.update(isolation_prestate=ISOLATION / 'prospective-prestate.json',
                     isolation_readback=ISOLATION / 'q16b-reapplication-handoff.json')
    elif stage != 'prelaunch':
        raise ValueError('unknown stage')
    return {key: str(value) for key, value in files.items()}
