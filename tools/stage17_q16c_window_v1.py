"""D275 finite sub-budgets inside the original signed Q16c source-study day."""
NS=10**9
QUALIFICATION=7200
COLLECTION=47220
AUTHORITY_PREPARATION=600
ANALYSIS=5400
RESTORATION=2400
FAMILY=COLLECTION+AUTHORITY_PREPARATION


def require(ok,message):
    if not ok:raise ValueError('Q16c original window: '+message)


def validate(record,*,now,qualification=False):
    require(type(now) is int and 0<record['started_monotonic_ns']<=now,'original monotonic anchor')
    require(record['global_deadline_ns']-record['started_monotonic_ns']==86400*NS,'original24h duration')
    require(record['completed_monotonic_ns']<record['source_deadline_ns']
        and record['all_workers_reaped'] is True,'completed original sources')
    total=FAMILY+ANALYSIS+RESTORATION+(QUALIFICATION if qualification else 0)
    require(now+total*NS<record['global_deadline_ns'],'complete remaining envelope cannot fit')
    return record['global_deadline_ns']-now


def infrastructure(record,configuration,*,now):
    validate(record,now=now,qualification=True)
    require(configuration['boot_id']==record['boot_id']
        and configuration['source_revision']==record['software_source_revision'],'actual source/boot')
    life=configuration['lifecycle_seconds'];protected=configuration['protected_work_ns']
    require(type(life) is int and life>0 and type(protected) is int
        and protected>=(QUALIFICATION+FAMILY+ANALYSIS)*NS,'complete protected work budget')
    require(life*NS>protected+configuration['stop_seconds']*NS,'finite infrastructure lifetime underfunded')
    require(now+(life+RESTORATION)*NS<=record['global_deadline_ns'],
        'prepared infrastructure would outlive original restoration reserve')
    return True
