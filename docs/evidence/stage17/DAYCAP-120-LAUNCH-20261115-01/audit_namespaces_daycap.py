#!/usr/bin/env python3
"""Bounded read-only Q16b public JSON/JSONL audit. Adapted from v25.

No raw reads, network, registration, signing, or experiment entry points.
"""
from dataclasses import asdict, dataclass
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

PLAN_SHA = '53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486'
FAMILIES = (
    'a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7',
    '91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2',
    'ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702',
    '6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847',
)
REGISTRY_SCHEMA = 'cpu-prefetch-stage17-q16b-planned-identities/1'
REPORT_SCHEMA = 'cpu-prefetch-stage17-q16b-namespace-audit/1'
# Exact finite exclusions, not caller-selected patterns or arbitrary subtrees.
LOCAL_EXCLUSIONS = ('build/stage17-daycap-120',)
STAND_EXCLUSIONS = ('local-authoring-cpuprefetchv5-26/daycap-collection-preparation-1',)
# Program payload trees must never be entered, including JSON-named payloads.
RAW_TREES = frozenset(('raw', 'raw-streams', 'streams', 'payload', 'payloads',
                       'working', 'archives', 'spool', 'release-hold', 'scratch'))
PUBLIC_TREES = ('admission-root/evidence', 'journal', 'actions', 'authorizations',
                'manifests', 'records', 'receipts')
PREPARATION_PREFIXES = ('discovery-preparation', 'formal-q16a-authoring',
    'formal-q16a-continuation-authoring', 'formal-q16b-preparation',
    'q16b-namespace-admission', 'continuation-prefix', 'formal-archive-program', 'daycap-collection-preparation')

