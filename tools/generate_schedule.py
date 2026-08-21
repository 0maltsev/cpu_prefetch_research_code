#!/usr/bin/env python3
"""Generate an ADR-0029 deterministic open-loop arrival schedule."""

from __future__ import annotations

import argparse
import decimal
import hashlib
import hmac
import json
import math
import os
import re
import struct
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2.0.0-pre.2"
# ADR-0025/0029 froze this label into deterministic hash/key preimages.
DERIVATION_DOMAIN_PROTOCOL_VERSION = "2.0.0-pre.1"
BASE_RNG_SUITE = "PHILOX4X32-10-HMAC-SHA256-v1"
SCHEDULE_ALGORITHM = "POISSON-EXPONENTIAL-PHILOX-DECIMAL80-FLOOR-ABS-PS"
SCHEDULE_VERSION = "1"
SCHEDULE_SUITE = f"{SCHEDULE_ALGORITHM}-v{SCHEDULE_VERSION}"
TIME_UNIT = "ps"
DEADLINE_ENCODING = "ABSOLUTE_INTEGER_TICKS"
ARTIFACT_FORMAT = "SCHEDULE-ABS-U64BE-v1"
OVERFLOW_RULE = "SCHEDULE-U64-ABS-FAIL-CLOSED-v1"
DECODED_HASH_ALGORITHM = "DECODED-DEADLINES-U64BE-SHA256-v1"
ENVELOPE_HASH_PROFILE = "SCHEDULE-JCS-I64-ZEROSELF-SHA256-v1"
DERIVATION_SCHEMA = "cpu-prefetch-schedule-derivation-v1"
DERIVATION_HASH_PROFILE = "SCHEDULE-DERIVATION-JCS-I64-ZEROSELF-SHA256-v1"
PURPOSE = "arrival-schedule"
UINT64_MAX = (1 << 64) - 1
UINT32_MASK = (1 << 32) - 1
DECIMAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)\Z")
HEX_SEED = re.compile(r"[0-9a-fA-F]{64}\Z")
SUPPORTED_KINDS = frozenset(
    {"WARMUP", "CALIBRATION", "PILOT", "CONFIRMATORY", "DIAGNOSTIC"}
)


