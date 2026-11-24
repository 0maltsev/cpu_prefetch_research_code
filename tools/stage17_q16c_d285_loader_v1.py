"""D285 explicit one-file correction over the immutable D282 cold packet.

The original manifest and every original member remain verified and unchanged.
The separately pinned D284 guard executes under its actual new file identity.
"""
import hashlib as _d285_hashlib
from pathlib import Path as _d285_Path

_D285_E = _d285_Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29')
_D285_BASE = _D285_E/'q16c-configuration-1/stage17_q16c_packet_v3.py'
_D285_BASE_SHA = 'faf1b1804a350e0d9c8b126c91364cc8f3416465c94e0e031926d23b6dcb6cbb'
_D285_TARGET = 'stage17_q16c_empty_reuse_v1'
_D285_ORIGINAL_SHA = 'ff436c39e83a0c6ce10bfcae02c9ac82925b0fb31cfc51678bcda18b279402e0'
_D285_FIXED = dict(path=str(_D285_E/'q16c-continuation-1/stage17_q16c_empty_reuse_v1.py'),
    size_bytes=10968, sha256='d1ffac09c9c2cfa2f277d93750dcca30794ea8d934421151d9fcdebd3604b1e4')


def install_exact_override(namespace, fixed_binding):
    original = namespace['load_source']
    def selected(name, path, raw):
        if name == _D285_TARGET:
            namespace['require'](_d285_hashlib.sha256(raw).hexdigest()==_D285_ORIGINAL_SHA,
                'D285 exact original guard required')
            raw = namespace['read'](fixed_binding)
            namespace['require'](_d285_hashlib.sha256(raw).hexdigest()==_D285_FIXED['sha256'],
                'D285 exact verified repair required')
            path = _d285_Path(fixed_binding['path'])
        return original(name, path, raw)
    namespace['load_source'] = selected


def _d285_bootstrap(namespace):
    raw = _D285_BASE.read_bytes()
    if _D285_BASE.is_symlink() or _d285_hashlib.sha256(raw).hexdigest()!=_D285_BASE_SHA:
        raise ValueError('D285 original loader bytes differ')
    exec(compile(raw,str(_D285_BASE),'exec'),namespace)
    namespace['read'](_D285_FIXED)
    install_exact_override(namespace,_D285_FIXED)


if __name__ == 'stage17_q16c_packet_v3':
    _d285_bootstrap(globals())
elif __name__ == '__main__':
    raise SystemExit('Use the bound D285 preparation/operator configuration')