@dataclass(frozen=True)
class Limits:
    max_roots: int = 1024
    max_contexts: int = 64
    max_entries: int = 400_000
    max_files: int = 200_000
    max_file_bytes: int = 96 * 1024**2
    max_total_bytes: int = 4 * 1024**3
    max_json_nodes: int = 10_000_000
    max_depth: int = 64
    wall_seconds: int = 300


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def parse(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def absolute(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute normalized path required')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path forbidden')
    return path


def stamp(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read_metadata(path, maximum):
    path = absolute(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'regular metadata required')
        require(before.st_size <= maximum, 'metadata byte bound')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size and stamp(before) == stamp(after)
            and stamp(after) == stamp(path.stat(follow_symlinks=False)), 'metadata changed during read')
    return raw


def bound_input(path, expected, maximum=96 * 1024**2):
    raw = read_metadata(path, maximum)
    require(sha(raw) == expected, 'bound input SHA256 differs: ' + str(path))
    return raw


def binding(path, raw):
    return dict(path=str(path), size_bytes=len(raw), sha256=sha(raw))


def planned_identities(plan, raw):
    require(sha(raw) == PLAN_SHA, 'exact final candidate-3 plan required')
    require(raw == canonical(plan), 'canonical no-LF plan required')
    require(plan['action_id'] == 'Q16b' and len(plan['captures']) == 120, '120 Q16b captures required')
    phase, linked = [], []
    for ordinal, item in enumerate(plan['captures']):
        capture = item['capture']
        require(capture['ordinal'] == ordinal, 'capture ordinal differs')
        require(capture['arena_seed'] == capture['measurement'], 'arena seed differs from measurement')
        phase.extend(capture[p] for p in ('warmup', 'measurement'))
        if capture['linked_order'] is not None:
            require(capture['package'] in ('L0', 'L1'), 'unexpected linked order')
            linked.append(capture['linked_order'])
        else:
            require(capture['package'] not in ('L0', 'L1'), 'missing linked order')
    result = dict(schema_version=REGISTRY_SCHEMA, plan_sha256=sha(raw), stand_id=plan['stand_id'],
        phase_identities=phase, linked_order_identities=linked, schedule_namespaces=[],
        execution_authority=False)
    Matcher(result)
    return result


def validate_registry(registry, plan, raw):
    require(registry == planned_identities(plan, raw), 'entire planned identity schema differs from final plan')
    return registry


class Matcher:
    def __init__(self, document):
        require(set(document) == {'schema_version', 'plan_sha256', 'stand_id', 'phase_identities',
            'linked_order_identities', 'schedule_namespaces', 'execution_authority'}, 'planned identity fields differ')
        require(document['schema_version'] == REGISTRY_SCHEMA and document['plan_sha256'] == PLAN_SHA
            and document['execution_authority'] is False and document['schedule_namespaces'] == [], 'planned identity binding differs')
        phase, linked = document['phase_identities'], document['linked_order_identities']
        require(len(phase) == 240 and len(linked) == 48, '240 phase + 48 linked identities required')
        for row in phase:
            require(set(row) == {'run_id', 'seed_id', 'seed_hex', 'namespace_id'}, 'phase identity fields differ')
        for row in linked:
            require(set(row) == {'seed_id', 'seed_hex', 'namespace_id', 'arena_alignment_bytes'}, 'linked identity fields differ')
        rows = phase + linked
        for key in ('seed_id', 'seed_hex'):
            require(len({r[key] for r in rows}) == 288, 'unique phase and linked ' + key + ' required')
        require(len({r['run_id'] for r in phase}) == 240, 'unique phase run IDs required')
        for row in rows:
            require(isinstance(row['seed_hex'], str) and re.fullmatch('[0-9a-f]{64}', row['seed_hex']), 'canonical numeric seed required')
            for key in ('seed_id', 'namespace_id'):
                require(isinstance(row[key], str) and re.fullmatch('[A-Za-z0-9_-]{1,160}', row[key]), 'identity token shape')
        self.namespaces = {r['namespace_id'] for r in rows}
        require(len(self.namespaces) == 3, 'two phase and one linked namespace required')
        self.wanted = {r[k] for r in phase for k in ('run_id', 'seed_id', 'namespace_id')}
        self.wanted.update(r[k] for r in linked for k in ('seed_id', 'namespace_id'))
        self.numeric = {int(r['seed_hex'], 16): r['seed_hex'] for r in rows}
        # Prefix matching avoids a huge 15k-alternative regex. Also matches embedded IDs.
        prefixes = {r['run_id'][:-8] for r in phase}
        seed_prefixes = {r['seed_id'][:-4] for r in rows}
        self.identity_namespace = {r[k]: r['namespace_id'] for r in rows for k in ('seed_id',)}
        self.identity_namespace.update({r['run_id']: r['namespace_id'] for r in phase})
        self.tokens = re.compile('(?=(' + '|'.join([re.escape(n) + r'(?:-SEED-[0-9]{4})?' for n in sorted(self.namespaces)]
            + [re.escape(p) + r'[0-9]{8}' for p in sorted(prefixes)]
            + [re.escape(p) + r'[0-9]{4}' for p in sorted(seed_prefixes)]) + '))')
        self.numbers = re.compile(r'(?<![A-Za-z0-9_])(?:0[xX][0-9a-fA-F]{1,64}|[0-9a-fA-F]{64}|[0-9]{1,78})(?![A-Za-z0-9_])')

    def text(self, text):
        found = set()
        for match in self.tokens.finditer(text):
            token = match.group(1)
            if token in self.wanted:
                found.add(token)
                if token in self.identity_namespace:
                    found.add(self.identity_namespace[token])
            found.update(n for n in self.namespaces if token.startswith(n))
        for match in self.numbers.finditer(text):
            token = match.group()
            bases = (16,) if token.lower().startswith('0x') or re.search('[a-fA-F]', token) else (10, 16)
            for base in bases:
                number = int(token, base)
                if number in self.numeric:
                    found.add('numeric_seed:' + self.numeric[number])
        return found

    def inspect(self, raw, lines=False, limits=Limits()):
        text = raw.decode('utf-8', errors='strict')
        records = (line for line in text.splitlines() if line.strip()) if lines else (text,)
        found, plans, nodes, count = set(), set(), 0, 0
        for record in records:
            count += 1
            # Scan decoded values; escaped identifiers cannot bypass matching.
            pending = [(parse(record), 0)]
            while pending:
                value, depth = pending.pop()
                nodes += 1
                require(nodes <= limits.max_json_nodes and depth <= limits.max_depth, 'JSON node/depth bound')
                if isinstance(value, str):
                    found.update(self.text(value))
                elif type(value) is int and value in self.numeric:
                    found.add('numeric_seed:' + self.numeric[value])
                elif isinstance(value, dict):
                    if (value.get('action_id') in ('Q16a', 'Q16b', 'Q17')
                        and isinstance(value.get('captures'), list)
                        and str(value.get('schema_version', '')).startswith('cpu-prefetch-stage17-formal-')):
                        plans.add(sha(canonical(value)))
                    pending.extend((v, depth + 1) for v in value.values())
                    pending.extend((k, depth + 1) for k in value.keys())
                elif isinstance(value, list):
                    pending.extend((v, depth + 1) for v in value)
        require(count > 0, 'empty JSONL')
        return sorted(found), sorted(plans)


def bounded_children(path, maximum):
    children = []
    with os.scandir(path) as scan:
        for entry in scan:
            require(len(children) < maximum, 'directory entry bound')
            children.append(Path(entry.path))
    return sorted(children)


def selected_roots(mode, base, limits=Limits()):
    base = absolute(base)
    if mode == 'local':
        require((base / 'AGENTS.md').is_file(), 'repository root required')
        require((base / 'docs/evidence').is_dir(), 'local evidence root required')
        roots = [base / 'docs/evidence']
        roots.extend(base / f'build/stage17-step{i}-prep' for i in (2, 3, 4, 5, 6)
                     if (base / f'build/stage17-step{i}-prep').exists())
        if (base / 'build/stage17-archive-optimization').exists():
            roots.append(base / 'build/stage17-archive-optimization')
        if (base / 'build/stage17-step6-q16b-prep/candidate-3').exists():
            roots.append(base / 'build/stage17-step6-q16b-prep/candidate-3')
        return roots
    require(mode == 'stand' and base.name == 'stage17-owner-evidence' and base.is_dir(), 'stand all-E base required')
    contexts = [p for p in bounded_children(base, limits.max_entries) if p.name.startswith('local-authoring-')]
    require(0 < len(contexts) <= limits.max_contexts, 'all-E context bound')
    roots = []
    for context in contexts:
        absolute(context)
        require(context.is_dir(), 'all-E context must be directory')
        children = bounded_children(context, limits.max_entries)
        roots.extend(p for p in children if p.suffix.lower() in ('.json', '.jsonl'))
        roots.extend(context / name for name in PUBLIC_TREES if (context / name).exists())
        for p in children:
            if p.name.startswith(PREPARATION_PREFIXES):
                if p.name.startswith('formal-archive-program'):
                    # Every program, every FAMILY record and retained plan metadata, never working/raw.
                    roots.extend(p / name for name in ('scope.json', 'ledger', 'metadata'))
                else:
                    roots.append(p)
    require(0 < len(roots) <= limits.max_roots, 'metadata root bound')
    return sorted(set(roots))


def exclusions(mode, base):
    return [absolute(base) / p for p in (LOCAL_EXCLUSIONS if mode == 'local' else STAND_EXCLUSIONS)]


def audit(mode, base, matcher, limits=Limits()):
    roots = selected_roots(mode, base, limits)
    excluded_roots = exclusions(mode, base)
    checked, matches, errors, excluded = [], [], [], []
    seen, historical_plans = set(), set()
    total = visited = reads = 0
    deadline = time.monotonic() + limits.wall_seconds
    stopped = False

    def visit(path, depth=0):
        nonlocal total, visited, reads, stopped
        if stopped or path in seen:
            return
        seen.add(path)
        visited += 1
        require(time.monotonic() < deadline, 'audit wall deadline')
        require(visited <= limits.max_entries and depth <= limits.max_depth, 'traversal entry/depth bound')
        if any(path == own or own in path.parents for own in excluded_roots):
            excluded.append(dict(path=str(path), reason='OWN_PROSPECTIVE_PREPARATION'))
            return
        try:
            absolute(path)
            mode_bits = path.lstat().st_mode
            if stat.S_ISDIR(mode_bits):
                if path.name in RAW_TREES:
                    excluded.append(dict(path=str(path), reason='RAW_PAYLOAD_TREE_NOT_ENTERED'))
                    return
                for child in bounded_children(path, limits.max_entries - visited):
                    visit(child, depth + 1)
                return
            if path.suffix.lower() not in ('.json', '.jsonl'):
                return
            require(stat.S_ISREG(mode_bits), 'nonregular metadata file')
            require(reads < limits.max_files, 'metadata file count bound')
            reads += 1
            remaining = limits.max_total_bytes - total
            raw = read_metadata(path, min(limits.max_file_bytes, remaining))
            total += len(raw)
            item = binding(path, raw)
            if raw == b'':
                found, plans = [], []
                item['metadata_status'] = 'EMPTY_FILE_NO_METADATA'
            else:
                found, plans = matcher.inspect(raw, path.suffix.lower() == '.jsonl', limits)
            checked.append(item)
            historical_plans.update(plans)
            if found:
                matches.append(dict(**item, matched=found))
        except (OSError, ValueError, RecursionError, UnicodeError) as error:
            errors.append(dict(path=str(path), reason=str(error)))
            # Bounds are hard stops, not per-file skips followed by more reads.
            if 'bound' in str(error) or 'deadline' in str(error):
                stopped = True
    try:
        for root in roots:
            visit(root)
    except (ValueError, TimeoutError) as error:
        errors.append(dict(path='<scope>', reason=str(error)))
    if not checked:
        errors.append(dict(path='<scope>', reason='no metadata checked'))
    missing = sorted(set(FAMILIES) - historical_plans)
    if missing:
        errors.append(dict(path='<registered-plan-history>', reason='missing exact prior registered plans', missing=missing))
    return dict(schema_version=REPORT_SCHEMA, status='PASS_SCOPED_HISTORY_AUDIT' if not errors and not matches else 'FAIL',
        mode=mode, base=str(base), observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        scope='Finite selected public metadata only; all-E stand contexts; no raw reads or whole-disk proof',
        roots=list(map(str, roots)), own_prospective_exclusions=list(map(str, excluded_roots)),
        limits=asdict(limits), visited_entries=visited, attempted_file_reads=reads, checked_files=len(checked), checked_bytes=total,
        checked_inventory=checked, checked_inventory_sha256=sha(canonical(checked)),
        prior_registered_plan_sha256=sorted(set(FAMILIES) & historical_plans),
        historical_plan_sha256=sorted(historical_plans), numeric_seeds_collision_scanned=True,
        planned_phase_identities=240, planned_linked_order_identities=48, planned_numeric_seeds=288,
        plan_sha256=PLAN_SHA, matches=matches, errors=errors, excluded=excluded,
        registration_performed=False, execution_authority=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', default=PLAN_SHA, choices=(PLAN_SHA,))
    parser.add_argument('--identities', type=Path)
    parser.add_argument('--identities-sha256')
    parser.add_argument('--emit-identities', action='store_true', help='Emit complete proposal to stdout; no history scan')
    parser.add_argument('--mode', choices=('local', 'stand'))
    parser.add_argument('--base', type=Path)
    parser.add_argument('--wall-seconds', type=int, default=300)
    args = parser.parse_args()
    require(1 <= args.wall_seconds <= 300, 'wall bound 1..300 seconds')
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('audit wall deadline')))
    signal.setitimer(signal.ITIMER_REAL, args.wall_seconds)
    try:
        raw = bound_input(args.plan, args.plan_sha256)
        plan = parse(raw)
        root = absolute(args.repository_root)
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(root / 'tools'))
        import stage17_formal_plan_v2 as formal
        require(Path(formal.__file__).resolve() == root / 'tools/stage17_formal_plan_v2.py', 'plan validator outside repository')
        # Exact immutable plan SHA pins the already validated candidate.
        # This scanner checks every identity; full action admission is separate.
        registry = planned_identities(plan, raw)
        if args.emit_identities:
            print(canonical(registry).decode())
            return 0
        require(args.identities is not None and args.identities_sha256 and args.mode and args.base, 'bound registry and explicit audit scope required')
        ids_raw = bound_input(args.identities, args.identities_sha256, 4 * 1024**2)
        validate_registry(parse(ids_raw), plan, raw)
        report = audit(args.mode, absolute(args.base), Matcher(registry), Limits(wall_seconds=args.wall_seconds))
        report['plan_binding'] = binding(args.plan, raw)
        report['identities_binding'] = binding(args.identities, ids_raw)
        report['helper_sha256'] = sha(read_metadata(Path(__file__).absolute(), 1024**2))
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0 if report['status'] == 'PASS_SCOPED_HISTORY_AUDIT' else 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    raise SystemExit(main())
