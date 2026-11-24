#!/usr/bin/env python3
"""Additive successor to `stage17_operational_cli_v11.py` (ADR-0164).

`load_json` caps any local JSON input file at 64 MiB
(`64 * 1024 * 1024`) -- unconditionally, independent of the separate
64 MiB (now 128 MiB, ADR-0163) cap already fixed in `stage17_
operational_semantics_v4.py`'s `_artifact_content` (a different
function, in a different module, reached only during manifest
verification). `load_json` is the CLI's own local-file reader, called
from `author_request` (reading `--action-inputs`), `author_
authorization` (reading the just-authored request file back),
`append_resolution` (reading `--repository-evidence` files), and
several other commands.

`S17-EXT-010`'s real `STAGE17-BLINDED-PILOT` request embeds the
complete, real, admitted `S17-EXT-008` pilot plan inline as `action_
inputs.pilot_plan` (required verbatim by `stage17_phase_controller_
v10.py`'s `_validate_action_inputs`) -- both the real `action-inputs.
json` input (74,831,673 bytes) and the resulting request document
exceed 64 MiB, and are read back via `load_json` at multiple points in
the real admission flow (`author-authorization`, and every later
journal re-validation).

This mirrors ADR-0163 exactly, for the CLI module's own independent
copy of the same class of bound. A faithful full copy of `load_json`,
changed only to replace the hardcoded `64 * 1024 * 1024` bound with a
named `LOAD_JSON_MAX_BYTES = 128 * 1024 * 1024` (128 MiB).
"""

from __future__ import annotations

import json
import os
import pathlib
import stat
from typing import Any

import stage17_operational_cli_v11 as base

OperationalCliError = base.OperationalCliError

LOAD_JSON_MAX_BYTES = 128 * 1024 * 1024


def load_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > LOAD_JSON_MAX_BYTES:
            raise OperationalCliError(f"not a bounded regular file: {path}")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
    finally:
        os.close(descriptor)
    if len(payload) != metadata.st_size:
        raise OperationalCliError(f"file changed during pinned read: {path}")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exception:
        raise OperationalCliError(f"invalid JSON: {path}") from exception
    if not isinstance(document, dict):
        raise OperationalCliError(f"JSON root is not an object: {path}")
    return document, payload


base.load_json = load_json
