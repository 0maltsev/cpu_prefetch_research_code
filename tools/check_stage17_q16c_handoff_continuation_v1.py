"""Read-only installed D306 admission; never signs operational authority or arms."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import stage17_q16c_handoff_continuation_v1 as resume
import stage17_q16c_continuation_study_v1 as study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--configuration-sha256', required=True)
    args = parser.parse_args()
    ops = Path(__file__).resolve().parent
    c, owned = study.configure(args)
    resume.require(ops == resume.E/'d306-continuation-1' and args.configuration == ops/'launch-configuration.json',
                   'actual unsigned configuration and installed operator paths')
    resume.check_time(time.monotonic_ns(), c)
    record = resume.admit(args, c, software_check=True)
    resume.require(record['global_deadline_ns'] == resume.runtime_deadline(c) == 1636624784571258,
                   'original signed day unchanged')
    clock = study.module('d306_readonly_isolation', c['clock_adapter'])
    resume.require(clock.Q == resume.E/'clock-rearm-d306-1' and not clock.Q.exists(), 'unused isolation receipt namespace')
    resume.require(clock.BINDINGS['isolation_config'] == study.io.document(c['qualification_isolation_configuration']),
                   'exact actual isolation configuration')
    resume.require(not Path(clock.BINDINGS['isolation_config']['evidence_root']).exists() and not clock.CG.exists()
                   and not (Path('/run/systemd/system')/clock.BINDINGS['isolation_config']['unit_name']).exists(),
                   'fresh isolation paths and absent native partition')
    resume.require(Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip() == '1', 'guard restored')
    for name in ('d306-study-1', 'platform-guard-d306-1', 'platform-observations-d306-1', 'q16c-study-d306-1',
                 'd306-independent-recovery-1.json'):
        resume.require(not (resume.E/name).exists(), 'unused '+name)
    for unit in ('cpu-prefetch-d301-v32-1.service', 'cpu-prefetch-d306-v32-1.service'):
        text = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '-p', 'ControlGroup'], text=True)
        facts = dict(line.split('=', 1) for line in text.splitlines())
        resume.require(facts['MainPID'] == '0' and facts['ControlGroup'] == '', 'no active '+unit)
    resume.validate_handoff(c)
    template = study.io.document(c['authorization_template']); schema = study.io.document(c['authorization_schema'])
    now = dt.datetime.now(dt.timezone.utc); endpoint = resume.saved.deadline_utc(c)
    resume.require(endpoint == dt.datetime(2026, 11, 20, 18, 41, 30, 487744, tzinfo=dt.timezone.utc), 'unchanged UTC endpoint')
    draft = resume.saved.finalize_template(template, now, schema, endpoint)
    resume.require(all(draft[k] == v for k, v in template.items() if k not in ('issued_at_utc', 'expires_at_utc')),
                   'only two authority times refreshed in memory')
    mem = int(next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')).split()[1])*1024
    fs = os.statvfs(resume.E); free = fs.f_bavail*fs.f_frsize
    resume.require(mem >= 112*1024**3 and free >= (512+256+16)*1024**3, 'actual unchanged memory and filesystem reserves')
    resume.check_time(time.monotonic_ns(), c)
    result = dict(status='D306_ACTUAL_INSTALLED_ADMISSION_PASS', checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        configuration_sha256=args.configuration_sha256, administrative_source_revision=c['administrative_source_revision'],
        qualified_native_source_revision=c['source_revision'], current_qualification_and_owner_verified=True,
        d301_d302_d306_owner_signatures_verified=True, retained_reports_verified=86, measured_libraries_verified=9,
        full_quiescent_ledger_replay_verified=True, empty_registered_family_verified=True,
        stopped_signed_handoff_preserved=True, fresh_output_and_authority_paths_verified=True,
        hardware_prestate_verified=True, available_memory_bytes=mem, free_filesystem_bytes=free,
        full_remaining_envelope_seconds=31460, admitted_day_deadline_ns=record['global_deadline_ns'],
        launch_permitted=False, operational_authority_signed=False, controls_rearmed=False,
        new_execution_window=False, execution_authority=False, phase18_authority=False)
    study.io.save(ops/'prelaunch-check.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
