#!/usr/bin/env python3
"""Strict pre-marker renderer for the six Stage 17 read-only observations.

Version 2 preserves the immutable v1 program family while rejecting fractional,
malformed, and impossible capture timestamps before a one-shot marker exists.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import stage17_read_only_preflight_collector_v1 as collector_v1


COLLECTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-COLLECTOR-v2"
OBSERVATION_IDS = collector_v1.OBSERVATION_IDS
_SECOND_UTC = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


class CollectorContractError(ValueError):
    """Typed observation input is invalid before marker creation."""


def validate_exact_second_utc(value: object, label: str = "captured_at_utc") -> str:
    if not isinstance(value, str) or _SECOND_UTC.fullmatch(value) is None:
        raise CollectorContractError(f"{label} is not exact second-precision UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise CollectorContractError(f"{label} is not a possible UTC instant") from exception
    if parsed.tzinfo != dt.timezone.utc or parsed.microsecond != 0:
        raise CollectorContractError(f"{label} is not exact second-precision UTC")
    return value


def render_observation_program(
    observation_id: str, context: dict[str, Any]
) -> bytes:
    """Validate the complete typed context, then render immutable v1 semantics."""

    validate_exact_second_utc(context.get("captured_at_utc"))
    try:
        program = collector_v1.render_observation_program(observation_id, context)
    except collector_v1.CollectorContractError as exception:
        raise CollectorContractError(str(exception)) from exception
    compile(program, f"<stage17:{observation_id}>", "exec")
    return program