class ScheduleGenerationError(ValueError):
    """A fail-closed schedule error with a stable category and field path."""

    def __init__(self, category: str, path: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"{self.category} {self.path}: {self.message}"


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    schedule_id: str
    schedule_kind: str
    namespace_id: str
    parent_namespace_id: str
    seed_id: str
    derivation_record_id: str
    master_seed: bytes
    origin_ticks: int
    horizon_ticks: int
    numerator_events: int
    denominator_ticks: int
    artifact_id: str
    artifact_uri: str


@dataclass(frozen=True, slots=True)
class GeneratedSchedule:
    deadlines: tuple[int, ...]
    artifact_bytes: bytes
    envelope_bytes: bytes
    derivation_record_bytes: bytes
    artifact_sha256: str
    decoded_deadlines_sha256: str
    schedule_sha256: str
    derivation_record_sha256: str


def _fail(category: str, path: str, message: str) -> None:
    raise ScheduleGenerationError(category, path, message)


def _require_id(value: str, path: str) -> None:
    if not value:
        _fail("INVALID_ID", path, "identifier must not be empty")


def validate_spec(spec: ScheduleSpec) -> None:
    for path, value in (
        ("schedule_id", spec.schedule_id),
        ("namespace_id", spec.namespace_id),
        ("parent_namespace_id", spec.parent_namespace_id),
        ("seed_id", spec.seed_id),
        ("derivation_record_id", spec.derivation_record_id),
        ("artifact_id", spec.artifact_id),
        ("artifact_uri", spec.artifact_uri),
    ):
        _require_id(value, path)
    if spec.schedule_kind not in SUPPORTED_KINDS:
        _fail(
            "UNSUPPORTED_SCHEDULE_KIND",
            "schedule_kind",
            "the Stage 7 generator supports Stage A preparation roles only",
        )
    if len(spec.master_seed) != 32:
        _fail("INVALID_SEED", "master_seed", "master seed must contain 256 bits")
    for path, value in (
        ("origin_ticks", spec.origin_ticks),
        ("horizon_ticks", spec.horizon_ticks),
        ("numerator_events", spec.numerator_events),
        ("denominator_ticks", spec.denominator_ticks),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            _fail("INVALID_INTEGER", path, "value must be an exact integer")
        if value < 0 or value > UINT64_MAX:
            _fail("INTEGER_OUT_OF_RANGE", path, "value is outside uint64")
    if spec.horizon_ticks == 0:
        _fail("HORIZON_INVALID", "horizon_ticks", "horizon must be positive")
    if spec.numerator_events == 0 or spec.denominator_ticks == 0:
        _fail("RATE_INVALID", "nominal_offered_rate", "rate fields must be positive")
    if math.gcd(spec.numerator_events, spec.denominator_ticks) != 1:
        _fail(
            "RATE_NONCANONICAL",
            "nominal_offered_rate",
            "rate numerator and denominator must already be reduced",
        )
    if spec.horizon_ticks > UINT64_MAX - spec.origin_ticks:
        _fail(
            "HORIZON_OVERFLOW",
            "horizon_ticks",
            "origin plus horizon overflows uint64",
        )


def _require_python_runtime() -> None:
    if sys.version_info[:2] != (3, 14):
        _fail(
            "UNSUPPORTED_RUNTIME",
            "python_version",
            "ADR-0029 requires Python 3.14.x",
        )


def _append_field(output: bytearray, value: bytes) -> None:
    if len(value) > UINT64_MAX:
        _fail("BYTE_COUNT_OVERFLOW", "hash_preimage", "field length exceeds uint64")
    output.extend(struct.pack(">Q", len(value)))
    output.extend(value)


def _derive_key(master_seed: bytes, namespace_id: str) -> tuple[int, int]:
    message = bytearray()
    for value in (
        DERIVATION_DOMAIN_PROTOCOL_VERSION,
        BASE_RNG_SUITE,
        namespace_id,
        PURPOSE,
    ):
        _append_field(message, value.encode("utf-8"))
    digest = hmac.new(master_seed, message, hashlib.sha256).digest()
    return struct.unpack(">II", digest[:8])


def _philox_draw(key: tuple[int, int], draw_ordinal: int) -> int:
    block_ordinal = draw_ordinal // 2
    counter = [block_ordinal >> 32, block_ordinal & UINT32_MASK, 0, 0]
    round_key = [key[0], key[1]]
    for round_index in range(10):
        product0 = 0xD2511F53 * counter[0]
        product1 = 0xCD9E8D57 * counter[2]
        counter = [
            ((product1 >> 32) ^ counter[1] ^ round_key[0]) & UINT32_MASK,
            product1 & UINT32_MASK,
            ((product0 >> 32) ^ counter[3] ^ round_key[1]) & UINT32_MASK,
            product0 & UINT32_MASK,
        ]
        if round_index != 9:
            round_key[0] = (round_key[0] + 0x9E3779B9) & UINT32_MASK
            round_key[1] = (round_key[1] + 0xBB67AE85) & UINT32_MASK
    word = 0 if draw_ordinal % 2 == 0 else 2
    return (counter[word] << 32) | counter[word + 1]


def _decimal_context(module: Any) -> Any:
    context = module.Context(
        prec=80,
        rounding=module.ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
    )
    for signal in (
        module.InvalidOperation,
        module.DivisionByZero,
        module.Overflow,
        module.Underflow,
        module.Subnormal,
        module.FloatOperation,
    ):
        context.traps[signal] = True
    context.clear_flags()
    return context


def _advance_cumulative(
    active: Any,
    module: Any,
    total: Any,
    draw: int,
    numerator_events: int,
    denominator_ticks: int,
) -> Any:
    unit = active.divide(
        module.Decimal((2 * draw) + 1), module.Decimal(1 << 65)
    )
    inverse = active.ln(unit).copy_negate()
    scaled = active.divide(
        active.multiply(inverse, module.Decimal(denominator_ticks)),
        module.Decimal(numerator_events),
    )
    return active.add(total, scaled)


def _transform_draws_for_test(
    draws: tuple[int, ...],
    numerator_events: int,
    denominator_ticks: int,
    module: Any = decimal,
) -> tuple[int, ...]:
    """Finite direct-transform seam for accepted boundary-vector verification."""

    if numerator_events <= 0 or denominator_ticks <= 0:
        _fail("RATE_INVALID", "nominal_offered_rate", "rate fields must be positive")
    if math.gcd(numerator_events, denominator_ticks) != 1:
        _fail("RATE_NONCANONICAL", "nominal_offered_rate", "rate must be reduced")
    context = _decimal_context(module)
    total = module.Decimal(0)
    offsets: list[int] = []
    with module.localcontext(context) as active:
        for draw in draws:
            if draw < 0 or draw > UINT64_MAX:
                _fail("RNG_INVALID", "draw", "RNG draw is outside uint64")
            next_total = _advance_cumulative(
                active,
                module,
                total,
                draw,
                numerator_events,
                denominator_ticks,
            )
            if not next_total.is_finite() or next_total <= total:
                _fail("DECIMAL_NONPROGRESS", "cumulative_time", "invalid progress")
            total = next_total
            offsets.append(
                int(
                    total.to_integral_value(
                        rounding=module.ROUND_FLOOR, context=active
                    )
                )
            )
    return tuple(offsets)


def _generate_deadlines(
    spec: ScheduleSpec,
    draw_at: Callable[[int], int],
    module: Any = decimal,
    max_draw_ordinal: int = UINT64_MAX,
) -> tuple[int, ...]:
    """Internal deterministic seam; production always uses the uint64 draw limit."""

    validate_spec(spec)
    if max_draw_ordinal < 0 or max_draw_ordinal > UINT64_MAX:
        _fail("DRAW_EXHAUSTION", "draw_ordinal", "invalid draw-ordinal limit")
    horizon_end = spec.origin_ticks + spec.horizon_ticks
    context = _decimal_context(module)
    deadlines: list[int] = []
    total = module.Decimal(0)
    draw_ordinal = 0
    try:
        with module.localcontext(context) as active:
            while True:
                draw = draw_at(draw_ordinal)
                if not isinstance(draw, int) or isinstance(draw, bool):
                    _fail("RNG_INVALID", "draw", "RNG draw must be an unsigned integer")
                if draw < 0 or draw > UINT64_MAX:
                    _fail("RNG_INVALID", "draw", "RNG draw is outside uint64")
                next_total = _advance_cumulative(
                    active,
                    module,
                    total,
                    draw,
                    spec.numerator_events,
                    spec.denominator_ticks,
                )
                if not next_total.is_finite():
                    _fail("DECIMAL_FAILURE", "cumulative_time", "nonfinite decimal")
                if next_total <= total:
                    _fail(
                        "DECIMAL_NONPROGRESS",
                        "cumulative_time",
                        "rounded cumulative time did not increase",
                    )
                total = next_total
                offset = int(
                    total.to_integral_value(
                        rounding=module.ROUND_FLOOR, context=active
                    )
                )
                if offset < 0 or offset > UINT64_MAX - spec.origin_ticks:
                    _fail("DEADLINE_OVERFLOW", "deadline", "deadline exceeds uint64")
                deadline = spec.origin_ticks + offset
                if deadline >= horizon_end:
                    return tuple(deadlines)
                if len(deadlines) >= UINT64_MAX // 8:
                    _fail(
                        "BYTE_COUNT_OVERFLOW",
                        "offered_count",
                        "encoded byte count exceeds uint64",
                    )
                deadlines.append(deadline)
                if draw_ordinal == max_draw_ordinal:
                    _fail(
                        "DRAW_EXHAUSTION",
                        "draw_ordinal",
                        "another candidate is required after the last draw ordinal",
                    )
                draw_ordinal += 1
    except ScheduleGenerationError:
        raise
    except (ArithmeticError, ValueError) as error:
        _fail("DECIMAL_FAILURE", "cumulative_time", str(error))
    except MemoryError:
        _fail("PUBLICATION_FAILURE", "deadlines", "schedule allocation failed")
    raise AssertionError("unreachable schedule generator state")


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _canonical_float(value: float) -> str:
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
        return prefix + digits[:decimal_position] + "." + digits[decimal_position:]
    scientific_exponent = decimal_position - 1
    coefficient_output = digits[0]
    if len(digits) > 1:
        coefficient_output += "." + digits[1:]
    sign = "+" if scientific_exponent >= 0 else "-"
    return prefix + coefficient_output + "e" + sign + str(abs(scientific_exponent))


def canonicalize(value: Any) -> str:
    """ADR-0015 JCS-I64-v1 canonical serialization."""

    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if value < -(1 << 63) or value > UINT64_MAX:
            raise ValueError("integer is outside the JCS-I64-v1 domain")
        return str(value)
    if isinstance(value, float):
        return _canonical_float(value)
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, list):
        return "[" + ",".join(canonicalize(item) for item in value) + "]"
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda item: item[0].encode("utf-16-be"))
        return "{" + ",".join(
            _quote(key) + ":" + canonicalize(item) for key, item in ordered
        ) + "}"
    raise TypeError(f"unsupported JSON value: {type(value)!r}")


