#!/usr/bin/env python3
"""Offline Stage 13 feasibility arithmetic and append-only records.

This module consumes calibration evidence; it is never imported by the timed
process. All examples and tests in this repository are synthetic and do not
constitute stand calibration output.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import _pydecimal
from dataclasses import dataclass
from decimal import Decimal, Context, ROUND_CEILING, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_VERSION = "2.0.0-pre.2"
CANONICALIZATION_SUITE = "JCS-I64-v1"
MATRIX_METHOD_ID = "MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1"
ARITHMETIC_PROFILE_ID = "HOEFFDING-DECIMAL80-GUARD160-UP-v1"
WORK_PRECISION = 160
OUTPUT_PRECISION = 80
REFERENCE_PRECISION = 240
ACCEPTED_CELL_COUNT = 180
ACCEPTED_CANDIDATE_COUNT = 5
ACCEPTED_ALPHA_DENOMINATOR = 18_000
ACCEPTED_CONFIDENCE = Fraction(19, 20)
ACCEPTED_THRESHOLD = Fraction(19, 20)
ACCEPTED_LADDER = (
    Fraction(1, 1),
    Fraction(9, 10),
    Fraction(4, 5),
    Fraction(7, 10),
    Fraction(3, 5),
)
I64_MIN = -(1 << 63)
U64_MAX = (1 << 64) - 1


class CalibrationError(ValueError):
    """Fail-closed calibration error with stable category and field path."""

    def __init__(self, category: str, path: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"{self.category} {self.path}: {self.message}"


@dataclass(frozen=True, slots=True)
class ClusterRun:
    run_id: str
    offered_count: int
    full_count: int
    source_artifact_id: str | None
    source_sha256: str | None
    integrity_artifact_id: str | None
    integrity_sha256: str | None
    failure_artifact_id: str | None
    failure_sha256: str | None
    validity: str
    evidence_phase: str


@dataclass(frozen=True, slots=True)
class CellProbe:
    cell_id: str
    namespace_id: str
    schedule_id: str
    schedule_sha256: str
    planned_run_ids: tuple[str, ...]
    runs: tuple[ClusterRun, ...]
    planned_confirmatory_runs: int
    scheduled_events_per_run: int


@dataclass(frozen=True, slots=True)
class MatrixConfig:
    estimator_id: str
    arithmetic_profile_id: str
    assumptions: tuple[str, ...]
    owner_ids: tuple[str, ...]
    authority_artifact_id: str
    authority_sha256: str
    stand_budget_artifact_id: str
    stand_budget_sha256: str
    confidence_numerator: int
    confidence_denominator: int
    acceptance_threshold_numerator: int
    acceptance_threshold_denominator: int
    family_cell_count: int
    family_candidate_count: int
    planned_blocks: int
    planned_runs: int
    global_scale_numerator: int
    global_scale_denominator: int
    candidate_index: int


@dataclass(frozen=True, slots=True)
class CellBound:
    cell_id: str
    namespace_id: str
    schedule_id: str
    schedule_sha256: str
    run_decisions: tuple[ClusterRun, ...]
    offered_count: int
    full_count: int
    p_hat: Fraction
    sum_squared_weights: Fraction
    p_upper: Decimal


@dataclass(frozen=True, slots=True)
class MatrixResult:
    cell_bounds: tuple[CellBound, ...]
    namespace_id: str
    candidate_index: int
    global_scale: Fraction
    planned_blocks: int
    planned_runs: int
    planned_offered_events: int
    matrix_probability_lower: Decimal
    passes: bool


def _fail(category: str, path: str, message: str) -> None:
    raise CalibrationError(category, path, message)


def _require_exact_nonnegative(value: int, path: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail("INVALID_INTEGER", path, "value must be an exact nonnegative integer")


def _require_sha256(value: str, path: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        _fail("INVALID_HASH", path, "SHA-256 must be 64 lowercase hexadecimal digits")


def _require_id(value: str, path: str) -> None:
    if not value or "/" in value:
        _fail(
            "INVALID_ID",
            path,
            "ID must be nonempty and cannot contain a path separator",
        )


def _fraction_to_decimal_up(value: Fraction, context: Context) -> Decimal:
    with localcontext(context):
        return Decimal(value.numerator) / Decimal(value.denominator)


def _margin_up(sum_squared_weights: Fraction, precision: int) -> Decimal:
    context = Context(prec=precision, rounding=ROUND_CEILING)
    with localcontext(context):
        # Decimal.ln and sqrt are correctly rounded. Advancing one ulp after
        # each transcendental encloses any half-ulp downward rounding; all
        # intervening rational operations use ROUND_CEILING.
        logarithm = Decimal(ACCEPTED_ALPHA_DENOMINATOR).ln().next_plus()
        squared_weights = _fraction_to_decimal_up(sum_squared_weights, context)
        radicand = (logarithm * squared_weights) / Decimal(2)
        return context.sqrt(radicand).next_plus()


def _p_upper(run_counts: Iterable[tuple[int, int]], precision: int) -> tuple[Fraction, Fraction, Decimal]:
    counts = tuple(run_counts)
    if not counts:
        _fail("MISSING_EVIDENCE", "$/runs", "a cell needs at least one run cluster")
    total_offered = 0
    total_full = 0
    for index, (offered, full) in enumerate(counts):
        _require_exact_nonnegative(offered, f"$/runs/{index}/offered_count")
        _require_exact_nonnegative(full, f"$/runs/{index}/full_count")
        if offered == 0:
            _fail("ZERO_OFFERED_RUN", f"$/runs/{index}/offered_count", "zero-offered clusters are estimator-ineligible")
        if full > offered:
            _fail("COUNT_MISMATCH", f"$/runs/{index}/full_count", "FULL count exceeds offered count")
        total_offered += offered
        total_full += full
    p_hat = Fraction(total_full, total_offered)
    sum_squared_weights = sum(
        (Fraction(offered, total_offered) ** 2 for offered, _ in counts),
        start=Fraction(0, 1),
    )
    context = Context(prec=precision, rounding=ROUND_CEILING)
    with localcontext(context):
        upper = _fraction_to_decimal_up(p_hat, context) + _margin_up(
            sum_squared_weights, precision
        )
        if upper > Decimal(1):
            upper = Decimal(1)
        return p_hat, sum_squared_weights, +upper


def p_upper(run_counts: Iterable[tuple[int, int]]) -> tuple[Fraction, Fraction, Decimal]:
    """Return exact p-hat/weight sum and conservative profile-v1 p_U."""

    if sys.version_info[:2] != (3, 14):
        _fail(
            "UNSUPPORTED_RUNTIME",
            "$/python_runtime",
            "arithmetic profile v1 requires Python 3.14.x",
        )
    return _p_upper(run_counts, WORK_PRECISION)


def p_upper_reference(run_counts: Iterable[tuple[int, int]]) -> Decimal:
    """Pure-Python Decimal precision-240 reference for the C Decimal profile."""

    if sys.version_info[:2] != (3, 14):
        _fail(
            "UNSUPPORTED_RUNTIME",
            "$/python_runtime",
            "arithmetic profile v1 requires Python 3.14.x",
        )
    counts = tuple(run_counts)
    if not counts:
        _fail("MISSING_EVIDENCE", "$/runs", "a cell needs at least one run cluster")
    total_offered = 0
    total_full = 0
    for index, (offered, full) in enumerate(counts):
        _require_exact_nonnegative(offered, f"$/runs/{index}/offered_count")
        _require_exact_nonnegative(full, f"$/runs/{index}/full_count")
        if offered == 0:
            _fail(
                "ZERO_OFFERED_RUN",
                f"$/runs/{index}/offered_count",
                "zero-offered clusters are estimator-ineligible",
            )
        if full > offered:
            _fail(
                "COUNT_MISMATCH",
                f"$/runs/{index}/full_count",
                "FULL count exceeds offered count",
            )
        total_offered += offered
        total_full += full
    p_hat = Fraction(total_full, total_offered)
    weight_sum = sum(
        (Fraction(offered, total_offered) ** 2 for offered, _ in counts),
        start=Fraction(0, 1),
    )
    context = _pydecimal.Context(
        prec=REFERENCE_PRECISION, rounding=_pydecimal.ROUND_CEILING
    )
    with _pydecimal.localcontext(context):
        logarithm = _pydecimal.Decimal(ACCEPTED_ALPHA_DENOMINATOR).ln().next_plus()
        squared_weights = _pydecimal.Decimal(weight_sum.numerator) / _pydecimal.Decimal(
            weight_sum.denominator
        )
        radicand = (logarithm * squared_weights) / _pydecimal.Decimal(2)
        margin = context.sqrt(radicand).next_plus()
        upper = (
            _pydecimal.Decimal(p_hat.numerator)
            / _pydecimal.Decimal(p_hat.denominator)
        ) + margin
        if upper > _pydecimal.Decimal(1):
            upper = _pydecimal.Decimal(1)
        return Decimal(str(+upper))


def validate_matrix_config(config: MatrixConfig) -> None:
    values = (
        config.confidence_numerator,
        config.confidence_denominator,
        config.acceptance_threshold_numerator,
        config.acceptance_threshold_denominator,
        config.family_cell_count,
        config.family_candidate_count,
        config.planned_blocks,
        config.planned_runs,
        config.global_scale_numerator,
        config.global_scale_denominator,
        config.candidate_index,
    )
    for index, value in enumerate(values):
        _require_exact_nonnegative(value, f"$/config/{index}")
    if (
        config.confidence_denominator == 0
        or config.acceptance_threshold_denominator == 0
        or config.global_scale_denominator == 0
    ):
        _fail("INVALID_DENOMINATOR", "$/config", "rational denominators must be positive")
    if config.estimator_id != MATRIX_METHOD_ID:
        _fail("UNSUPPORTED_ESTIMATOR", "$/config/estimator_id", "accepted matrix estimator is required")
    if config.arithmetic_profile_id != ARITHMETIC_PROFILE_ID:
        _fail("UNSUPPORTED_ARITHMETIC", "$/config/arithmetic_profile_id", "accepted outward arithmetic profile is required")
    if not config.assumptions or any(not assumption for assumption in config.assumptions):
        _fail(
            "MISSING_ASSUMPTION",
            "$/config/assumptions",
            "the common-marginal and run-independence assumptions must be explicit",
        )
    if not config.owner_ids or len(set(config.owner_ids)) != len(config.owner_ids):
        _fail(
            "MISSING_OWNER",
            "$/config/owner_ids",
            "calibration and statistical owners must be explicit",
        )
    for index, owner in enumerate(config.owner_ids):
        _require_id(owner, f"$/config/owner_ids/{index}")
    _require_id(config.authority_artifact_id, "$/config/authority_artifact_id")
    _require_id(
        config.stand_budget_artifact_id, "$/config/stand_budget_artifact_id"
    )
    _require_sha256(config.authority_sha256, "$/config/authority_sha256")
    _require_sha256(config.stand_budget_sha256, "$/config/stand_budget_sha256")
    if Fraction(config.confidence_numerator, config.confidence_denominator) != ACCEPTED_CONFIDENCE:
        _fail("CONFIDENCE_MISMATCH", "$/config/confidence", "confidence must be the accepted 19/20")
    if Fraction(config.acceptance_threshold_numerator, config.acceptance_threshold_denominator) != ACCEPTED_THRESHOLD:
        _fail("THRESHOLD_MISMATCH", "$/config/acceptance_threshold", "threshold must be the accepted 19/20")
    if config.family_cell_count != ACCEPTED_CELL_COUNT or config.family_candidate_count != ACCEPTED_CANDIDATE_COUNT:
        _fail("FAMILY_MISMATCH", "$/config/family", "Bonferroni family must cover 180 cells and five candidates")
    if config.planned_blocks == 0 or config.planned_runs != 180 * config.planned_blocks:
        _fail(
            "PLANNED_EXPOSURE_MISMATCH",
            "$/config/planned_runs",
            "planned runs must equal 180 times the positive complete-block count",
        )
    scale = Fraction(config.global_scale_numerator, config.global_scale_denominator)
    if config.candidate_index >= len(ACCEPTED_LADDER) or ACCEPTED_LADDER[config.candidate_index] != scale:
        _fail("LADDER_MISMATCH", "$/config/global_scale", "scale and candidate index must name the accepted ladder")


def evaluate_matrix(config: MatrixConfig, cells: Iterable[CellProbe]) -> MatrixResult:
    """Evaluate one predeclared complete global-scale candidate."""

    validate_matrix_config(config)
    probes = tuple(cells)
    if len(probes) != ACCEPTED_CELL_COUNT:
        _fail("INCOMPLETE_MATRIX", "$/cells", "one candidate requires exactly 180 cells")
    cell_ids = {probe.cell_id for probe in probes}
    if len(cell_ids) != ACCEPTED_CELL_COUNT:
        _fail("DUPLICATE_CELL", "$/cells", "matrix cell IDs must be unique")
    namespaces = {probe.namespace_id for probe in probes}
    if len(namespaces) != 1:
        _fail("NAMESPACE_MISMATCH", "$/cells", "a global candidate uses one predeclared common namespace")

    bounds: list[CellBound] = []
    union_exposure = Decimal(0)
    planned_offered_events = 0
    context = Context(prec=WORK_PRECISION, rounding=ROUND_CEILING)
    with localcontext(context):
        for index, probe in enumerate(probes):
            _require_id(probe.cell_id, f"$/cells/{index}/cell_id")
            _require_id(probe.namespace_id, f"$/cells/{index}/namespace_id")
            _require_id(probe.schedule_id, f"$/cells/{index}/schedule_id")
            _require_sha256(probe.schedule_sha256, f"$/cells/{index}/schedule_sha256")
            _require_exact_nonnegative(probe.planned_confirmatory_runs, f"$/cells/{index}/planned_confirmatory_runs")
            _require_exact_nonnegative(probe.scheduled_events_per_run, f"$/cells/{index}/scheduled_events_per_run")
            if probe.planned_confirmatory_runs == 0 or probe.scheduled_events_per_run == 0:
                _fail("MISSING_EXPOSURE", f"$/cells/{index}", "Rtotal and scheduled exposure must be positive and frozen")
            if probe.planned_confirmatory_runs != config.planned_blocks:
                _fail(
                    "PLANNED_EXPOSURE_MISMATCH",
                    f"$/cells/{index}/planned_confirmatory_runs",
                    "every cell must use the frozen complete-block count",
                )
            if not probe.planned_run_ids or len(set(probe.planned_run_ids)) != len(
                probe.planned_run_ids
            ):
                _fail(
                    "INVALID_PROSPECTIVE_PLAN",
                    f"$/cells/{index}/planned_run_ids",
                    "probe run IDs must be nonempty and unique",
                )
            for run_index, planned_run_id in enumerate(probe.planned_run_ids):
                _require_id(
                    planned_run_id,
                    f"$/cells/{index}/planned_run_ids/{run_index}",
                )
            actual_run_ids = tuple(run.run_id for run in probe.runs)
            if len(set(actual_run_ids)) != len(actual_run_ids):
                _fail(
                    "DUPLICATE_RUN",
                    f"$/cells/{index}/runs",
                    "probe run evidence must be unique",
                )
            if set(actual_run_ids) != set(probe.planned_run_ids):
                _fail(
                    "INCOMPLETE_PROBE_PLAN",
                    f"$/cells/{index}/runs",
                    "missing or unplanned probe evidence cannot be topped up or omitted",
                )
            for run_index, run in enumerate(probe.runs):
                if run.evidence_phase != "CALIBRATION":
                    _fail("FORBIDDEN_OUTCOME_ACCESS", f"$/cells/{index}/runs/{run_index}/evidence_phase", "confirmatory, pilot, and treatment outcomes cannot enter calibration")
                _require_id(run.run_id, f"$/cells/{index}/runs/{run_index}/run_id")
                if run.validity == "VALID":
                    if (
                        not run.source_artifact_id
                        or run.source_sha256 is None
                        or not run.integrity_artifact_id
                        or run.integrity_sha256 is None
                    ):
                        _fail(
                            "MISSING_EVIDENCE",
                            f"$/cells/{index}/runs/{run_index}",
                            "valid probe evidence requires raw and integrity evidence",
                        )
                    _require_sha256(
                        run.source_sha256,
                        f"$/cells/{index}/runs/{run_index}/source_sha256",
                    )
                    _require_id(
                        run.source_artifact_id,
                        f"$/cells/{index}/runs/{run_index}/source_artifact_id",
                    )
                    _require_sha256(
                        run.integrity_sha256,
                        f"$/cells/{index}/runs/{run_index}/integrity_sha256",
                    )
                    _require_id(
                        run.integrity_artifact_id,
                        f"$/cells/{index}/runs/{run_index}/integrity_artifact_id",
                    )
                    if run.failure_artifact_id is not None or run.failure_sha256 is not None:
                        _fail(
                            "INVALID_FAILURE_REFERENCE",
                            f"$/cells/{index}/runs/{run_index}",
                            "valid probe evidence cannot carry a failure artifact",
                        )
                elif run.validity == "INVALID":
                    if (run.source_artifact_id is None) != (run.source_sha256 is None):
                        _fail(
                            "PARTIAL_ARTIFACT_REFERENCE",
                            f"$/cells/{index}/runs/{run_index}",
                            "an existing partial raw source needs both ID and SHA-256",
                        )
                    if run.source_sha256 is not None:
                        assert run.source_artifact_id is not None
                        _require_id(
                            run.source_artifact_id,
                            f"$/cells/{index}/runs/{run_index}/source_artifact_id",
                        )
                        _require_sha256(
                            run.source_sha256,
                            f"$/cells/{index}/runs/{run_index}/source_sha256",
                        )
                    if not run.failure_artifact_id or run.failure_sha256 is None:
                        _fail(
                            "MISSING_FAILURE",
                            f"$/cells/{index}/runs/{run_index}",
                            "invalid probe evidence requires a failure artifact",
                        )
                    _require_sha256(
                        run.failure_sha256,
                        f"$/cells/{index}/runs/{run_index}/failure_sha256",
                    )
                    _require_id(
                        run.failure_artifact_id,
                        f"$/cells/{index}/runs/{run_index}/failure_artifact_id",
                    )
                    _fail(
                        "INCOMPLETE_ESTIMATOR",
                        f"$/cells/{index}/runs/{run_index}/validity",
                        "invalid planned evidence is retained but cannot enter a smaller estimator set",
                    )
                else:
                    _fail(
                        "UNKNOWN_VALIDITY",
                        f"$/cells/{index}/runs/{run_index}/validity",
                        "run validity must be VALID or INVALID",
                    )
            p_hat, weight_sum, upper = p_upper(
                (run.offered_count, run.full_count) for run in probe.runs
            )
            offered = sum(run.offered_count for run in probe.runs)
            full = sum(run.full_count for run in probe.runs)
            exposure = probe.planned_confirmatory_runs * probe.scheduled_events_per_run
            planned_offered_events += exposure
            union_exposure += Decimal(exposure) * upper
            bounds.append(
                CellBound(
                    probe.cell_id,
                    probe.namespace_id,
                    probe.schedule_id,
                    probe.schedule_sha256,
                    probe.runs,
                    offered,
                    full,
                    p_hat,
                    weight_sum,
                    upper,
                )
            )
        lower = Decimal(1) - union_exposure
        if lower < Decimal(0):
            lower = Decimal(0)
        threshold = _fraction_to_decimal_up(ACCEPTED_THRESHOLD, context)
        return MatrixResult(
            tuple(bounds),
            next(iter(namespaces)),
            config.candidate_index,
            Fraction(config.global_scale_numerator, config.global_scale_denominator),
            config.planned_blocks,
            config.planned_runs,
            planned_offered_events,
            +lower,
            lower >= threshold,
        )


def select_first_passing_global_scale(
    results: Iterable[MatrixResult],
) -> Fraction | None:
    candidates = tuple(results)
    if not candidates or len(candidates) > len(ACCEPTED_LADDER):
        _fail(
            "LADDER_MISMATCH",
            "$/candidate_results",
            "the evaluated candidate sequence must be a nonempty ladder prefix",
        )
    if tuple(result.global_scale for result in candidates) != ACCEPTED_LADDER[
        : len(candidates)
    ] or tuple(result.candidate_index for result in candidates) != tuple(
        range(len(candidates))
    ):
        _fail(
            "LADDER_MISMATCH",
            "$/candidate_results",
            "evaluated scales must be the accepted descending prefix",
        )
    if len({result.namespace_id for result in candidates}) != len(candidates):
        _fail(
            "NAMESPACE_REUSE",
            "$/candidate_results",
            "every evaluated global candidate requires a disjoint namespace",
        )
    passing_indices = [
        index for index, result in enumerate(candidates) if result.passes
    ]
    if passing_indices:
        if passing_indices != [len(candidates) - 1]:
            _fail(
                "OUTCOME_AFTER_STOP",
                "$/candidate_results",
                "no candidate may be evaluated after the first passing scale",
            )
        return candidates[-1].global_scale
    if len(candidates) != len(ACCEPTED_LADDER):
        _fail(
            "NEXT_CANDIDATE_REQUIRED",
            "$/candidate_results",
            "a failing prefix is unresolved until its next predeclared candidate",
        )
    return None


def _validate_canonical_value(value: Any) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            _fail("INVALID_UNICODE", "$", "lone surrogate is outside JCS-I64-v1")
        return
    if isinstance(value, int):
        if value < I64_MIN or value > U64_MAX:
            _fail("INTEGER_OUT_OF_RANGE", "$", "integer is outside JCS-I64-v1")
        return
    if isinstance(value, list):
        for item in value:
            _validate_canonical_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("INVALID_OBJECT_KEY", "$", "canonical object keys must be strings")
            _validate_canonical_value(key)
            _validate_canonical_value(item)
        return
    _fail("UNSUPPORTED_NUMBER", "$", "floats and non-JSON values are forbidden")


def canonicalize(value: Any) -> bytes:
    """Serialize the restricted calibration record domain as JCS-I64-v1."""

    _validate_canonical_value(value)

    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int):
            return str(item)
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(encode(element) for element in item) + "]"
        if isinstance(item, dict):
            ordered = sorted(
                item.items(), key=lambda entry: entry[0].encode("utf-16-be")
            )
            return "{" + ",".join(
                json.dumps(key, ensure_ascii=False, separators=(",", ":"))
                + ":"
                + encode(element)
                for key, element in ordered
            ) + "}"
        raise AssertionError("canonical value was not validated")

    return encode(value).encode("utf-8")


def seal_record(record: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    """Apply CALIBRATION-JCS-I64-ZEROSELF-SHA256-v1."""

    sealed = dict(record)
    sealed["record_sha256"] = "0" * 64
    digest = hashlib.sha256(canonicalize(sealed)).hexdigest()
    sealed["record_sha256"] = digest
    return sealed, canonicalize(sealed)


def invalidation_fingerprint(material_identity: dict[str, Any]) -> str:
    """Hash every caller-enumerated material platform/software identity field."""

    if not material_identity:
        _fail(
            "MISSING_INVALIDATION_IDENTITY",
            "$/material_identity",
            "material identity cannot be empty",
        )
    return hashlib.sha256(canonicalize(material_identity)).hexdigest()


def freeze_remains_applicable(
    frozen_fingerprint_sha256: str, current_material_identity: dict[str, Any]
) -> bool:
    _require_sha256(frozen_fingerprint_sha256, "$/invalidation_fingerprint_sha256")
    return frozen_fingerprint_sha256 == invalidation_fingerprint(
        current_material_identity
    )


def publish_append_only(directory: Path, record_id: str, record_bytes: bytes) -> Path:
    """Publish one immutable record with an exclusive create and directory sync."""

    if not record_id or "/" in record_id or record_id in {".", ".."}:
        _fail("INVALID_ID", "$/record_id", "record ID cannot be interpreted as a path")
    if not directory.is_dir():
        _fail("MISSING_DIRECTORY", "$/directory", "publication directory must already exist")
    destination = directory / f"record-{hashlib.sha256(record_id.encode()).hexdigest()}.json"
    try:
        with destination.open("xb") as output:
            output.write(record_bytes)
            output.flush()
            os.fsync(output.fileno())
        directory_descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError:
        _fail("ATTEMPTED_OVERWRITE", "$/record_id", "calibration records are append-only")
    return destination


def decimal_text(value: Decimal) -> str:
    """Canonical non-exponent decimal boundary text at the 80-digit profile."""

    context = Context(prec=OUTPUT_PRECISION, rounding=ROUND_CEILING)
    with localcontext(context):
        rounded = +value
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
