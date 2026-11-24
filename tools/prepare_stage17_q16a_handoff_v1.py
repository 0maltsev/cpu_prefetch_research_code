"""Publish D247 handoff after read-only qualified historical preparation.

No isolation, hardware action, raw decoding or formal execution is performed.
Run in a separately bound administrative packet, never the qualified tree.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
from pathlib import Path
import resource
import sys

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
CONFIG_SHA = '5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93'
BOOTSTRAP_SHA = 'b1feb13f9cbcfa9ec6c41d11662c64f1b8f11d591f311f75a2d166f6fe94be23'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() != 1000 or os.geteuid() != 1000:
        raise ValueError('owner-only administrative preparation')
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3,) * 2)
    bootstrap = E / 'offline-suffix-operators-1'
    if hashlib.sha256((bootstrap / 'validate_suffix.py').read_bytes()).hexdigest() != BOOTSTRAP_SHA:
        raise ValueError('original verified bootstrap differs')
    sys.path.insert(0, str(bootstrap))
    import validate_suffix as v
    c = v.config(E / 'offline-suffix-preparation-1/inputs/analysis-config.json', CONFIG_SHA)
    root = v.base.safe(args.output_root)
    v.require(root.parent == E and not root.exists(), 'fresh sibling handoff namespace required')
    root.mkdir(mode=0o700)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        m, pinned = v.modules(c)
        prepared = v.prepare(c, m)
        v.lifecycle(c, m, prepared, pinned)
        print('QUALIFIED_HISTORICAL_PREPARATION_PASS', flush=True)
        here = Path(__file__).resolve().parent
        manifest = v.parse((here / 'manifest.json').read_bytes())
        for row in manifest['files']:
            v.require(Path(row['name']).name == row['name'], 'flat administrative member')
            v.read(dict(path=str(here / row['name']), size_bytes=row['size_bytes'], sha256=row['sha256']))
        # Insert only the separately authenticated administrative additions.
        sys.path.insert(0, str(here))
        import stage17_q16a_handoff_v1 as handoff
        originals = E / 'offline-q16a-composition-1'
        document = dict(schema_version=handoff.SCHEMA,
            completion=v.base.binding(originals / 'complete.json'),
            composition=v.base.binding(originals / 'authenticated-composition.json'),
            geometry=v.base.binding(originals / 'native-geometry-verification.json'),
            execution_authority=False, phase18_authority=False)
        current = prepared.request['action_inputs']['plan']
        result = handoff.consume(document, validation=prepared.validation,
            plan=dict(source_revision=current['source_revision'], stand_id=current['stand_id']),
            selected_duration_ns=current['measurement_ns'])
        binding = v.save(root / 'q16a-handoff.json', document, 65536)
        v.save(root / 'verification.json', dict(status='VERIFIED_Q16A_DOWNSTREAM_PREREQUISITE',
            started_at_utc=started, completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            handoff=binding, operator_manifest=v.base.binding(here / 'manifest.json'),
            source_populations=result['source_populations'], valid_reports=708,
            measurement_zero_loss_gate=result['derived_result']['measurement_zero_loss_gate'],
            warmup_zero_loss_gate=result['derived_result']['warmup_zero_loss_gate'],
            raw_redecode_performed=False, raw_mutation=False, new_collection_performed=False,
            ext007_admitted=False, execution_authority=False, phase18_authority=False), 65536)
        print('Q16A_HANDOFF_VERIFIED', binding['sha256'], flush=True)
    except BaseException as error:
        v.save(root / 'failure.json', dict(type=type(error).__name__, message=str(error),
            raw_mutation=False, raw_redecode_performed=False, execution_authority=False), 65536)
        raise


if __name__ == '__main__':
    main()
