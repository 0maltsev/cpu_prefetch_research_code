#!/usr/bin/env python3
"""Prep-only EXT004/005 authoring with explicit renewed Q15 directories.

Reuses v2's policy-pinned Context. Preserves all predecessor helpers. Never
signs, admits, executes Q15 or changes old authorizations/evidence.
"""
import argparse
from pathlib import Path
import types
import author_ext004005_records as previous
from author_fresh_qualification_records_v2 import Context


def family(ctx, action):
    previous.require(action in ("Q15-R", "Q15-W"), "unsupported Q15 action")
    supplied = (ctx.args.q15r_authoring_directory if action == "Q15-R"
                else ctx.args.q15w_authoring_directory)
    previous.require(supplied is not None, "explicit authoring directory required")
    previous.require(not supplied.is_symlink(), "authoring directory is a symlink")
    directory = supplied.resolve(strict=True)
    previous.require(directory.is_dir() and directory.is_relative_to(ctx.root / "evidence"),
                     "authoring directory outside current admission evidence")
    request_path = directory / "request.json"
    request = previous.load(request_path)
    previous.require(request["action_id"] == action, "wrong action request")
    previous.require(request["session_id"] == request["action_inputs"]["session_id"],
                     "request session differs from action inputs")
    if action == "Q15-R":
        previous.require(request["attempt_id"] == request["action_inputs"]["attempt_id"],
                         "Q15-R input attempt differs")
    output = Path(request["evidence_root_binding"]["absolute_path"]).resolve(strict=True)
    previous.require(output.is_relative_to(ctx.evidence), "output outside fresh evidence root")
    prefix = action.replace("-", "_")
    result_path = output / ("stage17-" + action.lower() + "-result-v4.json")
    result = previous.load(result_path)
    previous.require(result["action_id"] == action and result["attempt_id"] == request["attempt_id"],
                     "result action/attempt differs")
    previous.require(result["request_sha256"] == previous.binding("REQUEST", request_path)["sha256"],
                     "result request binding differs")
    paths = {
        prefix + "_REQUEST": request_path,
        prefix + "_AUTHORIZATION": directory / "authorization.json",
        prefix + "_SIGNATURE": directory / "authorization.json.sig",
        prefix + "_ATTEMPT": output / ("stage17-" + prefix.lower() + "-attempt-v4.json"),
        prefix + "_RESULT": result_path,
    }
    if action == "Q15-R":
        paths["Q15_R_SESSION_WAITING"] = output / "stage17-q15-session-waiting-v1.json"
    else:
        paths["Q15_W_COMPLETION"] = output / "stage17-q15_w-completion-v4.json"
    for item in result["artifacts"]:
        role = item["role"]
        previous.require(role not in paths, "duplicate result role")
        path = (output / item["file_name"]).resolve(strict=True)
        previous.require(path.parent == output, "result artifact escaped output root")
        observed = previous.binding(role, path)
        previous.require((observed["sha256"], observed["size_bytes"])
                         == (item["sha256"], item["size_bytes"]), "result raw artifact drift")
        paths[role] = path
    return request, result, paths


def routed_action(command):
    """Use unchanged authoring logic with a private family binding; no global patch."""
    original = getattr(previous, command)
    namespace = dict(original.__globals__)
    namespace["family"] = family
    return types.FunctionType(original.__code__, namespace, original.__name__, original.__defaults__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ext004", "ext005"))
    for name in ("repository-root", "evidence-root", "bundle-root", "pilot-archive", "pilot-sidecar"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--id-prefix", required=True)
    parser.add_argument("--archive-runtime-root", type=Path)
    parser.add_argument("--q15r-authoring-directory", type=Path)
    parser.add_argument("--q15w-authoring-directory", type=Path)
    parser.add_argument("--platform-facts", type=Path)
    parser.add_argument("--qualification-directory", type=Path)
    args = parser.parse_args()
    if args.command == "ext004":
        previous.require(args.q15r_authoring_directory is not None, "--q15r-authoring-directory required")
        previous.require(args.platform_facts is not None and args.qualification_directory is not None,
                         "actual platform facts and five existing-tool envelopes required")
    else:
        previous.require(args.q15w_authoring_directory is not None, "--q15w-authoring-directory required")
    ctx = Context(args)
    routed_action(args.command)(ctx)
    print("AUTHORING ONLY: no signature, journal admission, Q15 execution or hardware operation")


if __name__ == "__main__":
    main()
