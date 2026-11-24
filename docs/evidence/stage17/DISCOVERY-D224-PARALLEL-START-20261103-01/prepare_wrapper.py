from pathlib import Path
import hashlib
ROOT=Path.cwd();target=ROOT/'build/stage17-step4-prep/d224-parallel-analysis/revision-2'
s=(ROOT/'build/stage17-step4-prep/d213-reanalysis/validate_d207_retained_study_v2.py').read_text()
s=s.replace('D213 offline reanalysis','D224 bounded parallel offline reanalysis')
s=s.replace("TOKEN = 'q16a_duration_discovery'", "PARALLEL_SHA256 = 'UNFROZEN'\nPARALLEL_DECISION_SHA256 = 'UNFROZEN'\nTOKEN = 'q16a_duration_discovery'")
a="    return cli, registry, validator, modules\n"
b='''    parallel_path = safe_path(Path(__file__).with_name('stage17_discovery_validation_parallel_v1.py'))
    parallel_raw = read_bytes(parallel_path, PARALLEL_SHA256)
    read_bytes(Path(__file__).with_name('0224-parallel-retained-discovery-validation.md'), PARALLEL_DECISION_SHA256)
    parallel_name = 'stage17_discovery_validation_parallel_v1'
    parallel = sys.modules.get(parallel_name)
    if parallel is None:
        spec = importlib.util.spec_from_file_location(parallel_name, parallel_path)
        require(spec is not None and spec.loader is not None, 'cannot load bound parallel adapter')
        parallel = importlib.util.module_from_spec(spec)
        sys.modules[parallel_name] = parallel
        exec(compile(parallel_raw, str(parallel_path), 'exec'), parallel.__dict__)
    require(safe_path(parallel.__file__) == parallel_path and parallel.base is validator,
            'parallel adapter dependency wiring differs')
    return cli, registry, parallel, (*modules, parallel)
'''
assert a in s;s=s.replace(a,b)
s=s.replace('if m is not validator else', "if safe_path(m.__file__).parent == repository / 'tools' else")
s=s.replace("        successor_validator_sha256=SUCCESSOR_SHA256,", "        successor_validator_sha256=SUCCESSOR_SHA256,\n        parallel_adapter_sha256=PARALLEL_SHA256, parallel_decision_sha256=PARALLEL_DECISION_SHA256,\n        analysis_workers=8, worker_address_space_limit_bytes=8*1024**3, maximum_analysis_seconds=86400,")
s=s.replace("retention_report=report, retention_binding=retention_binding, output_root=root)", "retention_report=report, retention_binding=retention_binding, output_root=root,\n                worker_count=8, worker_memory_bytes=8*1024**3, analysis_timeout_seconds=86400,\n                progress=lambda ordinal,completed,total: print(json.dumps(dict(event='capture_validated',ordinal=ordinal,completed=completed,total=total,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())),flush=True))")
(target/'validate_d207_retained_study_parallel_v1.py').write_text(s)
for src in ('tools/stage17_discovery_validation_v3.py','tools/stage17_discovery_validation_parallel_v1.py','docs/decisions/0213-discovery-whole-plot-readback-validation.md','docs/decisions/0224-parallel-retained-discovery-validation.md'):
 p=ROOT/src;(target/p.name).write_bytes(p.read_bytes())
s=s.replace("PARALLEL_SHA256 = 'UNFROZEN'", "PARALLEL_SHA256 = '"+hashlib.sha256((target/'stage17_discovery_validation_parallel_v1.py').read_bytes()).hexdigest()+"'")
s=s.replace("PARALLEL_DECISION_SHA256 = 'UNFROZEN'", "PARALLEL_DECISION_SHA256 = '"+hashlib.sha256((target/'0224-parallel-retained-discovery-validation.md').read_bytes()).hexdigest()+"'")
(target/'validate_d207_retained_study_parallel_v1.py').write_text(s)
