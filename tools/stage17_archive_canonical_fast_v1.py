"""Exact JCS-I64-v1 bytes with a guarded builtin JSON-tree fast path.

ASCII object keys have identical UTF-16 and Python sort order. With only
builtin integer/boolean/null/string leaves, the C JSON encoder emits the same
bytes as the original canonicalizer. Every other input uses the original
implementation, including its numeric formatting and error behavior.
"""
from __future__ import annotations

import json

import check_canonical as original

MAX_DEPTH = 128
MIN_INTEGER = -(1 << 63)
MAX_INTEGER = (1 << 64) - 1


def canonical(value) -> bytes:
    pending = [(value, 0)]
    seen = set()
    while pending:
        item, depth = pending.pop()
        kind = type(item)
        if kind is int:
            if not MIN_INTEGER <= item <= MAX_INTEGER:
                break
        elif kind is str or kind is bool or item is None:
            continue
        elif kind is list or kind is dict:
            # A container at depth zero is the first nesting level. Shared
            # containers fall back even when acyclic; no alias is inferred safe.
            if depth >= MAX_DEPTH or id(item) in seen:
                break
            seen.add(id(item))
            if kind is dict:
                if any(type(key) is not str or not key.isascii() for key in item):
                    break
                children = item.values()
            else:
                children = item
            pending.extend((child, depth + 1) for child in children)
        else:
            break
    else:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    return original.canonicalize(value).encode('utf-8')
