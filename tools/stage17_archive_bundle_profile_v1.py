"""Cold package bindings for D233; explicit runtime roots, never host inference.

This helper describes and checks bytes. It grants no experiment authority and
never launches the encoder or Python images it inventories.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import stat

PROFILE_PATH = "config/stage17/formal-archive-implementation-profile-v1.json"
SCHEMA_VERSION = "cpu-prefetch-formal-archive-implementation-profile/1"
POLICY_ID = "EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1"
ROOT_MODULES = ("stage17_formal_archive_runtime_v1", "stage17_formal_archive_broker_v1")
ENCODER_PATH = "release/bin/cpu_prefetch_stage17_archive_encoder"
ZSTD_PATH = "release/runtime/lib/libzstd.so.1"
PYTHON_PATH = "usr/bin/python3.14"
OPTIONS = dict(zstd_version="1.5.7", compression_level=3, worker_threads=1,
               nbWorkers=0, checksum_flag=1, content_size_flag=1, dictionary_id_flag=0)


class ProfileError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def explicit_root(root):
    root = Path(root)
    if (not root.is_absolute() or not root.is_dir()
            or any(item.is_symlink() for item in (root, *root.parents))):
        raise ProfileError("explicit absolute nonsymlink root required")
    return root


def regular(root, relative):
    if (not isinstance(relative, str) or not relative or "\0" in relative
            or Path(relative).is_absolute() or ".." in Path(relative).parts
            or Path(relative).as_posix() != relative or relative == "."):
        raise ProfileError("noncanonical relative member path")
    path = Path(root) / relative
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ProfileError("symlink member or ancestor")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ProfileError("member is not a regular file")
    return path


def binding(root, relative):
    path = regular(root, relative)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(1024 * 1024):
            digest.update(data)
    after = path.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
        raise ProfileError("member changed during inventory")
    if before.st_size == 0:
        raise ProfileError("empty implementation member")
    return dict(path=relative, size_bytes=before.st_size, sha256=digest.hexdigest())


def local_source_closure(tools_root):
    """Both literal bootstrap roots plus all statically named local imports.

    Package modules here are flat tools/*.py files. Relative local imports are
    rejected, and an absent stage17 module is a missing dependency, not stdlib.
    The two fixed bootstrap roots cover the intentionally string-named broker.
    """
    tools_root = Path(tools_root)
    pending = list(ROOT_MODULES)
    found = set()
    while pending:
        module = pending.pop()
        if module in found:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", module):
            raise ProfileError("invalid local module name")
        path = regular(tools_root, module + ".py")
        tree = ast.parse(path.read_bytes(), filename=str(path))
        found.add(module)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name.split(".")[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise ProfileError("relative import outside flat tools closure")
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if (tools_root / (name + ".py")).exists():
                    pending.append(name)
                elif name.startswith("stage17_"):
                    raise ProfileError("missing local dependency: " + name)
    return tuple(sorted(found))


def build_profile(*, bundle_root, runtime_root, window_log):
    bundle_root, runtime_root = explicit_root(bundle_root), explicit_root(runtime_root)
    if type(window_log) is not int or not 10 <= window_log <= 31:
        raise ProfileError("explicit zstd window_log must be in [10,31]")
    def image(location, relative):
        root = bundle_root if location == "bundle" else runtime_root
        return dict(location=location, **binding(root, relative))
    return dict(schema_version=SCHEMA_VERSION, policy_id=POLICY_ID,
        encoder=image("bundle", ENCODER_PATH), python=image("runtime", PYTHON_PATH),
        zstd_library=image("bundle", ZSTD_PATH),
        source_closure=[dict(module=name, image=image("bundle", "tools/" + name + ".py"))
                        for name in local_source_closure(bundle_root / "tools")],
        options=dict(OPTIONS, window_log=window_log))


def verify_profile(*, bundle_root, runtime_root=None):
    """Verify packaged members, optionally also the explicitly supplied runtime.

    Archive inspection has no stand runtime yet. It verifies the Python binding
    shape only; qualification must supply runtime_root and check its actual bytes.
    """
    bundle_root = explicit_root(bundle_root)
    raw = regular(bundle_root, PROFILE_PATH).read_bytes()
    try:
        document = json.loads(raw)
        if raw != canonical(document):
            raise ProfileError("profile is not exact canonical JSON without LF")
        if set(document) != {"schema_version", "policy_id", "encoder", "python", "zstd_library", "source_closure", "options"}:
            raise ProfileError("profile field set")
        if document["schema_version"] != SCHEMA_VERSION or document["policy_id"] != POLICY_ID:
            raise ProfileError("profile schema or policy")
        options = document["options"]
        window = options["window_log"]
        if type(window) is not int or not 10 <= window <= 31 or canonical(options) != canonical(dict(OPTIONS, window_log=window)):
            raise ProfileError("profile codec options")
        def check_image(value, location, relative):
            if (set(value) != {"location", "path", "size_bytes", "sha256"}
                    or value["location"] != location or value["path"] != relative
                    or type(value["size_bytes"]) is not int or value["size_bytes"] <= 0
                    or not re.fullmatch("[0-9a-f]{64}", value["sha256"])):
                raise ProfileError("implementation image shape")
            root = bundle_root if location == "bundle" else runtime_root
            if root is not None and value != dict(location=location, **binding(explicit_root(root), relative)):
                raise ProfileError("implementation image bytes differ: " + relative)
        check_image(document["encoder"], "bundle", ENCODER_PATH)
        check_image(document["python"], "runtime", PYTHON_PATH)
        check_image(document["zstd_library"], "bundle", ZSTD_PATH)
        closure = document["source_closure"]
        names = list(local_source_closure(bundle_root / "tools"))
        if not isinstance(closure, list) or [item["module"] for item in closure] != names:
            raise ProfileError("source closure exact membership/order")
        for item in closure:
            if set(item) != {"module", "image"}:
                raise ProfileError("source closure fields")
            check_image(item["image"], "bundle", "tools/" + item["module"] + ".py")
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeError) as exc:
        raise ProfileError("malformed implementation profile") from exc
    return document


def qualified_context(*, bundle_root, runtime_root):
    """Actual file-bound fields to merge only after full release verification."""
    bundle_root, runtime_root = explicit_root(bundle_root), explicit_root(runtime_root)
    verify_profile(bundle_root=bundle_root, runtime_root=runtime_root)
    return dict(archive_profile_binding=binding(bundle_root, PROFILE_PATH),
                archive_bundle_root=str(bundle_root), archive_runtime_root=str(runtime_root))


def manifest_binding(*, bundle_root, document=None):
    bundle_root = explicit_root(bundle_root)
    if document is None:
        document = verify_profile(bundle_root=bundle_root)
    return {"profile": binding(bundle_root, PROFILE_PATH),
            "zstd_license": binding(bundle_root, "licenses/zstd/LICENSE"),
            "runtime_python": document["python"],
            "runtime_root_binding": "EXPLICIT_AT_EXTRACTED_RELEASE_QUALIFICATION"}
