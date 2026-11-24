#!/usr/bin/env python3
"""Prep-only successor: policy-pinned validation, including retained drafts.

Original author helpers and all existing evidence stay untouched. No signing,
journal admission, hardware access, or capture. Run as actual evidence owner.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import author_fresh_qualification_records as previous


def pinned_policy_bytes(root, latest_path, validation):
    """Revalidate the current journal's policy and use admission's exact pin loop."""
    payload = previous.read(latest_path)
    previous.require(hashlib.sha256(payload).hexdigest() == validation.latest_journal_sha256,
                     "latest journal changed after validation")
    latest = json.loads(payload)
    semantic = importlib.import_module("stage17_semantic_verifier_v62")
    previous.require(Path(semantic.__file__).resolve().is_relative_to(root.resolve()),
                     "semantic verifier escaped supplied admission root")
    policy = json.loads(previous.read(root / semantic.POLICY_PATH))
    semantic.verify_policy_v62(
        root=root, policy=policy,
        graph_sha256=latest["graph"]["sha256"],
        catalog_sha256=latest["catalog"]["sha256"],
        genesis_record_sha256=latest["genesis"]["genesis_sha256"],
        resolution_schema_sha256=latest["version_hashes"]["resolution_schema_sha256"])
    pinned = {}
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            _, bound_payload = semantic.pinned_binding_bytes(root, binding, f"{group} {key}")
            pinned[binding["path"]] = bound_payload
    return pinned


class Context(previous.Context):
    def __init__(self, args):
        super().__init__(args)
        self.pinned = pinned_policy_bytes(
            self.root, self.base.latest_journal(self.evidence), self.validation)

    def validate_existing(self, input_id, destination):
        destination = destination.resolve(strict=True)
        previous.require(destination.is_relative_to(self.evidence), "manifest escaped evidence root")
        previous.require(input_id not in self.validation.resolutions, "input already admitted")
        before = previous.read(destination)
        result = self.operational.verify_manifest_v16(
            repository_root=self.root, manifest_path=destination,
            admitted_resolutions=self.validation.resolutions, expected_input_id=input_id,
            allow_synthetic=False, pinned_repository_bytes=self.pinned)
        previous.require(previous.read(destination) == before, "manifest changed during validation")
        print("PINNED_SEMANTIC_VALIDATION_PASS", input_id, hashlib.sha256(before).hexdigest())
        return result

    def manifest(self, number, destination, specs):
        self.base.author_operational_manifest(**self.common, input_id="S17-EXT-" + number,
            manifest_id=self.prefix + "-EXT" + number + "-MANIFEST-1",
            artifact_specs=specs, stand_id=previous.STAND, destination=destination)
        return self.validate_existing("S17-EXT-" + number, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ext002", "ext003", "ext006", "q15r-inputs",
                                           "q15w-inputs", "ext004", "ext005", "validate-existing"))
    for name in ("repository-root", "evidence-root", "bundle-root", "pilot-archive", "pilot-sidecar"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--id-prefix", required=True)
    parser.add_argument("--archive-runtime-root", type=Path)
    parser.add_argument("--trusted-record", type=Path)
    parser.add_argument("--probe-cpu", type=int)
    parser.add_argument("--platform-facts", type=Path)
    parser.add_argument("--qualification-directory", type=Path)
    parser.add_argument("--input-id", choices=("S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-005"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--author-custody", action="store_true")
    args = parser.parse_args()
    previous.require(not args.author_custody or args.command == "validate-existing",
                     "--author-custody is only for validating retained drafts")
    if args.command == "ext002":
        previous.require(args.trusted_record is not None, "--trusted-record required")
    if args.command == "ext004":
        previous.require(args.platform_facts is not None and args.qualification_directory is not None,
                         "actual platform facts and five existing-tool envelopes required")
    if args.command == "validate-existing":
        previous.require(args.input_id is not None and args.manifest is not None,
                         "--input-id and --manifest required")
        previous.require(not args.author_custody or args.input_id != "S17-EXT-003",
                         "EXT003 uses repository evidence, not custody")
    ctx = Context(args)
    if args.command == "validate-existing":
        ctx.validate_existing(args.input_id, args.manifest)
        if args.author_custody:
            ctx.custody(args.input_id[-3:], args.manifest)
    elif args.command in ("ext004", "ext005"):
        module = importlib.import_module("author_ext004005_records")
        getattr(module, args.command)(ctx)
    else:
        {"ext002": previous.ext002, "ext003": previous.ext003, "ext006": previous.ext006,
         "q15r-inputs": previous.q15r, "q15w-inputs": previous.q15w}[args.command](ctx)
    print("No signature, journal admission, capture, or hardware operation performed")


if __name__ == "__main__":
    main()
