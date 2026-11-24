#!/usr/bin/env python3
"""Render the six repository-owned Stage 17 read-only observation programs,
resolving symlinked system tools at S17-RO-PREFLIGHT-005 (ADR-0135).

Additive successor to `stage17_read_only_preflight_collector_v2.py`
(itself a thin wrapper that validates the capture timestamp and then
delegates unchanged to `stage17_read_only_preflight_collector_v1.py`'s
own `render_observation_program`). `v1`'s `OBSERVATION_IDS[4]` branch
(`S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES`) checks `/usr/bin/
python3`, `/usr/bin/sha256sum`, `/usr/bin/uname`, and the three sealed
bundle binaries uniformly with `os.lstat` + `require(S_ISREG and not
S_ISLNK)` -- which can never pass for the three system-tool paths on any
real, modern Linux host where they are symlinks (per-version Python,
consolidated coreutils), confirmed via a real, read-only `stat` against
the real stand. `digest()` already opens paths with plain `open()`,
which follows symlinks, so hashing through to the real target already
worked; only the `S_ISLNK` rejection blocked it.

Because `v1`'s `render_observation_program` is one function dispatching
on `observation_id` via `if`/`elif`, not six independently swappable
pieces, this fix requires a fresh copy of the whole function -- the same
"single function, one changed branch" situation ADR-0132's `pin_bound_
input` retargeting already established -- rather than an alias. Every
branch except `OBSERVATION_IDS[4]` is byte-identical to `v1`'s own. The
three bundle binaries keep the exact original `os.lstat`/reject-symlink
check unchanged, since they are sealed inside the hash-verified bundle
and must never legitimately be symlinks (`S17-RO-PREFLIGHT-004` already
proves they execute correctly as plain files there); only the three
fixed system-tool paths switch to `os.stat` (follows symlinks) and drop
the symlink rejection, recording the *resolved* regular file's real
identity -- the file that actually executes -- which is a more
meaningful pin, not a weaker one.
"""

from __future__ import annotations

import re
from typing import Any

import stage17_read_only_preflight_collector_v1 as collector_v1
import stage17_read_only_preflight_collector_v2 as immediate_predecessor


COLLECTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-COLLECTOR-v3"
OBSERVATION_IDS = collector_v1.OBSERVATION_IDS
CollectorContractError = immediate_predecessor.CollectorContractError
validate_exact_second_utc = immediate_predecessor.validate_exact_second_utc

_absolute_locator = collector_v1._absolute_locator
_identifier = collector_v1._identifier
_utc = collector_v1._utc
_literal = collector_v1._literal
_preamble = collector_v1._preamble


