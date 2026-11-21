"""S180 signed request construction from authenticated scoped resolutions.

The caller must obtain validation from the qualified journal replay. This module
does not replay a journal, qualify a profile, consume an attempt or launch a
worker. In particular, its signature result cannot supply missing EXT008/009
semantic admission. Legacy fixed-action authority remains unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import time

import stage17_formal_archive_v1 as archive
import stage17_phase_controller_v2 as signatures
from stage17_s180_checkpoint_v1 import BLUEPRINT_SHA256

SCHEMA = "cpu-prefetch-stage17-s180-authorization/1"
REQUEST_SCHEMA = "cpu-prefetch-stage17-s180-session-request/1"
ROLE, PROFILE = "STAGE17_S180_NATIVE_WORKER", "STAGE17-S180-NATIVE-WORKER-v1"
PLAN_SCOPE = "D310-S180-PILOT-INPUT-v1"
RESOURCE_SCOPE = "D310-S180-RESOURCE-ADMISSION-v1"
DAY_NS = 86_400_000_000_000
LIMIT = 16 * 1024**2
PREREQUISITES = frozenset(("calibration_freeze_sha256 ext007_resolution_sha256 "
    "ext008_resolution_sha256 ext009_resolution_sha256 qualification_sha256 "
    "compatibility_sha256 runtime_profile_sha256").split())
AUTH_FIELDS = frozenset(("schema_version authorization_id session_id request_id attempt_id "
    "stand_id actor trust_context plan_sha256 runtime_binding release_binding "
    "prerequisite_bindings evidence_root_binding window_binding "
    "issued_at_epoch_seconds expires_at_epoch_seconds permission_scope "
    "synthetic_test_only phase18_authority").split())
PERMISSIONS = dict(collect_one_s180_family=True, maximum_captures=180,
    automatic_retry=False, reset_window=False, replace_completed_calibration=False,
    confirmatory_execution=False, stage18_execution=False)


class AuthorityError(archive.ArchiveError):
    pass


def require(condition, message):
    if not condition:
        raise AuthorityError("S180 authority: " + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + " fields differ")


def same(value, expected, label):
    require(archive.canonical(value) == archive.canonical(expected), label + " differs")


def opaque(value, label):
    require(type(value) is str and 0 < len(value) <= 512
            and not any(ord(c) < 32 or ord(c) == 127 for c in value), label + " invalid")
    return value


def binding(resolution):
    return dict(input_id=resolution.input_id, resolution_id=resolution.resolution_id,
                sha256=resolution.sha256)


def _resolutions(validation):
    # A dict supplied by an authorization must never choose the signer or decide
    # semantic readiness. The qualified caller supplies its replay result, as in
    # the existing fixed-action controller. Tests use explicitly synthetic views.
    result = validation.resolutions
    for i in range(1, 10):
        key = f"S17-EXT-{i:03d}"
        require(key in result and result[key].input_id == key,
                "authenticated predecessor absent: " + key)
        archive.sha(result[key].sha256, key)
    return result


def _sample_window(authorization):
    window = authorization["window_binding"]
    fields(window, ("boot_id", "start_monotonic_ns", "end_monotonic_ns"), "window")
    require(window["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "original window belongs to another boot")
    start = archive.uint(window["start_monotonic_ns"], "window start", positive=True)
    end = archive.uint(window["end_monotonic_ns"], "window end", positive=True)
    require(end > start and end - start == DAY_NS, "original window is not exactly24h")
    # Match the native conservative whole-second epoch rule. Missing fractional
    # seconds cannot prove authority coverage at equality after rounding.
    epoch = time.time_ns() // 1_000_000_000
    current = time.monotonic_ns()
    issued = archive.uint(authorization["issued_at_epoch_seconds"], "issued", positive=True)
    expires = archive.uint(authorization["expires_at_epoch_seconds"], "expires", positive=True)
    require(start <= current < end and issued <= epoch < expires,
            "authority/window future or expired")
    require((expires - epoch - 1) * 1_000_000_000 >= end - current,
            "authority expires before original window ends")


@dataclass(frozen=True)
class VerifiedRequest:
    # Keep exact immutable bytes: callers cannot mutate a cached verified dict.
    authorization_bytes: bytes
    request_bytes: bytes

    @property
    def authorization_sha256(self):
        return sha(self.authorization_bytes)

    @property
    def request_sha256(self):
        return sha(self.request_bytes)

    def proof(self):
        return dict(schema_version="cpu-prefetch-stage17-s180-signature-proof/1",
            authorization_sha256=self.authorization_sha256, request_sha256=self.request_sha256,
            signature_verified=True, attempt_consumed=False, qualified_parent_replay_performed=False,
            execution_authority=False, launch_ready=False, phase18_authority=False)


def verify_authorization(*, authorization_bytes, signature_path, plan, validation):
    """Verify the exact owner signature and deterministically build its request.

    No authorization hash cycle: the owner signs the plan, identities, runtime,
    all preceding evidence, output root and original window. Only after signing
    is its digest added as EXT010's request prerequisite. No arbitrary request
    binding, argv, key, trust path or new command can be supplied by the signer.
    """
    require(type(authorization_bytes) is bytes and 0 < len(authorization_bytes) <= LIMIT,
            "authorization exceeds bound")
    # Own the plan used for both the signed hash check and request construction.
    # Retaining the caller's mutable dict would reopen that binding after check.
    plan_bytes = archive.canonical(plan)
    require(0 < len(plan_bytes) <= LIMIT, "plan exceeds native input bound")
    plan = archive.parse_json(plan_bytes)
    authorization = archive.parse_json(authorization_bytes)
    fields(authorization, AUTH_FIELDS, "authorization")
    require(authorization["schema_version"] == SCHEMA, "authorization version differs")
    for key in ("authorization_id", "session_id", "request_id", "attempt_id", "stand_id", "actor"):
        opaque(authorization[key], key)
    for key in ("authorization_id", "session_id", "request_id", "attempt_id"):
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", authorization[key]) is not None,
                "native opaque identity invalid: " + key)
    require(authorization["synthetic_test_only"] is False
            and authorization["phase18_authority"] is False, "production-only scoped authority required")
    same(authorization["permission_scope"], PERMISSIONS, "permission scope")
    require(plan.get("schema_version") == "cpu-prefetch-stage17-s180-session-plan/1"
            and sha(archive.canonical(plan["blueprint"])) == BLUEPRINT_SHA256,
            "exact approved plan blueprint required")
    same(authorization["plan_sha256"], sha(archive.canonical(plan)), "signed exact plan")
    same(authorization["stand_id"], plan["blueprint"]["stand_id"], "stand")
    resolutions = _resolutions(validation)
    trust = resolutions["S17-EXT-003"].semantic_context["trust"]
    same(authorization["trust_context"], {"ext002_resolution": binding(resolutions["S17-EXT-002"]),
         "ext003_resolution": binding(resolutions["S17-EXT-003"])}, "admitted trust ancestry")
    same(authorization["actor"], trust["measurements"]["principal"], "admitted signer")
    signatures._verify_signature(authorization_bytes, Path(signature_path), trust)
    _sample_window(authorization)
    prereq = authorization["prerequisite_bindings"]
    fields(prereq, PREREQUISITES, "prerequisites")
    for key, digest in prereq.items():
        archive.sha(digest, key)
    for key, expected in dict(calibration_freeze_sha256=plan["blueprint"]["calibration_freeze"]["sha256"],
            ext007_resolution_sha256=plan["blueprint"]["ext007_resolution"]["sha256"],
            ext008_resolution_sha256=resolutions["S17-EXT-008"].sha256,
            ext009_resolution_sha256=resolutions["S17-EXT-009"].sha256).items():
        same(prereq[key], expected, key)
    same(resolutions["S17-EXT-007"].sha256, prereq["ext007_resolution_sha256"], "accepted EXT007")
    prior = resolutions["S17-EXT-007"].semantic_context
    require(prior.get("data_provenance_accepted") is True
            and prior.get("legacy_statistical_freeze_satisfied") is False,
            "descriptive calibration scope absent")
    pilot, resource = (resolutions[f"S17-EXT-{i:03d}"].semantic_context for i in (8, 9))
    fields(pilot, ("scope_id", "plan_sha256", "window_binding", "evidence_root_binding",
        "runtime_binding", "release_binding", "qualification_sha256", "compatibility_sha256",
        "runtime_profile_sha256", "phase18_authority"), "scoped EXT008 context")
    fields(resource, ("scope_id", "plan_sha256", "window_binding", "evidence_root_binding",
        "resource_admission_status", "phase18_authority"), "scoped EXT009 context")
    same(pilot.get("scope_id"), PLAN_SCOPE, "scoped EXT008")
    same(resource.get("scope_id"), RESOURCE_SCOPE, "scoped EXT009")
    require(resource.get("resource_admission_status") == "ADMITTED"
            and pilot.get("phase18_authority") is False
            and resource.get("phase18_authority") is False, "scoped readiness missing")
    for context in (pilot, resource):
        for key in ("plan_sha256", "window_binding", "evidence_root_binding"):
            same(context[key], authorization[key], "admitted " + key)
    runtime, release = authorization["runtime_binding"], authorization["release_binding"]
    fields(runtime, ("role", "profile", "sha256", "size_bytes"), "runtime")
    require(runtime["role"] == ROLE and runtime["profile"] == PROFILE, "native runtime role/profile differs")
    archive.sha(runtime["sha256"], "native runtime")
    archive.uint(runtime["size_bytes"], "native runtime size", positive=True)
    fields(release, ("source_revision", "worker_sha256"), "release")
    require(type(release["source_revision"]) is str
            and re.fullmatch(r"[0-9a-f]{40}", release["source_revision"]) is not None,
            "release source revision invalid")
    same(release["worker_sha256"], runtime["sha256"], "release runtime")
    same(release["source_revision"], plan["source_revision"], "release source")
    for key in ("runtime_binding", "release_binding"):
        same(pilot[key], authorization[key], "qualified " + key)
    for key in ("qualification_sha256", "compatibility_sha256", "runtime_profile_sha256"):
        same(pilot[key], prereq[key], "qualified " + key)
    root = authorization["evidence_root_binding"]
    fields(root, ("absolute_path", "device", "inode"), "evidence root")
    path = Path(root["absolute_path"])
    require(path.is_absolute() and str(path) == root["absolute_path"]
            and ".." not in path.parts and path.name == authorization["plan_sha256"]
            and path.parent.name == "working", "original family root differs")
    archive.uint(root["device"], "root device")
    archive.uint(root["inode"], "root inode", positive=True)
    request = {key: authorization[key] for key in ("session_id", "request_id", "attempt_id",
        "authorization_id", "stand_id", "runtime_binding", "release_binding", "synthetic_test_only", "phase18_authority")}
    request.update(schema_version=REQUEST_SCHEMA, plan=plan,
        prerequisite_bindings={**prereq, "ext010_authorization_sha256": sha(authorization_bytes)})
    raw = archive.canonical(request)
    require(len(raw) <= LIMIT, "derived request exceeds native16MiB limit")
    return VerifiedRequest(authorization_bytes, raw)


def verify_admitted_authorization(**arguments):
    """Recheck the signature against the exact EXT010 from a fresh replay.

    This remains a signature/request boundary, not attempt consumption or launch.
    """
    verified = verify_authorization(**arguments)
    resolutions = arguments["validation"].resolutions
    require("S17-EXT-010" in resolutions, "actual scoped EXT010 is absent")
    resolution = resolutions["S17-EXT-010"]
    require(resolution.input_id == "S17-EXT-010", "EXT010 input identity differs")
    context = resolution.semantic_context
    fields(context, ("scope_id", "authorization_sha256", "authorization", "phase18_authority"),
           "scoped EXT010 context")
    same(context.get("scope_id"), "D310-S180-FAMILY-AUTHORIZATION-v1", "scoped EXT010")
    same(context.get("authorization_sha256"), verified.authorization_sha256, "admitted authorization bytes")
    same(context.get("authorization"), archive.parse_json(verified.authorization_bytes), "admitted authorization")
    require(context.get("phase18_authority") is False, "EXT010 cannot grant Stage18")
    return verified
