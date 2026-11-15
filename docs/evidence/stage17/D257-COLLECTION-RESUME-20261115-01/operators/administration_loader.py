"""Authenticate the closed D256 sidecar before importing its private CLI graph."""
import json
import pathlib
import sys
import types

MANIFEST_SHA = '69baa4f6ea40f461be1dccff5f40ed4c4cea7db0ce1da3008af11b4c3fb8d871'


def load(configuration, read):
    manifest = configuration['administration_manifest']
    if manifest['sha256'] != MANIFEST_SHA:
        raise ValueError('actual signed D256 administrative closure required')
    directory = pathlib.Path(manifest['path']).parent
    expected = pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26/d256-admin-1')
    if directory != expected:
        raise ValueError('D256 administrative namespace differs')
    document = json.loads(read(manifest))
    for row in document['files']:
        if pathlib.Path(row['name']).name != row['name']:
            raise ValueError('invalid administrative source name')
        read(dict(path=str(directory/row['name']), size_bytes=row['size_bytes'], sha256=row['sha256']))
    if {p.name for p in directory.iterdir()} != {r['name'] for r in document['files']} | {'manifest.json'}:
        raise ValueError('D256 administrative closure expanded')
    binding = configuration['administration']
    if pathlib.Path(binding['path']) != directory/'stage17_daycap_administration_v2.py':
        raise ValueError('explicit D256/D255 graph required')
    if any(name in sys.modules for name in ('stage17_daycap_administration_v1',
            'stage17_daycap_administration_v2', 'stage17_state_journal_v55')):
        raise ValueError('unverified cached administrative module')
    # The qualified root remains first; only the previously authenticated,
    # separately versioned administrative sources are added here.
    sys.path.insert(1, str(directory))
    name = 'stage17_daycap_administration_v2'
    module = types.ModuleType(name)
    module.__file__ = binding['path']
    sys.modules[name] = module
    exec(compile(read(binding), module.__file__, 'exec'), module.__dict__)
    return module.make_cli()
