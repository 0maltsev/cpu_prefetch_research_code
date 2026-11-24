"""Software fixtures only; no stand access or experiments."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import audit_namespaces_q16b as audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = audit.parse((HERE.parent / 'planned-identities.json').read_bytes())
        cls.matcher = audit.Matcher(cls.ids)
        cls.phase = cls.ids['phase_identities'][0]
        cls.linked = cls.ids['linked_order_identities'][0]

    def test_complete_schema_and_counts(self):
        self.assertEqual(len(self.matcher.numeric), 8496)
        self.assertEqual(len(self.matcher.namespaces), 3)
        for name in ('phase_identities', 'linked_order_identities'):
            wrong = copy.deepcopy(self.ids)
            wrong[name].pop()
            with self.assertRaisesRegex(ValueError, '7080 phase'):
                audit.Matcher(wrong)
        wrong = copy.deepcopy(self.ids)
        wrong['linked_order_identities'][0]['seed_hex'] = self.phase['seed_hex']
        with self.assertRaisesRegex(ValueError, 'unique phase and linked seed_hex'):
            audit.Matcher(wrong)
        wrong = copy.deepcopy(self.ids)
        wrong['extra'] = True
        with self.assertRaisesRegex(ValueError, 'fields'):
            audit.Matcher(wrong)

    def test_all_phase_and_linked_identity_fields_match(self):
        for row in (self.phase, self.linked):
            for key in ('namespace_id', 'seed_id', 'seed_hex'):
                with self.subTest(key=key, linked=row is self.linked):
                    hits, _ = self.matcher.inspect(json.dumps({'old': row[key]}).encode())
                    self.assertIn('numeric_seed:' + row[key] if key == 'seed_hex' else row[key], hits)
        hits, _ = self.matcher.inspect(json.dumps({'run': self.phase['run_id']}).encode())
        self.assertIn(self.phase['run_id'], hits)

    def test_numeric_collision_is_exact_and_accepts_numeric_representations(self):
        seed = self.linked['seed_hex']
        for value in (seed, seed.upper(), '0x' + seed, str(int(seed, 16)), int(seed, 16)):
            hits, _ = self.matcher.inspect(json.dumps({'history': value}).encode())
            self.assertIn('numeric_seed:' + seed, hits)
        for value in ('f' + seed + 'f', 'prefix' + seed, int(seed, 16) + 1):
            hits, _ = self.matcher.inspect(json.dumps({'history': value}).encode())
            self.assertEqual(hits, [])

    def test_escaped_embedded_ids_and_jsonl(self):
        value = json.dumps({'history': 'prefix/' + self.linked['seed_id'] + '/suffix'})
        value = value.replace('CPU', '\\u0043PU')
        hits, _ = self.matcher.inspect((value + '\n{}\n').encode(), lines=True)
        self.assertIn(self.linked['seed_id'], hits)
        self.assertIn(self.linked['namespace_id'], hits)
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'\xff', b''):
            with self.assertRaises((ValueError, UnicodeError)):
                self.matcher.inspect(raw)
        with self.assertRaisesRegex(ValueError, 'node/depth'):
            self.matcher.inspect(b'{"a":[1,2]}', limits=replace(audit.Limits(), max_json_nodes=2))

    def fixture(self, base):
        (base / 'AGENTS.md').write_text('fixture')
        (base / 'docs/evidence').mkdir(parents=True)
        (base / 'docs/evidence/history.json').write_text('{}')

    def scan(self, base, limits=audit.Limits()):
        with patch.object(audit, 'FAMILIES', ()):
            return audit.audit('local', base, self.matcher, limits)

    def test_finite_exact_own_exclusions_and_raw_never_opened(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp)
            self.fixture(base)
            for relative in audit.LOCAL_EXCLUSIONS:
                path = base / relative
                path.mkdir(parents=True)
                (path / 'self.json').write_text(json.dumps(self.linked))
            raw = base / 'docs/evidence/raw'
            raw.mkdir()
            (raw / 'payload.json').write_bytes(b'not metadata')
            (base / 'docs/evidence/payload.bin').write_bytes(b'not metadata')
            report = self.scan(base)
            self.assertEqual(report['status'], 'PASS_SCOPED_HISTORY_AUDIT', report['errors'])
            self.assertEqual(report['checked_files'], 1)
            self.assertEqual(len(report['own_prospective_exclusions']), 2)
            self.assertTrue(any(x['reason'] == 'RAW_PAYLOAD_TREE_NOT_ENTERED' for x in report['excluded']))
            (base / 'docs/evidence/collision.json').write_text(json.dumps(self.linked))
            report = self.scan(base)
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(len(report['matches']), 1)

    def test_scratch_json_named_raw_control_never_opened_or_descended(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp)
            self.fixture(base)
            scratch = base / 'docs/evidence/continuation-prefix-1/analysis3/scratch'
            raw = scratch / '104954-capture173/q16a-c173-control.json'
            raw.parent.mkdir(parents=True)
            with raw.open('wb') as stream:
                stream.write(json.dumps(self.linked).encode())
                stream.truncate(audit.Limits().max_file_bytes + 1)
            original_read = audit.read_metadata
            original_children = audit.bounded_children
            def guarded_read(path, maximum):
                self.assertNotIn(scratch, Path(path).parents, 'raw scratch control was opened')
                return original_read(path, maximum)
            def guarded_children(path, maximum):
                self.assertNotEqual(Path(path), scratch, 'scratch payload tree was entered')
                return original_children(path, maximum)
            with patch.object(audit, 'read_metadata', side_effect=guarded_read), \
                 patch.object(audit, 'bounded_children', side_effect=guarded_children):
                report = self.scan(base)
            self.assertEqual(report['status'], 'PASS_SCOPED_HISTORY_AUDIT', report['errors'])
            self.assertEqual(report['checked_files'], 1)
            self.assertIn(dict(path=str(scratch), reason='RAW_PAYLOAD_TREE_NOT_ENTERED'), report['excluded'])
            outside = scratch.parent / 'registered-plan.json'
            outside.write_text(json.dumps(self.linked))
            report = self.scan(base)
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(report['matches'][0]['path'], str(outside))
            self.assertIn('numeric_seed:' + self.linked['seed_hex'], report['matches'][0]['matched'])

    def test_missing_prior_registered_plans_blocks_clearance(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp)
            self.fixture(base)
            report = audit.audit('local', base, self.matcher)
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(report['errors'][0]['missing'], sorted(audit.FAMILIES))

    def test_global_historical_plan_numeric_seed_collision(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp)
            self.fixture(base)
            old = dict(schema_version='cpu-prefetch-stage17-formal-service-plan/2',
                       action_id='Q16b', captures=[dict(capture=dict(linked_order=self.linked))])
            path = base / 'docs/evidence/registered-plan.json'
            path.write_bytes(audit.canonical(old))
            digest = audit.sha(audit.canonical(old))
            with patch.object(audit, 'FAMILIES', (digest,)):
                report = audit.audit('local', base, self.matcher)
            self.assertEqual(report['prior_registered_plan_sha256'], [digest])
            self.assertTrue(any('numeric_seed:' + self.linked['seed_hex'] in row['matched'] for row in report['matches']))
            self.assertEqual(report['status'], 'FAIL')

    def test_symlinks_missing_roots_and_finite_limits_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp)
            self.fixture(base)
            for limits in (replace(audit.Limits(), max_file_bytes=1),
                           replace(audit.Limits(), max_total_bytes=1),
                           replace(audit.Limits(), max_files=0),
                           replace(audit.Limits(), max_entries=1),
                           replace(audit.Limits(), wall_seconds=0)):
                with self.subTest(limits=limits):
                    self.assertEqual(self.scan(base, limits)['status'], 'FAIL')
            (base / 'docs/evidence/link.json').symlink_to(base / 'docs/evidence/history.json')
            report = self.scan(base)
            self.assertEqual(report['status'], 'FAIL')
            self.assertTrue(any('symlink' in x['reason'] for x in report['errors']))
            with self.assertRaises(ValueError):
                audit.selected_roots('local', base / 'absent')

    def test_all_E_roots_program_metadata_ledger_and_no_raw_trees(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp) / 'stage17-owner-evidence'
            for name in ('local-authoring-cpuprefetchv5-23', 'local-authoring-cpuprefetchv5-25', 'local-authoring-other-1'):
                ctx = base / name
                (ctx / 'admission-root/evidence').mkdir(parents=True)
                (ctx / 'context.json').write_text('{}')
                for sub in ('scope.json', 'ledger', 'metadata', 'working', 'archives'):
                    p = ctx / 'formal-archive-program-1' / sub
                    if sub.endswith('.json'):
                        p.parent.mkdir(exist_ok=True)
                        p.write_text('{}')
                    else:
                        p.mkdir()
            roots = audit.selected_roots('stand', base)
            self.assertEqual(len(roots), 15)
            self.assertFalse(any(p.name in audit.RAW_TREES for p in roots))
            self.assertTrue(all(base / name / 'formal-archive-program-1/ledger' in roots
                for name in ('local-authoring-cpuprefetchv5-23', 'local-authoring-cpuprefetchv5-25', 'local-authoring-other-1')))
            with self.assertRaisesRegex(ValueError, 'context bound'):
                audit.selected_roots('stand', base, replace(audit.Limits(), max_contexts=2))
            with self.assertRaisesRegex(ValueError, 'root bound'):
                audit.selected_roots('stand', base, replace(audit.Limits(), max_roots=2))

    def test_root_expansion_over_old512_accepted_but_new1024_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp) / 'stage17-owner-evidence'
            ctx = base / 'local-authoring-fixture'
            ctx.mkdir(parents=True)
            for i in range(513):
                (ctx / f'context-{i}.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'root bound'):
                audit.selected_roots('stand', base, replace(audit.Limits(), max_roots=512))
            self.assertEqual(len(audit.selected_roots('stand', base)), 513)
            for i in range(513, 1025):
                (ctx / f'context-{i}.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'root bound'):
                audit.selected_roots('stand', base)
            self.assertEqual(audit.Limits().max_roots, 1024)
            self.assertEqual(audit.Limits().max_contexts, 64)
            self.assertEqual(audit.Limits().max_total_bytes, 4 * 1024**3)
            self.assertEqual(audit.Limits().max_files, 200000)
            self.assertEqual(audit.Limits().max_entries, 400000)
            self.assertEqual(audit.Limits().wall_seconds, 300)

    def test_exact_zero_byte_metadata_is_inventoried_nonempty_invalid_still_fails(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp)
            self.fixture(base)
            empty = base / 'docs/evidence/failed.stdout.json'
            empty.write_bytes(b'')
            report = self.scan(base)
            self.assertEqual(report['status'], 'PASS_SCOPED_HISTORY_AUDIT')
            self.assertEqual(report['checked_files'], 2)
            item = next(i for i in report['checked_inventory'] if i['path'] == str(empty))
            self.assertEqual(item['metadata_status'], 'EMPTY_FILE_NO_METADATA')
            self.assertEqual(item['sha256'], hashlib.sha256(b'').hexdigest())
            self.assertEqual(item['size_bytes'], 0)
            empty.write_bytes(b' ')
            report = self.scan(base)
            self.assertEqual(report['status'], 'FAIL')
            self.assertTrue(any(e['path'] == str(empty) for e in report['errors']))

    def test_bound_input_wrong_hash_size_and_symlink(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            p = Path(tmp) / 'metadata.json'
            p.write_bytes(b'{}')
            self.assertEqual(audit.bound_input(p, audit.sha(b'{}'), 2), b'{}')
            for digest, maximum in [('0' * 64, 2), (audit.sha(b'{}'), 1)]:
                with self.assertRaises(ValueError):
                    audit.bound_input(p, digest, maximum)
            link = p.parent / 'link.json'
            link.symlink_to(p)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                audit.bound_input(link, audit.sha(b'{}'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
