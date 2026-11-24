"""Bounded, pure archive JSON parsing with an explicitly bound fallback.

Proof of the acceptance guard:
* Exact bytes, ASCII input and string masking bound the speculative domain.
  At most 128 container openings bound nesting without walking the JSON tree.
* Outside strings, floats, negatives and integers of 20 or more digits fall
  back. Remaining integers are nonnegative and strictly below 10**19 < 2**64.
* A successful builtin load/dump equality proves exact object serialization.
  Duplicate keys lose an occurrence on loading and cannot survive equality.
  Non-ASCII decoded strings must have been escaped in ASCII input; dumping
  them as UTF-8 differs (or fails for lone surrogates). Thus accepted keys are
  ASCII, where Python ordering agrees with the original UTF-16 ordering.
* On that domain the builtin encoder and JCS-I64-v1 agree on all leaf types.
  Every other case delegates to the captured original callable, including all
  speculative exceptions and byte mismatches, preserving its error behavior.

There is no semantic cache, Python JSON-tree walk, or archive/global patch.
This module grants no execution authority or empirical performance claim.
"""
from __future__ import annotations

import json
import re
from typing import Callable

MAX_CONTAINERS = 128
_STRINGS = re.compile(rb'"(?:[^"\\]|\\.)*"')
_UNSAFE_NUMBER = re.compile(rb'[0-9][.eE]|-[0-9]{19}|[0-9]{20}')


def bind_parse(original: Callable[[bytes], dict]) -> Callable[[bytes], dict]:
    """Bind the caller's original parser; only proven canonical objects bypass it.

    The large-negative guard is intentionally supplemented by rejecting every
    minus outside strings: even small negative numbers use the original path.
    The caller controls the original parser's metadata/canonicalization scope.
    """
    def parse_json(raw: bytes) -> dict:
        try:
            if type(raw) is bytes and raw.isascii():
                masked = _STRINGS.sub(b'""', raw)
                if (masked.count(b'{') + masked.count(b'[') <= MAX_CONTAINERS
                        and b'-' not in masked
                        and _UNSAFE_NUMBER.search(masked) is None):
                    value = json.loads(raw.decode('utf-8', errors='strict'))
                    if (type(value) is dict
                            and json.dumps(value, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False, allow_nan=False).encode('utf-8') == raw):
                        return value
        except Exception:
            pass
        # Outside the try/except: propagate the original exception unchanged,
        # with no speculative exception attached as its context.
        return original(raw)

    return parse_json
