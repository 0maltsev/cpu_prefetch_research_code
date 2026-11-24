#!/usr/bin/env python3
"""Aggregate existing clean-release codegen evidence; never build or execute workers.

The output preserves the existing codegen-facts interface. This does not replace
release qualification: both compilers' exact reports/probes and source hashes
must already exist, and the supplied checkout must match the clean bundle.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from author_fresh_qualification_records import read, write, require

EMITTER = "include/cpu_prefetch/runner/software_prefetch.hpp"
REPORTS = (
    ("software_prefetch_mapping_codegen_report.json", "cpu-prefetch-software-prefetch-mapping-codegen/1",
     "cpu_prefetch_software_prefetch_mapping_codegen", "check_software_prefetch_mapping_codegen.py"),
    ("runner_combined_codegen_report.json", "cpu-prefetch-runner-combined-codegen/3",
     "cpu_prefetch_runner_combined_codegen", "check_runner_combined_codegen.py"),
)


def load(path):
    payload = read(path)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(payload, object_pairs_hook=unique), payload


def digest(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), "not a regular source/binary")
        value = hashlib.sha256()
        size = 0
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            value.update(chunk)
        after = os.fstat(fd)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(fields(before) == fields(after) and size == before.st_size, "input changed while hashed")
        return value.hexdigest()
    finally:
        os.close(fd)


def clean_revision(root):
    def git(*arguments):
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30).stdout.strip()
    revision = git("rev-parse", "HEAD")
    require(re.fullmatch(r"[0-9a-f]{40}", revision) is not None, "invalid source revision")
    require(not git("status", "--porcelain"), "source checkout is dirty")
    return revision


def render(*, repository_root, bundle_root, gcc_build, clang_build):
    root, bundle = repository_root.resolve(strict=True), bundle_root.resolve(strict=True)
    revision = clean_revision(root)
    manifest, manifest_bytes = load(bundle / "BUNDLE_MANIFEST.json")
    require(manifest["bundle_profile"] == "STAGE17-PILOT-CANDIDATE-BUNDLE-v26", "not the D207 production bundle")
    require(manifest["source_archive"]["source_revision"] == revision
            and manifest["source_archive"]["source_dirty"] is False, "bundle source is stale/dirty")
    emitter = digest(bundle / EMITTER)
    require(emitter == digest(root / EMITTER), "bundle/source emitter differs")
    records = []
    retained = [(bundle / "BUNDLE_MANIFEST.json", hashlib.sha256(manifest_bytes).hexdigest())]
    for compiler, library, prefix, directory in (
            ("GNU", "libstdc++", "gcc-", gcc_build),
            ("Clang", "libc++", "clang-libcxx-", clang_build)):
        build = directory.resolve(strict=True)
        meta_path = build / "generated/version_metadata.json"
        meta, meta_bytes = load(meta_path)
        require(meta["schema_version"] == "cpu-prefetch-build-metadata/1"
                and meta["protocol_version"] == "2.0.0-pre.3"
                and meta["source_revision"] == revision and meta["source_dirty"] is False
                and meta["compiler"]["id"] == compiler and bool(meta["compiler"]["version"])
                and meta["standard_library"] == library and meta["build_type"] == "Release"
                and meta["language_standard"] == "C++20", "build metadata is stale/dirty/wrong compiler")
        retained.append((meta_path, hashlib.sha256(meta_bytes).hexdigest()))
        for name, schema, binary_prefix, rule in REPORTS:
            report, payload = load(build / name)
            require(report["schema_version"] == schema and report["status"] == "PASS"
                    and report["missing_tools"] == [], "codegen report failed/incomplete")
            for tool in ("GNU_OBJDUMP", "LLVM_OBJDUMP"):
                require(report["tools"][tool]["status"] == "PASS", "disassembler failed: " + tool)
            require(re.search(r"\b22\.", report["tools"]["LLVM_OBJDUMP"]["version"]) is not None,
                    "accepted LLVM 22 evidence missing")
            if name.startswith("software_"):
                for role, suffix in (("binary", "probe"), ("mutant", "mutant")):
                    actual = build / (binary_prefix + "_" + suffix)
                    require(Path(report[role]["path"]).resolve() == actual,
                            "mapping report names a different build binary")
                    require(digest(actual) == report[role]["sha256"], "mapping binary/report hash differs")
                require(report["rule_set"]["sha256"] == digest(root / "tools" / rule), "mapping rule hash differs")
            else:
                for field, suffix in (("binary_sha256", "probe"), ("mutant_sha256", "mutant")):
                    require(report[field] == digest(build / (binary_prefix + "_" + suffix)), "combined binary/report hash differs")
                require(report["rule_set_sha256"] == digest(root / "tools" / rule), "combined rule hash differs")
                require("X86-64-PREFETCHT0-ONLY-v1" in report["software_prefetch_mapping_ids"], "T0-only mapping absent")
                source = report["source_contract"]
                require(source["status"] == "PASS" and source["emitter_sha256"] == emitter, "emitter contract differs")
                require(source["packages_sha256"] == digest(root / "include/cpu_prefetch/workload/packages.hpp")
                        and source["linked_queue_sha256"] == digest(root / "include/cpu_prefetch/queue/linked_spsc.hpp"),
                        "package/queue source contract differs")
                require(EMITTER in report["source_evidence"], "emitter source evidence absent")
                for relative, expected in report["source_evidence"].items():
                    path = Path(relative)
                    require(not path.is_absolute() and ".." not in path.parts, "source evidence path escapes")
                    require(digest(root / path) == expected, "combined source evidence differs: " + relative)
            report_hash = hashlib.sha256(payload).hexdigest()
            retained.append((build / name, report_hash))
            records.append(dict(compiler=meta["compiler"], standard_library=library,
                build_type=meta["build_type"], source_revision=revision, file_name=prefix + name,
                size_bytes=len(payload), sha256=report_hash))
    for path, expected in retained:
        require(digest(path) == expected, "metadata/report changed during preparation")
    require(clean_revision(root) == revision, "source revision changed during preparation")
    return dict(gcc_codegen_passed=True, clang_codegen_passed=True,
        gnu_objdump_passed=True, llvm_objdump_passed=True, source_revision=revision,
        reports=records, emitter=dict(path=EMITTER, sha256=emitter),
        scope="SOFTWARE_CODEGEN_EVIDENCE_NOT_HARDWARE_QUALIFICATION")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository-root", "bundle-root", "gcc-build", "clang-build", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = render(repository_root=args.repository_root, bundle_root=args.bundle_root,
                    gcc_build=args.gcc_build, clang_build=args.clang_build)
    write(args.output, result)
    print("CODEGEN_FACTS_PASS four exact reports; software evidence only", args.output)


if __name__ == "__main__":
    main()
