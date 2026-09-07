#!/usr/bin/env python3
"""Independent Python check of the shared JCS-I64-v1 boundary fixtures."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


def canonical_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("non-finite values are not JSON/JCS numbers")
    if value == 0.0:
        return "0"
    shortest = repr(value).lower()
    negative = shortest.startswith("-")
    coefficient = shortest[1:] if negative else shortest
    exponent = 0
    if "e" in coefficient:
        coefficient, exponent_text = coefficient.split("e", maxsplit=1)
        exponent = int(exponent_text)
    integer_digits = coefficient.find(".")
    if integer_digits < 0:
        integer_digits = len(coefficient)
    digits = coefficient.replace(".", "")
    decimal_position = integer_digits + exponent
    prefix = "-" if negative else ""
    magnitude = abs(value)
    if 1e-6 <= magnitude < 1e21:
        if decimal_position <= 0:
            return prefix + "0." + ("0" * -decimal_position) + digits
        if decimal_position >= len(digits):
            return prefix + digits + ("0" * (decimal_position - len(digits)))
        return (
            prefix
            + digits[:decimal_position]
            + "."
            + digits[decimal_position:]
        )
    scientific_exponent = decimal_position - 1
    coefficient_output = digits[0]
    if len(digits) > 1:
        coefficient_output += "." + digits[1:]
    sign = "+" if scientific_exponent >= 0 else "-"
    return prefix + coefficient_output + "e" + sign + str(abs(scientific_exponent))


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonicalize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if value < -(2**63) or value > 2**64 - 1:
            raise ValueError("integer is outside the JCS-I64-v1 domain")
        return str(value)
    if isinstance(value, float):
        return canonical_float(value)
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, list):
        return "[" + ",".join(canonicalize(item) for item in value) + "]"
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda item: item[0].encode("utf-16-be"))
        return (
            "{"
            + ",".join(quote(key) + ":" + canonicalize(item) for key, item in ordered)
            + "}"
        )
    raise TypeError(f"unsupported JSON value: {type(value)!r}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fixture_path = root / "tests" / "fixtures" / "jcs_i64_v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("suite") != "JCS-I64-v1":
        raise ValueError("canonical fixture suite ID is not JCS-I64-v1")
    cases = fixture.get("cases", [])
    if not cases:
        raise ValueError("canonical fixture suite is empty")
    for case in cases:
        document = json.loads(case["input"])
        actual = canonicalize(document)
        if actual != case["canonical"]:
            raise ValueError(
                f"{case['name']}: canonical mismatch: {actual!r} != "
                f"{case['canonical']!r}"
            )
    print(f"canonical-check: PASS ({len(cases)} shared JCS-I64-v1 cases)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TypeError, ValueError, KeyError) as error:
        print(f"canonical-check: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