def _decoded_hash(spec: ScheduleSpec, deadlines: tuple[int, ...]) -> str:
    preimage = bytearray()
    for value in (
        b"cpu-prefetch/decoded-deadlines-sha256/v1",
        DERIVATION_DOMAIN_PROTOCOL_VERSION.encode(),
        SCHEDULE_SUITE.encode(),
        TIME_UNIT.encode(),
        struct.pack(">Q", spec.origin_ticks),
        struct.pack(">Q", spec.horizon_ticks),
        struct.pack(">Q", spec.numerator_events),
        struct.pack(">Q", spec.denominator_ticks),
        struct.pack(">Q", len(deadlines)),
    ):
        _append_field(preimage, value)
    for deadline in deadlines:
        _append_field(preimage, struct.pack(">Q", deadline))
    return hashlib.sha256(preimage).hexdigest()


def generate_schedule(spec: ScheduleSpec) -> GeneratedSchedule:
    _require_python_runtime()
    validate_spec(spec)
    key = _derive_key(spec.master_seed, spec.namespace_id)
    deadlines = _generate_deadlines(spec, lambda ordinal: _philox_draw(key, ordinal))
    artifact = b"".join(struct.pack(">Q", deadline) for deadline in deadlines)
    artifact_sha256 = hashlib.sha256(artifact).hexdigest()
    decoded_sha256 = _decoded_hash(spec, deadlines)
    derivation_record: dict[str, Any] = {
        "record_schema": DERIVATION_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "record_id": spec.derivation_record_id,
        "schedule_suite": SCHEDULE_SUITE,
        "base_rng_suite": BASE_RNG_SUITE,
        "purpose": PURPOSE,
        "seed_id": spec.seed_id,
        "parent_namespace_id": spec.parent_namespace_id,
        "namespace_id": spec.namespace_id,
        "derived_key_u32be_hex": f"{key[0]:08x}{key[1]:08x}",
        "python_version": ".".join(str(value) for value in sys.version_info[:3]),
        "decimal_version": decimal.__version__,
        "libmpdec_version": decimal.__libmpdec_version__,
        "canonicalization_suite": "JCS-I64-v1",
        "record_hash_profile": DERIVATION_HASH_PROFILE,
        "record_sha256": "0" * 64,
    }
    envelope: dict[str, Any] = {
        "schema_version": PROTOCOL_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "schedule_id": spec.schedule_id,
        "schedule_kind": spec.schedule_kind,
        "arrival_family": "POISSON_EXPONENTIAL",
        "namespace_id": spec.namespace_id,
        "rng": {
            "algorithm": SCHEDULE_ALGORITHM,
            "version": SCHEDULE_VERSION,
            "seed_id": spec.seed_id,
            "derivation_record_id": spec.derivation_record_id,
            "parent_namespace_id": spec.parent_namespace_id,
        },
        "time_unit": TIME_UNIT,
        "deadline_encoding": DEADLINE_ENCODING,
        "origin_ticks": spec.origin_ticks,
        "horizon_ticks": spec.horizon_ticks,
        "inclusion_boundary": {"start_inclusive": True, "end_exclusive": True},
        "offered_count": len(deadlines),
        "nominal_offered_rate": {
            "numerator_events": spec.numerator_events,
            "denominator_ticks": spec.denominator_ticks,
        },
        "overflow_rule_record_id": OVERFLOW_RULE,
        "immutable_ordering": True,
        "deadline_storage": {
            "mode": "EXTERNAL_IMMUTABLE_ARTIFACT",
            "artifact_id": spec.artifact_id,
            "artifact_uri": spec.artifact_uri,
            "row_count": len(deadlines),
            "byte_count": len(artifact),
            "artifact_sha256": artifact_sha256,
        },
        "decoded_deadlines_sha256": decoded_sha256,
        "schedule_sha256": "0" * 64,
    }
    try:
        derivation_record_sha256 = hashlib.sha256(
            canonicalize(derivation_record).encode()
        ).hexdigest()
        derivation_record["record_sha256"] = derivation_record_sha256
        derivation_record_bytes = canonicalize(derivation_record).encode() + b"\n"
        schedule_sha256 = hashlib.sha256(canonicalize(envelope).encode()).hexdigest()
        envelope["schedule_sha256"] = schedule_sha256
        envelope_bytes = canonicalize(envelope).encode() + b"\n"
    except (TypeError, ValueError, UnicodeError) as error:
        _fail("CANONICALIZATION_FAILURE", "schedule", str(error))
    return GeneratedSchedule(
        deadlines,
        artifact,
        envelope_bytes,
        derivation_record_bytes,
        artifact_sha256,
        decoded_sha256,
        schedule_sha256,
        derivation_record_sha256,
    )