def _render_v3(observation_id: str, context: dict[str, Any]) -> bytes:
    """Faithful copy of `collector_v1.render_observation_program`, changed
    only in the `OBSERVATION_IDS[4]` branch's system-tool handling.
    """
    if observation_id not in OBSERVATION_IDS:
        raise collector_v1.CollectorContractError("unknown fixed observation ID")
    archive = _absolute_locator(context.get("archive_locator"), "archive locator")
    sidecar = _absolute_locator(context.get("sidecar_locator"), "sidecar locator")
    bundle = _absolute_locator(context.get("bundle_root_locator"), "bundle root")
    capture_id = _identifier(context.get("capture_id"), "capture_id")
    captured_at = _utc(context.get("captured_at_utc"))
    expected_archive_size = context.get("archive_size_bytes")
    expected_archive_sha = context.get("archive_sha256")
    expected_sidecar_size = context.get("sidecar_size_bytes")
    expected_sidecar_sha = context.get("sidecar_sha256")
    expected_manifest_sha = context.get("manifest_sha256")
    expected_internal_file_count = context.get("internal_file_count")
    if not isinstance(expected_archive_size, int) or expected_archive_size < 1:
        raise collector_v1.CollectorContractError("archive size is invalid")
    if not isinstance(expected_sidecar_size, int) or expected_sidecar_size < 1:
        raise collector_v1.CollectorContractError("sidecar size is invalid")
    for value, label in (
        (expected_archive_sha, "archive SHA-256"),
        (expected_sidecar_sha, "sidecar SHA-256"),
        (expected_manifest_sha, "manifest SHA-256"),
    ):
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise collector_v1.CollectorContractError(f"{label} is invalid")
    if (
        not isinstance(expected_internal_file_count, int)
        or expected_internal_file_count < 1
    ):
        raise collector_v1.CollectorContractError("internal file count is invalid")

    program = _preamble(observation_id)
    if observation_id == OBSERVATION_IDS[0]:
        program += (
            "emit({'hostname':socket.gethostname(),'kernel':platform.system(),"
            "'release':platform.release(),'machine':platform.machine(),"
            "'python_executable':sys.executable})\n"
        )
    elif observation_id == OBSERVATION_IDS[1]:
        program += (
            f"archive={_literal(archive)};sidecar={_literal(sidecar)}\n"
            f"require(os.path.getsize(archive)=={expected_archive_size},'archive size')\n"
            f"require(digest(archive)=={_literal(expected_archive_sha)},'archive hash')\n"
            f"require(os.path.getsize(sidecar)=={expected_sidecar_size},'sidecar size')\n"
            f"require(digest(sidecar)=={_literal(expected_sidecar_sha)},'sidecar hash')\n"
            "emit({'archive_size_bytes':os.path.getsize(archive),"
            "'archive_sha256':digest(archive),'sidecar_size_bytes':os.path.getsize(sidecar),"
            "'sidecar_sha256':digest(sidecar)})\n"
        )
    elif observation_id == OBSERVATION_IDS[2]:
        program += (
            f"root=pathlib.Path({_literal(bundle)})\n"
            "require(root.is_dir() and not root.is_symlink(),'bundle root')\n"
            "manifest=root/'BUNDLE_MANIFEST.json';sums=root/'SHA256SUMS'\n"
            "require(manifest.is_file() and sums.is_file(),'bundle controls')\n"
            f"require(digest(manifest)=={_literal(expected_manifest_sha)},'manifest hash')\n"
            "manifest_doc=json.loads(manifest.read_text(encoding='utf-8'))\n"
            "checked=0\n"
            "for line in sums.read_text(encoding='utf-8').splitlines():\n"
            " expected,relative=line.split('  ',1);rel=pathlib.PurePosixPath(relative)\n"
            " require(not rel.is_absolute() and '..' not in rel.parts and str(rel)==relative,'bundle relative path')\n"
            " path=root/relative;cursor=root\n"
            " for part in rel.parts:\n"
            "  cursor=cursor/part;require(not cursor.is_symlink(),'bundle symlink')\n"
            " require(path.is_file(),'bundle member')\n"
            " require(digest(path)==expected,'bundle member hash');checked+=1\n"
            f"require(checked=={expected_internal_file_count},'bundle file count')\n"
            "for item in manifest_doc['release_artifacts']:\n"
            " path=root/item['path'];require(path.is_file() and not path.is_symlink(),'release artifact')\n"
            " require(os.path.getsize(path)==item['size_bytes'] and digest(path)==item['sha256'],'release artifact identity')\n"
            "emit({'manifest_sha256':digest(manifest),'sha256sum_entries':checked})\n"
        )
    elif observation_id == OBSERVATION_IDS[3]:
        commands = [
            [f"{bundle}/release/bin/cpu_prefetch_smoke"],
            [f"{bundle}/release/bin/cpu_prefetch_preflight", "--self-test"],
            [f"{bundle}/release/bin/cpu_prefetch_qualification", "--self-test"],
        ]
        program += (
            f"root=pathlib.Path({_literal(bundle)});manifest=root/'BUNDLE_MANIFEST.json'\n"
            f"require(digest(manifest)=={_literal(expected_manifest_sha)},'manifest hash')\n"
            "artifacts={item['path']:item for item in json.loads(manifest.read_text(encoding='utf-8'))['release_artifacts']}\n"
            f"commands={_literal(commands)}\n"
            "results=[]\n"
            "for command in commands:\n"
            " relative=str(pathlib.Path(command[0]).relative_to(root));item=artifacts[relative]\n"
            " require(os.path.getsize(command[0])==item['size_bytes'] and digest(command[0])==item['sha256'],'self-test executable identity')\n"
            " completed=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,"
            "stderr=subprocess.PIPE,timeout=20,check=False,shell=False,env={'LANG':'C','LC_ALL':'C','TZ':'UTC0'})\n"
            " require(completed.returncode==0,'self-test failure')\n"
            " require(len(completed.stdout)+len(completed.stderr)<=1048576,'self-test output')\n"
            " results.append({'argv':command,'returncode':completed.returncode,"
            "'stdout_sha256':hashlib.sha256(completed.stdout).hexdigest(),"
            "'stderr_sha256':hashlib.sha256(completed.stderr).hexdigest()})\n"
            "emit({'self_tests':results})\n"
        )
    elif observation_id == OBSERVATION_IDS[4]:
        system_paths = ["/usr/bin/python3", "/usr/bin/sha256sum", "/usr/bin/uname"]
        bundle_paths = [
            f"{bundle}/release/bin/cpu_prefetch_smoke",
            f"{bundle}/release/bin/cpu_prefetch_preflight",
            f"{bundle}/release/bin/cpu_prefetch_qualification",
        ]
        program += (
            f"root=pathlib.Path({_literal(bundle)});manifest=root/'BUNDLE_MANIFEST.json'\n"
            f"require(digest(manifest)=={_literal(expected_manifest_sha)},'manifest hash')\n"
            f"system_paths={_literal(system_paths)}\n"
            f"bundle_paths={_literal(bundle_paths)}\n"
            "identities=[]\n"
            "for path in system_paths:\n"
            " s=os.stat(path);require(stat.S_ISREG(s.st_mode),'runtime file')\n"
            " identities.append({'path':path,'size_bytes':s.st_size,'sha256':digest(path),"
            "'mode':stat.S_IMODE(s.st_mode)})\n"
            "for path in bundle_paths:\n"
            " s=os.lstat(path);require(stat.S_ISREG(s.st_mode) and not stat.S_ISLNK(s.st_mode),'runtime file')\n"
            " identities.append({'path':path,'size_bytes':s.st_size,'sha256':digest(path),"
            "'mode':stat.S_IMODE(s.st_mode)})\n"
            "emit({'runtime_identities':identities})\n"
        )
    else:
        command = [
            f"{bundle}/release/bin/cpu_prefetch_preflight",
            "--snapshot-id",
            capture_id,
            "--captured-at-utc",
            captured_at,
        ]
        program += (
            f"root=pathlib.Path({_literal(bundle)});manifest=root/'BUNDLE_MANIFEST.json'\n"
            f"require(digest(manifest)=={_literal(expected_manifest_sha)},'manifest hash')\n"
            "artifacts={item['path']:item for item in json.loads(manifest.read_text(encoding='utf-8'))['release_artifacts']}\n"
            f"command={_literal(command)}\n"
            "item=artifacts['release/bin/cpu_prefetch_preflight']\n"
            "require(os.path.getsize(command[0])==item['size_bytes'] and digest(command[0])==item['sha256'],'inventory executable identity')\n"
            "completed=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,"
            "stderr=subprocess.PIPE,timeout=30,check=False,shell=False,env={'LANG':'C','LC_ALL':'C','TZ':'UTC0'})\n"
            "require(completed.returncode==0,'inventory failure')\n"
            "require(len(completed.stdout)<=1048576 and len(completed.stderr)<=1048576,'inventory output')\n"
            "inventory=json.loads(completed.stdout.decode('utf-8'))\n"
            "emit({'inventory':inventory,'stderr_sha256':hashlib.sha256(completed.stderr).hexdigest()})\n"
        )
    encoded = program.encode("utf-8")
    if len(encoded) > 65536:
        raise collector_v1.CollectorContractError("rendered fixed program exceeds its bound")
    return encoded


def render_observation_program(
    observation_id: str, context: dict[str, Any]
) -> bytes:
    """Validate the complete typed context, then render `v3` semantics."""

    validate_exact_second_utc(context.get("captured_at_utc"))
    try:
        program = _render_v3(observation_id, context)
    except collector_v1.CollectorContractError as exception:
        raise CollectorContractError(str(exception)) from exception
    compile(program, f"<stage17:{observation_id}>", "exec")
    return program


def describe_contract() -> dict[str, Any]:
    return {
        "collector_id": COLLECTOR_ID,
        "observation_ids": list(OBSERVATION_IDS),
        "accepts_owner_command_bytes": False,
        "opens_transport": False,
        "writes_remote_files": False,
        "remote_subprocess_shell": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(describe_contract(), sort_keys=True, separators=(",", ":")))
