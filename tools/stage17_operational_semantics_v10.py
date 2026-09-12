#!/usr/bin/env python3
"""Additive successor to `stage17_operational_semantics_v4.py` (ADR-0163).

`_artifact_content` caps any fully-parsed ("load") artifact at 64 MiB
(`64 * 1024 * 1024`). The real, locally-validated `S17-EXT-008` pilot
plan (`config/stage17/ext008-pilot-plan-standv2-30.json`,
68,832,714 bytes) is a single required `PILOT_PLAN_V4` artifact that
must be fully parsed (`pilot_plan_runtime.validate()` needs the parsed
document), so it is subject to this cap -- and exceeds it by about
1.7 MiB. The real size is not padding: roughly 85% of it is the
genuine, schema-required per-run `schedule_deadline_ticks`/
`warmup_schedule_deadline_ticks` arrays for 540 real runs (each run
object must carry its own complete copy, per the schema's `run`
definition -- there is no more compact in-schema representation).

This mirrors the precedent already set in this engagement for exactly
this class of problem: the Python-side `MAX_BOUND_INPUT_BYTES` was
previously raised to match the C++ side when a real artifact
legitimately exceeded the old bound. Here the successor raises the
64 MiB cap to 128 MiB (comfortable headroom over the real artifact's
size, while still a bounded, defensive limit rather than no limit at
all) and otherwise faithfully copies `_artifact_content` unchanged.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import stat
from typing import Any

import stage17_operational_semantics_v4 as base

OperationalSemanticError = base.OperationalSemanticError

LOAD_ARTIFACT_MAX_BYTES = 128 * 1024 * 1024


def _artifact_content(
    manifest_path: pathlib.Path, locator: Any, *, load: bool,
    expected_size: int,
) -> tuple[pathlib.Path, bytes | None, int, str]:
    if not isinstance(locator, str):
        raise OperationalSemanticError("artifact locator is absent")
    relative = pathlib.PurePosixPath(locator)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise OperationalSemanticError("artifact locator is not manifest-relative")
    descriptor = os.open(
        manifest_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for index, part in enumerate(relative.parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if index + 1 < len(relative.parts):
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != expected_size
                or (load and metadata.st_size > LOAD_ARTIFACT_MAX_BYTES)):
            raise OperationalSemanticError(
                "artifact size/type differs from its bounded contract"
            )
        digest = hashlib.sha256()
        chunks: list[bytes] | None = [] if load else None
        offset = 0
        while offset != metadata.st_size:
            chunk = os.pread(
                descriptor, min(1024 * 1024, metadata.st_size - offset), offset
            )
            if not chunk:
                raise OperationalSemanticError(
                    "artifact changed during streaming verification"
                )
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino, after.st_size) != (
            metadata.st_dev, metadata.st_ino, metadata.st_size
        ):
            raise OperationalSemanticError(
                "artifact identity changed during streaming verification"
            )
        payload = b"".join(chunks) if chunks is not None else None
        return (
            manifest_path.parent.joinpath(*relative.parts), payload,
            metadata.st_size, digest.hexdigest(),
        )
    except OSError as exception:
        raise OperationalSemanticError("artifact locator cannot be opened safely") from exception
    finally:
        if descriptor >= 0:
            os.close(descriptor)


base._artifact_content = _artifact_content
