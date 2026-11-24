#!/usr/bin/env python3
"""Fixed Intel 06_55H prefetch-state recovery used by Stage 17 controllers.

This is deliberately not a generic MSR interface.  It exposes the single
accepted register, CPU set, mapping, and complete-value readback contract.
The synthetic branch is reachable only from separately packaged test drivers;
the production CLIs never expose a backend selector.
"""

from __future__ import annotations

import os
import struct
from typing import Any


MSR = 0x1A4
CPUS = (0, 1, 26)
MAPPING_ID = "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1"


class HardwareRecoveryError(RuntimeError):
    pass


def parse_prestate(values: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(values, list) or len(values) != len(CPUS):
        raise HardwareRecoveryError("complete three-CPU prestate is absent")
    parsed: list[tuple[int, int]] = []
    for expected_cpu, item in zip(CPUS, values, strict=True):
        if (not isinstance(item, dict) or set(item) != {
                "cpu", "complete_value_hex"}
                or item.get("cpu") != expected_cpu
                or not isinstance(item.get("complete_value_hex"), str)
                or len(item["complete_value_hex"]) != 16):
            raise HardwareRecoveryError("complete prestate is malformed")
        try:
            value = int(item["complete_value_hex"], 16)
        except ValueError as exception:
            raise HardwareRecoveryError("complete prestate is malformed") from exception
        if item["complete_value_hex"] != f"{value:016x}":
            raise HardwareRecoveryError("complete prestate is not canonical hex")
        parsed.append((expected_cpu, value))
    return tuple(parsed)


def request_prestate(action: str, request: dict[str, Any]) \
        -> tuple[tuple[int, int], ...] | None:
    values = request.get("action_inputs")
    if not isinstance(values, dict):
        raise HardwareRecoveryError("action inputs are absent")
    if action in {"Q16a", "Q16b", "Q16c"}:
        control = values.get("hardware_control")
    elif action == "STAGE17-BLINDED-PILOT":
        plan = values.get("pilot_plan")
        control = plan.get("hardware_control") if isinstance(plan, dict) else None
    else:
        return None
    if not isinstance(control, dict) or set(control) != {
            "mapping_id", "q15_w_result_sha256", "prestate"}:
        raise HardwareRecoveryError("fixed hardware-control binding is absent")
    if control.get("mapping_id") != MAPPING_ID:
        raise HardwareRecoveryError("fixed hardware-control mapping drifted")
    return parse_prestate(control.get("prestate"))


def _read(cpu: int) -> int:
    descriptor = os.open(
        f"/dev/cpu/{cpu}/msr",
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        payload = os.pread(descriptor, 8, MSR)
        if len(payload) != 8:
            raise HardwareRecoveryError("fixed MSR read was incomplete")
        return struct.unpack("<Q", payload)[0]
    finally:
        os.close(descriptor)


def _write_readback(cpu: int, value: int) -> int:
    descriptor = os.open(
        f"/dev/cpu/{cpu}/msr",
        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        payload = struct.pack("<Q", value)
        if os.pwrite(descriptor, payload, MSR) != 8:
            raise HardwareRecoveryError("fixed MSR restore write was incomplete")
        observed = os.pread(descriptor, 8, MSR)
        if len(observed) != 8:
            raise HardwareRecoveryError("fixed MSR restore readback was incomplete")
        return struct.unpack("<Q", observed)[0]
    finally:
        os.close(descriptor)


def verify(prestate: tuple[tuple[int, int], ...], *, synthetic: bool = False) \
        -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for cpu, expected in prestate:
        observed = expected if synthetic else _read(cpu)
        records.append({
            "cpu": cpu,
            "expected_hex": f"{expected:016x}",
            "observed_hex": f"{observed:016x}",
            "matches": observed == expected,
        })
    if not all(item["matches"] for item in records):
        raise HardwareRecoveryError("live MSR state differs from sealed prestate")
    return records


def restore(prestate: tuple[tuple[int, int], ...], *, synthetic: bool = False) \
        -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    failures: list[str] = []
    for cpu, expected in reversed(prestate):
        try:
            observed = expected if synthetic else _write_readback(cpu, expected)
            matches = observed == expected
        except BaseException as exception:
            observed = None
            matches = False
            failures.append(f"cpu={cpu}:{type(exception).__name__}")
        records.append({
            "cpu": cpu,
            "requested_hex": f"{expected:016x}",
            "observed_hex": f"{observed:016x}" if observed is not None else None,
            "matches": matches,
        })
    if failures or not all(item["matches"] for item in records):
        raise HardwareRecoveryError(
            "fixed restore/readback failed: " + ",".join(failures)
        )
    return records
