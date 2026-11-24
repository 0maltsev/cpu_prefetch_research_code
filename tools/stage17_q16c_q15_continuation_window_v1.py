"""D276 one corrected first-native Q15 session; the original study day stays fixed."""
import stage17_q16c_window_v1 as original

NS=original.NS
QUALIFICATION=1800
FAMILY=original.FAMILY
ANALYSIS=original.ANALYSIS
RESTORATION=original.RESTORATION
SUCCESS_ENVELOPE_SECONDS=QUALIFICATION+FAMILY+ANALYSIS+RESTORATION


def require(ok,message):
    if not ok:raise ValueError('Q16c Q15 continuation: '+message)


def validate(record,*,now,qualification=False):
    original.validate(record,now=now)
    if qualification:require(now+SUCCESS_ENVELOPE_SECONDS*NS<record['global_deadline_ns'],
        'full corrected qualification and unchanged downstream envelope cannot fit')
    return record['global_deadline_ns']-now


def infrastructure(record,configuration,*,now):
    validate(record,now=now,qualification=True)
    require(configuration['boot_id']==record['boot_id']
        and configuration['source_revision']==record['software_source_revision'],'actual source and boot')
    life=configuration['lifecycle_seconds'];protected=configuration['protected_work_ns']
    # The keeper is restored before offline analysis. The complete global
    # envelope above still charges analysis and restoration in full.
    require(type(life) is int and type(protected) is int and protected>=(QUALIFICATION+FAMILY)*NS,
        'whole corrected protected work declaration')
    require(life*NS>protected+configuration['stop_seconds']*NS,'insufficient finite keeper lifetime')
    require(now+(life+RESTORATION)*NS<=record['global_deadline_ns'],'keeper exceeds original restoration reserve')
    return True


def verify_retained(*,clocks,failed_launch,terminal,restoration,owner,attempt_files,source_revision,worker_sha256):
    require(clocks.get('both_pairs_passed') is True,'both original clock runs must pass')
    require(failed_launch.get('formal_capture_started') is False and failed_launch.get('automatic_retry') is False
        and failed_launch.get('error')=="RuntimeError('persistent Q15 session exited without a complete result: 1')",
        'exact stopped prelaunch incident')
    require(terminal.get('exit_code')==1 and terminal.get('leader_reaped') is True
        and terminal.get('cleanup_error') is None,'original controller reaped without cleanup error')
    require(restoration.get('verified') is True and restoration.get('partition_absent') is True,'actual prior restoration')
    require(owner.get('status')=='PASS' and owner.get('verified_execution_uid')==1000
        and owner.get('source_revision')==source_revision and owner.get('worker',{}).get('sha256')==worker_sha256
        and owner.get('worker_executed') is False,'actual corrected execution-owner admission')
    require(type(attempt_files) is list and attempt_files==[],'Q15 execution already started; no retry')
    return True
