"""D240 incident-bound Q16a continuation declarations, without authority.

validate_plan checks the actual 531-capture execution family and finite budgets.
validate_parent additionally authenticates original plan bytes and enforces the
unchanged prospective experiment. Neither authenticates the separately required
prefix, failure/restoration, compatibility, qualification or signed authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

import stage17_formal_ring_plan_v1 as ring
from stage17_discovery_contract_v2 import ContractError, _constant

VERSION = "cpu-prefetch-stage17-formal-ring-plan/3"
POLICY = "Q16A-COMPLETE-CONTEXT-CONTINUATION-v1"
AMENDMENT = "AMEND-2.0.0-pre.3-Q16A-CONTINUATION-v1"
SEED_POLICY = "PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES"
PARENT_SHA256 = "a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7"
PARENT_SIZE = 12128860
PARENT_SOURCE = "dd981b4fdcf953386d4a7514fec381ff9be6e359"
FAILURE_SHA256 = "a6704159e3dd2adab1598e2959202cfa5a6a0b5c9164a01fab967deeb251c7e4"
FAILURE_SIZE = 1082
FIRST_ORDINAL = 177
CAPTURE_COUNT = 531
REPETITIONS = 59
SCHEMA = Path(__file__).resolve().parents[1] / "config/schemas/stage17-formal-ring-plan-v3.schema.json"
CPUSET_FILES = frozenset(("cpuset.cpus", "cpuset.cpus.effective", "cpuset.cpus.exclusive",
                         "cpuset.cpus.partition", "cpuset.mems.effective"))


def _require(condition, message):
    if not condition:
        raise ContractError("continuation: " + message)


def _path(value):
    _require(type(value) is str and value.startswith("/") and "\x00" not in value,
             "absolute evidence/monitor path required")
    path = PurePosixPath(value)
    _require(str(path) == value and ".." not in path.parts, "noncanonical path")
    return path


def _no_floats(value):
    _require(not isinstance(value, float), "floating-point input is forbidden")
    if isinstance(value, dict):
        for item in value.values():
            _no_floats(item)
    elif isinstance(value, list):
        for item in value:
            _no_floats(item)


def _path_replacements(rows):
    _require(len(rows) in (0, 5), "replace either no monitor paths or all five cpuset paths")
    result = {}
    old_parents, new_parents = set(), set()
    for row in rows:
        old, new = (_path(row[k]) for k in ("original_path", "continuation_path"))
        _require(old.name in CPUSET_FILES and old.name == new.name, "cpuset basename changed")
        _require(old != new and str(old).startswith("/sys/fs/cgroup/")
                 and str(new).startswith("/sys/fs/cgroup/"), "invalid cpuset relocation")
        # Qualification must prove ownership and actual values; a path is not proof.
        _require(any(p.startswith("cpu-prefetch-") for p in new.parts[4:]),
                 "new cpuset must be within a named experiment delegation")
        _require(str(old) not in result, "duplicate monitor path replacement")
        result[str(old)] = str(new)
        old_parents.add(old.parent)
        new_parents.add(new.parent)
    if rows:
        _require(len(old_parents) == len(new_parents) == 1
                 and {PurePosixPath(p).name for p in result} == CPUSET_FILES,
                 "monitor paths must describe one old and one new owned cpuset")
    return result


def validate_declaration(plan):
    """Closed /3 declaration and incident binding checks, not proof admission."""
    _no_floats(plan)
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    error = next(validator.iter_errors(plan), None)
    _require(error is None, "schema: " + (error.message if error else ""))
    continuation = plan["continuation"]
    for field in ("parent_plan", "failed_family_receipt", "accepted_prefix_manifest", "compatibility_manifest"):
        _path(continuation[field]["path"])
    _path_replacements(continuation["monitor_path_replacements"])
    _require(plan["source_revision"] != PARENT_SOURCE, "new qualified continuation source required")


def validate_plan(plan) -> ring.FamilyExtent:
    """Validate exactly 531 real captures; never synthesize a complete family."""
    return ring._validate_plan(plan, archived=True, continuation=True)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate key in original plan")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ContractError("continuation: nonfinite original JSON")


def _compare_parent(plan, parent):
    """Compare already authenticated parent; private seam for focused fixtures."""
    _constant(parent["source_revision"], PARENT_SOURCE, "original source")
    _require(plan["plan_id"] != parent["plan_id"], "plan identity must be fresh")
    changed = {"schema_version", "plan_id", "source_revision", "warmup_namespace",
               "measurement_namespace", "captures", "storage"}
    for key, value in parent.items():
        if key not in changed:
            _constant(plan[key], value, "unchanged parent field " + key)
    # Keep the full declared finite ceilings; do not trade away a failing gate.
    expected_storage = copy.deepcopy(parent["storage"])
    expected_storage["implementation_profile_sha256"] = plan["storage"]["implementation_profile_sha256"]
    _constant(plan["storage"], expected_storage, "unchanged shared program and storage bounds")
    old_ids = {c["capture"][phase][key] for c in parent["captures"]
               for phase in ("warmup", "measurement") for key in ("run_id", "seed_id", "namespace_id")}
    replacements = _path_replacements(plan["continuation"]["monitor_path_replacements"])
    used_replacements = set()
    for ordinal, item in enumerate(plan["captures"]):
        original = parent["captures"][FIRST_ORDINAL + ordinal]
        expected = copy.deepcopy(original)
        for part in ("capture", "resources", "monitoring"):
            expected[part]["ordinal"] = ordinal
        for phase in ("warmup", "measurement"):
            identity = item["capture"][phase]
            old = original["capture"][phase]
            _constant(identity["seed_hex"], old["seed_hex"], "preserved prospective numeric seed")
            for key in ("run_id", "seed_id", "namespace_id"):
                _require(identity[key] not in old_ids, "phase identity overlaps original family")
            # Same LP padding width preserves the exact prospective raw extent.
            _require((4 + len(identity["run_id"].encode()) + 7) // 8
                     == (4 + len(old["run_id"].encode()) + 7) // 8,
                     "new run identity changes raw record width")
            expected["capture"][phase] = copy.deepcopy(identity)
        expected["capture"]["arena_seed"] = copy.deepcopy(item["capture"]["measurement"])
        for source in expected["monitoring"]["environment_sources"]:
            old_path = source["path"]
            if old_path in replacements:
                source["path"] = replacements[old_path]
                used_replacements.add(old_path)
        _constant(item, expected, "original slot " + str(FIRST_ORDINAL + ordinal))
    _require(used_replacements == set(replacements), "unused monitor path replacement")


def validate_parent(plan, original_plan_bytes: bytes) -> ring.FamilyExtent:
    """Mandatory parent gate at authoring and execution; no proof/authority grant.

    Caller must also authenticate failed-family evidence, all 177 prefix results,
    the compatibility manifest, qualified monitor values, and exact phase authority.
    """
    extent = validate_plan(plan)
    _require(type(original_plan_bytes) is bytes, "original exact bytes required")
    binding = plan["continuation"]["parent_plan"]
    _require(len(original_plan_bytes) == binding["size_bytes"] == PARENT_SIZE
             and hashlib.sha256(original_plan_bytes).hexdigest() == binding["sha256"] == PARENT_SHA256,
             "original plan bytes differ from the accepted incident")
    try:
        parent = json.loads(original_plan_bytes, object_pairs_hook=_unique, parse_constant=_reject_constant)
    except (ValueError, UnicodeError) as error:
        raise ContractError("continuation: invalid original JSON") from error
    ring._validate_plan(parent, archived=True)
    _compare_parent(plan, parent)
    return extent