def _stage_file(path: Path, data: bytes) -> Path:
    if not path.parent.is_dir():
        _fail("PUBLICATION_FAILURE", str(path), "parent directory does not exist")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def publish_schedule(
    generated: GeneratedSchedule,
    artifact_path: Path,
    envelope_path: Path,
    derivation_record_path: Path,
) -> None:
    # The schedule envelope is the commit record and is linked last. A crash
    # before that point can leave only unreferenced bytes, never a valid
    # envelope that points at a missing artifact or derivation record.
    outputs = {
        derivation_record_path: generated.derivation_record_bytes,
        artifact_path: generated.artifact_bytes,
        envelope_path: generated.envelope_bytes,
    }
    if len(outputs) != 3:
        _fail(
            "PUBLICATION_FAILURE", "output", "all three output paths must differ"
        )
    staged: dict[Path, Path] = {}
    linked: list[Path] = []
    try:
        for path, data in outputs.items():
            staged[path] = _stage_file(path, data)
        for path, temporary in staged.items():
            os.link(temporary, path)
            linked.append(path)
    except ScheduleGenerationError:
        raise
    except OSError as error:
        _fail("PUBLICATION_FAILURE", "output", str(error))
    finally:
        if len(linked) != len(outputs):
            for path in linked:
                path.unlink(missing_ok=True)
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _u64_argument(text: str) -> int:
    if DECIMAL_INTEGER.fullmatch(text) is None:
        raise argparse.ArgumentTypeError("expected canonical unsigned decimal integer")
    value = int(text)
    if value > UINT64_MAX:
        raise argparse.ArgumentTypeError("integer is outside uint64")
    return value


