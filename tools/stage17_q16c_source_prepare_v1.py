#!/usr/bin/env python3
"""D273 one bounded stand-only original-source generation/verification job.

This software job creates no native measurements and grants no phase authority.
The caller authenticates this administrative source and the qualified bundle.
An exclusive output/window makes this a single attempt, without automatic retry.
"""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import hashlib
import importlib
import json
import multiprocessing
from multiprocessing.connection import wait
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from fractions import Fraction

WORKERS = 32
WORKER_MEMORY = 2 * 1024**3
SOURCE_WORKSPACE = 64 * 1024**3
SOURCE_CAP_NS = 22_500_000_000_000
DAY_NS = 86_400_000_000_000
SETUP_SCHEMA = 'cpu-prefetch-stage17-q16c-source-setup/1'
PURPOSE = 'D270-ORIGINAL-GENERATION-AND-INDEPENDENT-VALIDATION-ONLY'


def require(condition, message):
    if not condition: raise ValueError('source preparation: '+message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def reject(_value): raise ValueError('source preparation: exact integer JSON required')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def save(path, raw):
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try: os.fsync(directory)
    finally: os.close(directory)
    return binding(path)


def binding(path):
    raw = path.read_bytes()
    return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def stamp(path):
    s = path.stat(follow_symlinks=False)
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns


def _original_job(source, output, bundle, basis_raw):
    """Use the actual unchanged generator, then actual independent verifier."""
    sys.path.insert(0, str(bundle/'tools'))
    gen = importlib.import_module('generate_schedule')
    verify = importlib.import_module('stage17_q16c_schedule_provenance_v2')
    require(Path(gen.__file__).resolve() == bundle/'tools/generate_schedule.py', 'foreign generator import')
    require(Path(verify.__file__).resolve() == bundle/'tools/stage17_q16c_schedule_provenance_v2.py', 'foreign validator import')
    basis = json.loads(basis_raw)
    rate = Fraction(**basis['base_rates'][source['load_level']]) / 10**12
    duration = (5_000_000_000 if source['phase'] == 'warmup' else 1_000_000_000)
    spec = gen.ScheduleSpec(source['schedule_id'], 'WARMUP' if source['phase']=='warmup' else 'CALIBRATION',
        source['namespace_id'], source['parent_namespace_id'], source['seed_id'], source['derivation_record_id'],
        bytes.fromhex(source['seed_hex']), 0, duration*1000, rate.numerator, rate.denominator,
        source['artifact_id'], source['artifact_uri'])
    produced = gen.generate_schedule(spec)
    count = len(produced.deadlines)
    # A prospective resource ceiling; hitting it fails the family, never clips
    # its source, resamples the seed or chooses a favorable replacement.
    maximum = 4 * ((rate.numerator * spec.horizon_ticks + rate.denominator - 1) // rate.denominator) + 1024
    require(count <= maximum, 'prospective source extent ceiling reached')
    original = save(output/'original.u64be', produced.artifact_bytes)
    envelope = save(output/'schedule.json', produced.envelope_bytes)
    derivation = save(output/'derivation.json', produced.derivation_record_bytes)
    schedule = dict(schedule_id=source['schedule_id'], seed_id=source['seed_id'], seed_hex=source['seed_hex'],
        namespace_id=source['namespace_id'], source_origin_ticks=0, source_horizon_ticks=duration*1000,
        offered_count=count, storage_format='SEALED_U64BE_ORIGINAL-v1',
        source_artifact=dict(artifact_id=source['artifact_id'], sha256=original['sha256']))
    del produced
    def ref(value, suffix): return dict(artifact_id=source['artifact_id']+suffix,
                                        size_bytes=value['size_bytes'], sha256=value['sha256'])
    result = verify.verify_schedule_source(schedule=schedule, phase=source['phase'], duration_ns=duration,
        scale_ordinal=0, load_level=source['load_level'], load_basis_utf8_bytes=basis_raw,
        artifact_path=Path(original['path']), artifact_binding=ref(original,''),
        envelope_utf8_bytes=Path(envelope['path']).read_bytes(), envelope_binding=ref(envelope,':envelope'),
        derivation_utf8_bytes=Path(derivation['path']).read_bytes(), derivation_binding=ref(derivation,':derivation'),
        expected_parent_namespace_id=source['parent_namespace_id'])
    return dict(ordinal=source['ordinal'], binary=original, envelope=envelope, derivation=derivation,
                provenance=result)


def _worker(pipe, jobs, output, bundle, basis_raw):
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit = min(WORKER_MEMORY, soft if soft != resource.RLIM_INFINITY else WORKER_MEMORY,
                    hard if hard != resource.RLIM_INFINITY else WORKER_MEMORY)
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        for source in jobs:
            row = _original_job(source, output/f"s{source['ordinal']:03d}", bundle, basis_raw)
            pipe.send(('source', row))
        pipe.send(('done', None))
    except BaseException as error:
        with contextlib.suppress(Exception): pipe.send(('error', f'{type(error).__name__}: {str(error)[:4096]}'))
    finally: pipe.close()


def _balanced(sources, basis):
    groups = [[] for _ in range(WORKERS)]; weights = [Fraction(0) for _ in groups]
    def cost(source):
        return Fraction(**basis['base_rates'][source['load_level']]) * (5 if source['phase']=='warmup' else 1)
    for source in sorted(sources, key=lambda s:(-cost(s), s['ordinal'])):
        selected = min(range(WORKERS), key=lambda i:(weights[i],i))
        groups[selected].append(source); weights[selected] += cost(source)
    return groups


def _stop(processes):
    # These fixed pure-software children do not spawn other processes. Held
    # multiprocessing handles own their PIDs until join; no external group is
    # selected or signalled. The caller's systemd unit additionally owns its CG.
    for process in processes:
        if process.is_alive(): process.terminate()
    deadline = time.monotonic() + 10
    for process in processes: process.join(max(0,deadline-time.monotonic()))
    for process in processes:
        if process.is_alive(): process.kill()
    for process in processes: process.join(5)
    require(all(not p.is_alive() for p in processes), 'owned software child did not reap')


def collect_sources(sources, output, bundle, basis_raw, source_deadline):
    rows = {}; processes = []; channels = {}; finished = set(); context = multiprocessing.get_context('fork')
    try:
        for group in _balanced(sources, json.loads(basis_raw)):
            parent, child = context.Pipe(duplex=False)
            process = context.Process(target=_worker, args=(child,group,output,bundle,basis_raw))
            process.start(); child.close(); processes.append(process); channels[parent]=process
        while len(finished)<WORKERS:
            require(time.monotonic_ns()<source_deadline, 'original source preparation deadline reached')
            for channel in wait(list(channels), timeout=1):
                kind, value = channel.recv()
                if kind=='error': raise ValueError(value)
                if kind=='done': finished.add(channels[channel].pid); channel.close(); del channels[channel]; continue
                require(kind=='source' and value['ordinal'] not in rows, 'foreign/duplicate source worker result')
                i = value['ordinal']; rows[i]=value
                save(output/f'source-progress-{i:03d}.json', canonical(value))
            for process in processes:
                if process.pid not in finished and process.exitcode is not None and process.exitcode!=0:
                    raise ValueError('source worker exited before completion')
        for process in processes: process.join(10)
        require(all(p.exitcode==0 and not p.is_alive() for p in processes), 'source worker completion/reaping failed')
        require(set(rows)==set(range(360)), 'source family incomplete')
        # Source-byte completion can precede its grouped worker's exit. Publish
        # reaping facts only after every actual worker has been joined.
        for i in range(360):
            rows[i].update(exit_code=0, leader_reaped=True)
            save(output/f'source-result-{i:03d}.json', canonical(rows[i]))
        return rows
    finally:
        _stop(processes)
        for channel in channels: channel.close()
        for process in processes: process.close()


def run(setup_path, expected_sha256, output, signing_key, namespace):
    require(output.is_absolute() and not output.exists(), 'exclusive absolute output root required')
    require(output.parent.resolve(strict=True)==output.parent, 'canonical output parent required')
    require(setup_path.is_absolute() and setup_path.resolve(strict=True)==setup_path, 'canonical setup path required')
    original_setup = binding(setup_path)
    raw = setup_path.read_bytes(); require(len(raw)<=2*1024**2 and hashlib.sha256(raw).hexdigest()==expected_sha256, 'setup bytes differ')
    require(original_setup == binding(setup_path), 'source setup changed during read')
    setup = strict_json(raw)
    require(set(setup)=={'schema_version','stand_id','boot_id','bundle_root','source_revision',
        'bundle_inventory_sha256','sources','execution_authority','phase18_authority'}, 'closed prospective source setup required')
    require(setup['schema_version']==SETUP_SCHEMA and setup['execution_authority'] is False
            and setup['phase18_authority'] is False, 'source setup schema or authority differs')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==setup['boot_id'], 'source setup boot changed')
    require(len(os.sched_getaffinity(0)) >= WORKERS, 'observed logical CPU availability cannot support pool')
    available = [r for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith('MemAvailable:')]
    require(len(available)==1 and int(available[0].split()[1])*1024 >= (WORKERS+1)*WORKER_MEMORY,
            'observed available memory cannot support bounded source pool')
    bundle = Path(setup['bundle_root']); require(bundle.is_absolute() and bundle.resolve(strict=True)==bundle, 'canonical bundle root')
    sys.path.insert(0, str(bundle/'tools'))
    import stage17_semantic_verifier_v61 as semantic
    import stage17_q16c_schedule_provenance_v2 as provenance
    inventory = json.loads((bundle/'BUNDLE_INVENTORY.json').read_bytes())
    bundle_manifest = json.loads((bundle/'BUNDLE_MANIFEST.json').read_bytes())
    require(bundle_manifest['source_archive']['source_revision']==setup['source_revision'], 'actual software source revision differs')
    require(binding(bundle/'BUNDLE_INVENTORY.json')['sha256']==setup['bundle_inventory_sha256'], 'actual software inventory differs')
    index = {row['path']:row for row in inventory['files']}
    names = semantic.discover_python_closure(bundle, ('generate_schedule','stage17_q16c_schedule_provenance_v2'))
    names |= {'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json',
        'config/schemas/schedule-derivation-v2.schema.json','config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'}
    closure = {}
    for name in sorted(names):
        observed = binding(bundle/name)
        require([observed['size_bytes'], observed['sha256']]==[index[name]['size_bytes'],index[name]['sha256']], 'actual source closure differs')
        closure[name] = observed
    basis_raw = (bundle/'docs/evidence/stage17/Q16B-HANDOFF-20261117-01/descriptive-load-basis.json').read_bytes()
    require(len(basis_raw)==provenance.BASIS_BYTES and hashlib.sha256(basis_raw).hexdigest()==provenance.BASIS_SHA256,
            'exact completed load basis required')
    sources = setup['sources']; require(type(sources) is list and len(sources)==360, 'all360 prospective sources required')
    seen = {key:set() for key in ('schedule_id','seed_id','namespace_id','artifact_id')}
    for i, source in enumerate(sources):
        require(set(source)=={'ordinal','capture_ordinal','phase','load_level','schedule_id','seed_id','seed_hex',
            'namespace_id','parent_namespace_id','artifact_id','artifact_uri','derivation_record_id'}, 'closed source coordinates required')
        require(type(source['ordinal']) is int and source['ordinal']==i and source['capture_ordinal']==i//2
                and source['phase']==('warmup','measurement')[i%2] and source['load_level'] in ('L025','L050','L075'), 'prospective source coordinates differ')
        for name in seen:
            require(source[name] not in seen[name], 'prospective source identity reused'); seen[name].add(source[name])
    output.mkdir(mode=0o755)
    # This is the first actual prospective-source preparation action. The
    # immutable original clock is never reset by a failure or later command.
    started = time.monotonic_ns(); global_deadline = started + DAY_NS; source_deadline = started + SOURCE_CAP_NS
    save(output/'window.json', canonical(dict(started_monotonic_ns=started, global_deadline_ns=global_deadline,
        source_deadline_ns=source_deadline, boot_id=setup['boot_id'], source_setup=binding(setup_path),
        retry_authorized=False, phase18_authority=False)))
    rows = {}
    try:
        require(os.statvfs(output).f_bavail*os.statvfs(output).f_frsize >= SOURCE_WORKSPACE+16*1024**3, 'source workspace/reserve unavailable')
        for i in range(360): (output/f's{i:03d}').mkdir(mode=0o755)
        rows = collect_sources(sources, output, bundle, basis_raw, source_deadline)
        require(sum(r['binary']['size_bytes']+r['envelope']['size_bytes']+r['derivation']['size_bytes'] for r in rows.values())<=SOURCE_WORKSPACE,
                'source workspace bound reached')
        for name, expected in closure.items(): require(binding(bundle/name)==expected, 'accepted software changed during preparation')
        require(binding(setup_path)==original_setup, 'source setup changed during preparation')
        completed = time.monotonic_ns(); require(completed<source_deadline, 'source preparation deadline reached')
        record = dict(schema_version='cpu-prefetch-stage17-q16c-source-preparation/1', purpose=PURPOSE,
            protocol_version='2.0.0-pre.3', stand_id=setup['stand_id'], boot_id=setup['boot_id'],
            software_source_revision=setup['source_revision'], bundle_inventory_sha256=setup['bundle_inventory_sha256'],
            load_basis_sha256=provenance.BASIS_SHA256, source_root=str(output), source_closure=closure,
            source_setup=original_setup,
            started_monotonic_ns=started, completed_monotonic_ns=completed, source_deadline_ns=source_deadline,
            global_deadline_ns=global_deadline, workers=WORKERS, all_workers_reaped=True,
            sources=[rows[i] for i in range(360)], experimental_actions=0, execution_authority=False, phase18_authority=False)
        manifest = output/'source-preparation.json'; save(manifest,canonical(record))
        signed = subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(signing_key),'-n',namespace,str(manifest)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
        require(signed.returncode==0, 'owner signature publication failed')
        save(output/'complete.json',canonical(dict(manifest=binding(manifest),signature=binding(Path(str(manifest)+'.sig')),
            all_workers_reaped=True, experimental_actions=0, phase18_authority=False)))
    except BaseException as error:
        with contextlib.suppress(Exception):
            save(output/'failure.json',canonical(dict(error=type(error).__name__+': '+str(error)[:4096],
                original_started_monotonic_ns=started, original_global_deadline_ns=global_deadline,
                completed_sources=sorted(rows), all_workers_reaped=not multiprocessing.active_children(),
                experimental_actions=0, retry_authorized=False, phase18_authority=False)))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--setup',type=Path,required=True);p.add_argument('--setup-sha256',required=True)
    p.add_argument('--output-root',type=Path,required=True);p.add_argument('--signing-key',type=Path,required=True)
    p.add_argument('--namespace',required=True);a=p.parse_args()
    def terminate(_number, _frame): raise InterruptedError('source preparation terminated; no retry')
    signal.signal(signal.SIGTERM, terminate)
    run(a.setup,a.setup_sha256,a.output_root,a.signing_key,a.namespace)
    return 0


if __name__=='__main__': raise SystemExit(main())
