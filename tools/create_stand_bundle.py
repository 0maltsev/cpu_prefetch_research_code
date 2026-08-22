#!/usr/bin/env python3
"""Create the deterministic Stage 16 source/release stand-preflight bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from typing import Any


PROFILE = "STAGE16-STAND-BUNDLE-v1"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: pathlib.Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def source_paths(root: pathlib.Path) -> list[pathlib.Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    paths = [pathlib.Path(item.decode("utf-8")) for item in output.split(b"\0") if item]
    return sorted(path for path in paths if (root / path).is_file())


def add_file(archive: tarfile.TarFile, source: pathlib.Path, name: str) -> None:
    info = archive.gettarinfo(str(source), arcname=name)
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    info.mode = 0o755 if os.access(source, os.X_OK) else 0o644
    with source.open("rb") as stream:
        archive.addfile(info, stream)


def deterministic_tar(output: pathlib.Path, entries: list[tuple[pathlib.Path, str]]) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as archive:
                for source, name in sorted(entries, key=lambda item: item[1]):
                    add_file(archive, source, name)


def copy_tree_files(source: pathlib.Path, destination: pathlib.Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(0o755 if os.access(path, os.X_OK) else 0o644)


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )


def normalized_ldd_output(output: str) -> str:
    """Remove per-process loader addresses while retaining resolved identities."""
    return re.sub(r"[ \t]+\(0x[0-9A-Fa-f]+\)(?=\n|$)", "", output)


def make_sbom(root: pathlib.Path, dependencies: dict[str, Any], revision: str) -> dict[str, Any]:
    packages: list[dict[str, Any]] = [
        {
            "SPDXID": "SPDXRef-Repository",
            "copyrightText": "NOASSERTION",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "name": "cpu-prefetch-research-code",
            "versionInfo": revision,
        }
    ]
    relationships: list[dict[str, str]] = []
    for dependency in dependencies["dependencies"]:
        spdx_id = "SPDXRef-Dependency-" + "".join(
            character if character.isalnum() else "-" for character in dependency["id"]
        )
        packages.append(
            {
                "SPDXID": spdx_id,
                "copyrightText": "NOASSERTION",
                "downloadLocation": dependency["source"],
                "filesAnalyzed": False,
                "licenseConcluded": dependency["license"],
                "licenseDeclared": dependency["license"],
                "name": dependency["id"],
                "summary": dependency["purpose"],
                "versionInfo": dependency["version_rule"],
            }
        )
        relationships.append(
            {
                "relatedSpdxElement": spdx_id,
                "relationshipType": "DEPENDS_ON",
                "spdxElementId": "SPDXRef-Repository",
            }
        )
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: create_stand_bundle.py"],
        },
        "dataLicense": "CC0-1.0",
        "documentNamespace": f"https://example.invalid/cpu-prefetch/sbom/{revision}",
        "name": "cpu-prefetch-stage16-stand-bundle",
        "packages": packages,
        "relationships": relationships,
        "spdxVersion": "SPDX-2.3",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    parser.add_argument("--build-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    build = args.build_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    revision = git(root, "rev-parse", "HEAD")
    revision_short = revision[:7]
    dirty = bool(git(root, "status", "--porcelain=v1"))
    source_state = "dirty" if dirty else "clean"
    version_metadata = json.loads(
        (build / "generated" / "version_metadata.json").read_text(encoding="utf-8")
    )
    if version_metadata["protocol_version"] != "2.0.0-pre.2":
        raise ValueError("release metadata is not bound to protocol 2.0.0-pre.2")
    if version_metadata["source_revision"] != revision:
        raise ValueError("release metadata revision differs from the source tree")

    required_binaries = ["cpu_prefetch_smoke", "cpu_prefetch_preflight"]
    required_libraries = sorted(build.glob("libcpu_prefetch_*.a"))
    for name in required_binaries:
        if not (build / name).is_file():
            raise ValueError(f"missing release binary: {name}")
    if not required_libraries:
        raise ValueError("release libraries are absent")

    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-stage16-") as temporary:
        staging = pathlib.Path(temporary) / "bundle"
        staging.mkdir()
        source_archive = staging / "source" / f"cpu-prefetch-source-{revision_short}-{source_state}.tar.gz"
        source_archive.parent.mkdir(parents=True)
        deterministic_tar(
            source_archive,
            [(root / path, f"cpu_prefetch_research_code/{path.as_posix()}") for path in source_paths(root)],
        )

        release_bin = staging / "release" / "bin"
        release_lib = staging / "release" / "lib"
        release_bin.mkdir(parents=True)
        release_lib.mkdir(parents=True)
        for name in required_binaries:
            shutil.copyfile(build / name, release_bin / name)
            (release_bin / name).chmod(0o755)
        for library in required_libraries:
            shutil.copyfile(library, release_lib / library.name)

        provenance = staging / "build-provenance"
        provenance.mkdir()
        shutil.copyfile(build / "generated" / "version_metadata.json", provenance / "version_metadata.json")
        shutil.copyfile(build / "compile_commands.json", provenance / "compile_commands.json")
        runtime_lines: list[str] = []
        for name in required_binaries:
            completed = subprocess.run(
                ["ldd", str(build / name)], check=True, text=True, stdout=subprocess.PIPE
            )
            runtime_lines.append(f"[{name}]\n{normalized_ldd_output(completed.stdout)}")
        (provenance / "runtime-dependencies.txt").write_text(
            "\n".join(runtime_lines), encoding="utf-8"
        )

        copy_tree_files(root / "protocol" / "2.0.0-pre.2", staging / "protocol" / "2.0.0-pre.2")
        copy_tree_files(root / "config" / "schemas", staging / "config" / "schemas" / "implementation")
        copy_tree_files(
            root / "protocol" / "2.0.0-pre.2" / "handoff" / "schemas",
            staging / "config" / "schemas" / "imported",
        )
        copy_tree_files(root / "config" / "examples", staging / "config" / "examples")
        licenses = staging / "licenses"
        licenses.mkdir()
        shutil.copyfile(root / "config" / "dependencies.json", licenses / "dependencies.json")
        shutil.copyfile(root / "docs" / "NO_LICENSE_GRANT.md", licenses / "NO_LICENSE_GRANT.md")
        for document in (
            "PRE_PILOT_READINESS_REPORT.md",
            "STAND_BUNDLE.md",
            "STAND_RUNBOOK.md",
        ):
            target = staging / "docs" / document
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / "docs" / document, target)

        validator_names = (
            "check_calibration_schemas.py",
            "check_canonical.py",
            "check_orchestration_schemas.py",
            "check_protocol.py",
            "check_protocol_fixtures.py",
            "check_reconciliation_schema.py",
            "check_storage_schemas.py",
            "verify_stand_bundle.py",
        )
        validators = staging / "validators"
        validators.mkdir()
        for name in validator_names:
            shutil.copyfile(root / "tools" / name, validators / name)
            (validators / name).chmod(0o755)
        copy_tree_files(root / "tests" / "fixtures", staging / "tests" / "fixtures")

        dependencies = json.loads(
            (root / "config" / "dependencies.json").read_text(encoding="utf-8")
        )
        write_json(staging / "SBOM.spdx.json", make_sbom(root, dependencies, revision))

        release_artifacts = []
        for path in sorted((staging / "release").rglob("*")):
            if path.is_file():
                release_artifacts.append(
                    {
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": sha256(path),
                        "size_bytes": path.stat().st_size,
                    }
                )
        manifest = {
            "bundle_profile": PROFILE,
            "confirmatory_authorized": False,
            "pilot_authorized": False,
            "protocol_import_manifest_sha256": sha256(
                root / "protocol" / "2.0.0-pre.2" / "IMPORT_MANIFEST.json"
            ),
            "protocol_version": "2.0.0-pre.2",
            "readiness_state": "READY_FOR_STAND_PREFLIGHT",
            "release_artifacts": release_artifacts,
            "repository_license": "NO-LICENSE-GRANT",
            "schema_version": "cpu-prefetch-stand-bundle/1",
            "source_archive": {
                "path": source_archive.relative_to(staging).as_posix(),
                "sha256": sha256(source_archive),
                "source_dirty": dirty,
                "source_revision": revision,
            },
            "unresolved_before_pilot": [
                "production measurement executable and final integrated worker codegen",
                "eligible stand, selected worker pairs, and runtime atomic checks",
                "privileged authority, exact controls, independent readback, probes, and restoration",
                "clock, address residency, storage domains/capacity/custody, and recovery evidence",
                "prospective calibration and pilot inputs and authorization",
            ],
        }
        write_json(staging / "BUNDLE_MANIFEST.json", manifest)

        checksum_files = sorted(
            path for path in staging.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
        )
        (staging / "SHA256SUMS").write_text(
            "".join(
                f"{sha256(path)}  {path.relative_to(staging).as_posix()}\n"
                for path in checksum_files
            ),
            encoding="utf-8",
        )

        source_hash_short = sha256(source_archive)[:12]
        bundle_name = (
            f"cpu-prefetch-stand-bundle-2.0.0-{revision_short}-{source_state}-"
            f"{source_hash_short}.tar.gz"
        )
        output = output_dir / bundle_name
        if output.exists() or output.with_suffix(output.suffix + ".sha256").exists():
            raise FileExistsError(f"append-only bundle output already exists: {output}")
        top = bundle_name.removesuffix(".tar.gz")
        deterministic_tar(
            output,
            [(path, f"{top}/{path.relative_to(staging).as_posix()}") for path in staging.rglob("*") if path.is_file()],
        )
        outer_hash = sha256(output)
        output.with_suffix(output.suffix + ".sha256").write_text(
            f"{outer_hash}  {output.name}\n", encoding="utf-8"
        )
        print(f"stand-bundle: PASS path={output} sha256={outer_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
