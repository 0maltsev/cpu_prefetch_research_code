#!/usr/bin/env python3
"""Operational-semantics successor completing ADR-0160: `_phase_family`
(defined once, in `stage17_operational_semantics_v4.py`) enforces a
hard `<=1800` second authorization-lifetime bound on every action it
cross-validates, uniformly -- discovered live only now, while
admitting `S17-EXT-007` (the calibration freeze), which is the first
and only code path that ever calls `_phase_family` on `Q16b`'s own
authorization. `Q15-R`/`Q15-W` (validated by `S17-EXT-004`/`S17-EXT-005`)
both use the real, fixed 30-minute (1800s) `ONE_SHOT_ACTION` window and
never tripped this; `Q16b`'s real, live authorization used ADR-0160's
own frozen `session_max_wall_seconds=3600` `DURABLE_PILOT_SESSION`
window (59 real minutes), which this check had never been updated to
recognize.

This is the same bare-name free-variable-resolution case already
fixed three times this session (`prepare_action`, `execute_fixed_
action`, `_validate_run_families`): `_phase_family`'s own three real
callers (all defined in `v4.py` itself, at `S17-EXT-004`/`S17-EXT-005`/
`S17-EXT-007`'s own branches) reach it via a bare name resolved
against `v4.py`'s own module globals, so a fresh copy here, faithful
to `v4`'s own body except for the one targeted widening, monkey-
patched onto `v4`'s own module attribute, is sufficient -- no further
rebinding needed.

Unlike the two ADR-0160 fixes already committed (`stage17_phase_
controller_v18.py`'s `prepare_action`, `stage17_fixed_action_executor_
v6.py`'s `execute_fixed_action`), this function is exercised only at
admission time (Python-side bookkeeping over already-completed,
already-signed real evidence), not by the compiled worker itself, and
its own already-sealed `standv2-30` admission-root was never going to
need this exact cross-check until `S17-EXT-007` was attempted -- so
this fix is deployed here via a local wrapper (mirroring the `q15_
session_journal_runtime_patch_standv2-30.py` precedent) rather than a
new bundle/journal: no real hardware evidence changes, only which
authorization-lifetime bound this one Python-side check accepts for
`Q16b` specifically.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
from typing import Any

import stage17_operational_semantics_v4 as base

ACTION_PREFIX = base.ACTION_PREFIX
_one = base._one
verify_sshsig = base.verify_sshsig
sha = base.sha
_parse_utc = base._parse_utc
OperationalSemanticError = base.OperationalSemanticError
output_registry = base.output_registry

# ADR-0160: the same fixed bound tools/stage17_phase_controller_v18.py's
# own prepare_action and tools/stage17_fixed_action_executor_v6.py's own
# execute_fixed_action already re-validate the signed authorization
# against for Q16b specifically.
Q16B_SESSION_MAX_WALL_SECONDS = 3600


def _phase_family(
    *, root: pathlib.Path, artifacts: list[Any], action_id: str,
    trust: dict[str, Any], expected_predecessors: list[dict[str, str]],
    synthetic_test_only: bool,
) -> dict[str, Any]:
    prefix = ACTION_PREFIX[action_id]
    authorization = _one(artifacts, prefix + "_AUTHORIZATION")
    signature = _one(artifacts, prefix + "_SIGNATURE")
    request = _one(artifacts, prefix + "_REQUEST")
    attempt = _one(artifacts, prefix + "_ATTEMPT")
    result = _one(artifacts, prefix + "_RESULT")
    completion = None if action_id == "Q15-R" else _one(
        artifacts, prefix + "_COMPLETION"
    )
    waiting = _one(artifacts, "Q15_R_SESSION_WAITING") \
        if action_id == "Q15-R" else None
    typed = (authorization, request, attempt, result) + (
        (waiting,) if waiting is not None else (completion,)
    )
    assert all(item is not None and item.document is not None for item in typed)
    verify_sshsig(authorization=authorization, signature=signature,
                  trust_record=trust)
    auth, req, att, res = (
        item.document for item in (authorization, request, attempt, result)
    )
    comp = completion.document if completion is not None else None
    auth_hash, request_hash = sha(authorization.payload), sha(request.payload)
    if (auth["action_id"] != action_id or req["action_id"] != action_id
            or att["action_id"] != action_id or res["action_id"] != action_id
            or (comp is not None and comp["action_id"] != action_id)):
        raise OperationalSemanticError("phase action identity drifted")
    maximum_lifetime_seconds = (
        Q16B_SESSION_MAX_WALL_SECONDS if action_id == "Q16b" else 1800
    )
    if (not _parse_utc(auth["issued_at_utc"]) < _parse_utc(auth["expires_at_utc"])
            or _parse_utc(auth["expires_at_utc"]) - _parse_utc(auth["issued_at_utc"])
            > dt.timedelta(seconds=maximum_lifetime_seconds)):
        raise OperationalSemanticError("phase authorization lifetime drifted")
    if (auth["predecessor_resolutions"] != expected_predecessors
            or req["predecessor_resolutions"] != expected_predecessors):
        raise OperationalSemanticError("phase predecessor lineage drifted")
    if auth["request_binding"] != {
        "path": str(request.path), "size_bytes": len(request.payload),
        "sha256": request_hash,
    }:
        raise OperationalSemanticError("authorization does not bind exact request bytes")
    if (req["authorization_id"] != auth["authorization_id"]
            or req["synthetic_test_only"] is not synthetic_test_only
            or att["authorization_sha256"] != auth_hash
            or att["request_sha256"] != request_hash
            or res["authorization_sha256"] != auth_hash
            or res["request_sha256"] != request_hash
            or res["attempt_id"] != att["attempt_id"]
            or (comp is not None and (
                comp["authorization_sha256"] != auth_hash
                or comp["request_sha256"] != request_hash
                or comp["attempt_id"] != att["attempt_id"]
                or not comp["leader_reaped"]
                or not comp["process_group_gone"]
            ))):
        raise OperationalSemanticError("phase attempt/result/completion lineage drifted")
    if waiting is not None:
        wait = waiting.document
        assert wait is not None
        if (wait["session_id"] != req["action_inputs"]["session_id"]
                or wait["q15_r_request_sha256"] != request_hash
                or wait["q15_r_result_sha256"] != sha(result.payload)
                or wait["state"] != "H0_SEALED_WAITING_FOR_Q15_W"
                or not wait["same_buffer_retained"]):
            raise OperationalSemanticError("Q15-R waiting/session lineage drifted")
    registry = output_registry.pin_registry(root)
    output_directory = result.path.parent
    descriptor = os.open(
        output_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        output_registry.validate_worker_result(
            registry=registry, directory_fd=descriptor, result=res, request=req,
            authorization_sha256=auth_hash,
            synthetic_test_only=synthetic_test_only,
        )
    except output_registry.OutputAdmissionError as exception:
        raise OperationalSemanticError(str(exception)) from exception
    finally:
        os.close(descriptor)
    by_path: dict[pathlib.Path, Any] = {}
    for item in artifacts:
        if item.path in by_path:
            raise OperationalSemanticError("action manifest path is duplicated")
        by_path[item.path] = item
    for binding in res["artifacts"]:
        match = by_path.get(result.path.parent / binding["file_name"])
        if (match is None or match.role != binding["role"]
                or match.reference["size_bytes"] != binding["size_bytes"]
                or match.reference["sha256"] != binding["sha256"]
                or match.reference["schema_identity"]
                != binding["schema_identity"]):
            raise OperationalSemanticError(
                "action manifest does not list exact worker output: "
                f"action={action_id} file={binding['file_name']} "
                f"expected_role={binding['role']} "
                f"observed={match.reference if match is not None else None}"
            )
    return {
        "authorization": auth, "authorization_path": authorization.path,
        "authorization_sha256": auth_hash, "request": req,
        "request_path": request.path, "request_sha256": request_hash,
        "attempt": att, "attempt_sha256": sha(attempt.payload),
        "result": res, "result_sha256": sha(result.payload),
        "completion": comp,
        "completion_sha256": sha(completion.payload) if completion else None,
        "waiting": waiting.document if waiting else None,
        "waiting_sha256": sha(waiting.payload) if waiting else None,
    }


base._phase_family = _phase_family