def _seed_argument(text: str) -> bytes:
    if HEX_SEED.fullmatch(text) is None:
        raise argparse.ArgumentTypeError("expected exactly 64 hexadecimal digits")
    return bytes.fromhex(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an ADR-0029 schedule before measurement"
    )
    parser.add_argument("--schedule-id", required=True)
    parser.add_argument("--schedule-kind", required=True, choices=sorted(SUPPORTED_KINDS))
    parser.add_argument("--namespace-id", required=True)
    parser.add_argument("--parent-namespace-id", required=True)
    parser.add_argument("--seed-id", required=True)
    parser.add_argument("--derivation-record-id", required=True)
    parser.add_argument("--master-seed-hex", required=True, type=_seed_argument)
    parser.add_argument("--origin-ticks", required=True, type=_u64_argument)
    parser.add_argument("--horizon-ticks", required=True, type=_u64_argument)
    parser.add_argument("--rate-numerator-events", required=True, type=_u64_argument)
    parser.add_argument("--rate-denominator-ticks", required=True, type=_u64_argument)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--artifact-uri", required=True)
    parser.add_argument("--output-artifact", required=True, type=Path)
    parser.add_argument("--output-envelope", required=True, type=Path)
    parser.add_argument("--output-derivation-record", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    spec = ScheduleSpec(
        schedule_id=arguments.schedule_id,
        schedule_kind=arguments.schedule_kind,
        namespace_id=arguments.namespace_id,
        parent_namespace_id=arguments.parent_namespace_id,
        seed_id=arguments.seed_id,
        derivation_record_id=arguments.derivation_record_id,
        master_seed=arguments.master_seed_hex,
        origin_ticks=arguments.origin_ticks,
        horizon_ticks=arguments.horizon_ticks,
        numerator_events=arguments.rate_numerator_events,
        denominator_ticks=arguments.rate_denominator_ticks,
        artifact_id=arguments.artifact_id,
        artifact_uri=arguments.artifact_uri,
    )
    try:
        generated = generate_schedule(spec)
        publish_schedule(
            generated,
            arguments.output_artifact,
            arguments.output_envelope,
            arguments.output_derivation_record,
        )
    except ScheduleGenerationError as error:
        print(f"schedule-generation: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "schedule-generation: PASS "
        f"(count={len(generated.deadlines)}, artifact_sha256={generated.artifact_sha256}, "
        f"decoded_sha256={generated.decoded_deadlines_sha256}, "
        f"schedule_sha256={generated.schedule_sha256}, "
        f"derivation_sha256={generated.derivation_record_sha256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
