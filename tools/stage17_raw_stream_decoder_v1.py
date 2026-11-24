#!/usr/bin/env python3
"""Bounded-memory independent Stage 17 raw-stream reconciliation.

The decoder never trusts a worker-authored JOIN_AUDIT.  It opens the three
immutable physical streams, verifies exact bytes and row grammar, walks
producer logical order, and consumes consumer/joined rows only for accepted
events.  Memory use is O(1) apart from fixed-size row buffers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import struct
import tempfile
from dataclasses import dataclass
from typing import Any, BinaryIO


FORMAT_ID = "RAW-OBS-U64LE-LP-RUNID-v1"
SCHEMA_ID = "cpu-prefetch-stage17-independent-raw-reconciliation/1"
ACCEPTED_FLAGS = 15
FULL_FLAGS = 1


class DecodeError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_path(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_layout(run_id: str) -> tuple[int, int, int, int]:
    encoded = run_id.encode("utf-8", errors="strict")
    if not encoded or len(encoded) > 0xFFFFFFFF:
        raise DecodeError("run_id length is invalid")
    prefix = (4 + len(encoded) + 7) & ~7
    return prefix, prefix + 15 * 8, prefix + 10 * 8, prefix + 24 * 8


def _read_exact(stream: BinaryIO, size: int, label: str) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise DecodeError(f"{label}: short row")
    return value


def _row(stream: BinaryIO, row_bytes: int, run_id: str, word_count: int,
         label: str) -> tuple[int, ...]:
    value = _read_exact(stream, row_bytes, label)
    encoded = run_id.encode()
    prefix = row_bytes - word_count * 8
    if struct.unpack_from("<I", value, 0)[0] != len(encoded):
        raise DecodeError(f"{label}: run_id length drift")
    if value[4:4 + len(encoded)] != encoded or any(value[4 + len(encoded):prefix]):
        raise DecodeError(f"{label}: run_id prefix/padding drift")
    return struct.unpack_from("<" + "Q" * word_count, value, prefix)


def _binding(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "path", "size_bytes", "sha256", "row_count"
    }:
        raise DecodeError(f"{label}: binding shape is invalid")
    path = value["path"]
    digest = value["sha256"]
    if (not isinstance(path, str) or not path or pathlib.PurePosixPath(path).is_absolute()
            or ".." in pathlib.PurePosixPath(path).parts):
        raise DecodeError(f"{label}: unsafe path")
    if (not isinstance(digest, str) or len(digest) != 64
            or any(item not in "0123456789abcdef" for item in digest)):
        raise DecodeError(f"{label}: invalid SHA-256")
    if (not isinstance(value["size_bytes"], int) or value["size_bytes"] < 0
            or not isinstance(value["row_count"], int) or value["row_count"] < 0):
        raise DecodeError(f"{label}: invalid counts")
    return value


@dataclass(frozen=True)
class Reconciliation:
    offered: int
    accepted: int
    full: int
    consumed: int
    valid: bool
    zero_loss: bool
    effective_tail_status: str

    def document(self, run_id: str, hashes: dict[str, str]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_ID,
            "physical_format": FORMAT_ID,
            "run_id": run_id,
            "producer_sha256": hashes["producer"],
            "consumer_sha256": hashes["consumer"],
            "joined_sha256": hashes["joined"],
            "offered_count": self.offered,
            "accepted_count": self.accepted,
            "full_count": self.full,
            "consumed_count": self.consumed,
            "join_status": "PASSED",
            "run_validity": "VALID" if self.valid else "INVALID",
            "zero_loss_status": "PASS" if self.zero_loss else "FAIL",
            # This bounded decoder deliberately makes no N_eff claim.  A later
            # estimator must consume these verified joined bytes explicitly.
            "effective_tail_status": self.effective_tail_status,
            "n_eff_claimed": None,
            "record_index_is_event_identity": False,
        }


def reconcile(root: pathlib.Path, contract: dict[str, Any]) -> dict[str, Any]:
    if set(contract) != {"schema_version", "run_id", "physical_format", "streams"}:
        raise DecodeError("contract shape is invalid")
    if contract["schema_version"] != "cpu-prefetch-stage17-raw-stream-contract/1":
        raise DecodeError("contract version is unsupported")
    if contract["physical_format"] != FORMAT_ID:
        raise DecodeError("physical format is unsupported")
    run_id = contract["run_id"]
    if not isinstance(run_id, str):
        raise DecodeError("run_id is invalid")
    streams = contract["streams"]
    if not isinstance(streams, dict) or set(streams) != {"producer", "consumer", "joined"}:
        raise DecodeError("stream family is incomplete")
    bindings = {name: _binding(streams[name], name) for name in streams}
    prefix, producer_bytes, consumer_bytes, joined_bytes = row_layout(run_id)
    del prefix
    expected_row_bytes = {
        "producer": producer_bytes,
        "consumer": consumer_bytes,
        "joined": joined_bytes,
    }
    paths: dict[str, pathlib.Path] = {}
    hashes: dict[str, str] = {}
    for name, binding in bindings.items():
        path = root / binding["path"]
        if path.is_symlink() or not path.is_file():
            raise DecodeError(f"{name}: not a nonsymlink regular file")
        if path.stat().st_size != binding["size_bytes"]:
            raise DecodeError(f"{name}: byte count mismatch")
        if binding["size_bytes"] != binding["row_count"] * expected_row_bytes[name]:
            raise DecodeError(f"{name}: row/byte count mismatch")
        hashes[name] = sha256_path(path)
        if hashes[name] != binding["sha256"]:
            raise DecodeError(f"{name}: SHA-256 mismatch")
        paths[name] = path

    accepted = 0
    full = 0
    with (paths["producer"].open("rb") as producer,
          paths["consumer"].open("rb") as consumer,
          paths["joined"].open("rb") as joined):
        for logical in range(bindings["producer"]["row_count"]):
            p = _row(producer, producer_bytes, run_id, 15, f"producer[{logical}]")
            if p[0] != logical or p[14] not in {ACCEPTED_FLAGS, FULL_FLAGS}:
                raise DecodeError("producer logical sequence/flags mismatch")
            if not (p[2] <= p[4] <= p[6] <= p[8] <= p[12]):
                raise DecodeError("producer timestamp order is invalid")
            if p[14] == FULL_FLAGS:
                if p[9] != 0 or p[10] != 0 or p[13] != 0:
                    raise DecodeError("FULL contains accepted-only values")
                full += 1
                continue
            if p[13] != accepted or not (p[8] <= p[10] <= p[12]):
                raise DecodeError("accepted ordinal/linearization mismatch")
            c = _row(consumer, consumer_bytes, run_id, 10, f"consumer[{accepted}]")
            j = _row(joined, joined_bytes, run_id, 24, f"joined[{accepted}]")
            if c[0] != accepted or c[1] != p[1]:
                raise DecodeError("consumer ordinal/index mismatch")
            if not (c[3] <= c[5] <= c[7] <= c[9]):
                raise DecodeError("consumer timestamp order is invalid")
            expected = (
                accepted, p[0], p[1], logical, accepted,
                p[2], p[4], p[6], p[8], p[10], p[12],
                c[3], c[5], c[7], c[9],
                p[4] - p[2], p[6] - p[4], p[12] - p[8],
                p[10] - p[2], c[5] - p[10], c[7] - c[3],
                c[9] - c[5], c[9] - c[7], c[9] - p[2],
            )
            if j != expected:
                raise DecodeError("joined row is not the independently derived row")
            accepted += 1
        if producer.read(1) or consumer.read(1) or joined.read(1):
            raise DecodeError("stream contains trailing bytes")
    if bindings["consumer"]["row_count"] != accepted:
        raise DecodeError("consumer count differs from accepted count")
    if bindings["joined"]["row_count"] != accepted:
        raise DecodeError("joined count differs from accepted count")
    result = Reconciliation(
        offered=bindings["producer"]["row_count"], accepted=accepted, full=full,
        consumed=bindings["consumer"]["row_count"], valid=True,
        zero_loss=full == 0, effective_tail_status="NOT_EVALUATED",
    )
    if result.accepted + result.full != result.offered:
        raise DecodeError("accepted/FULL arithmetic mismatch")
    return result.document(run_id, hashes)


def _prefix(run_id: str) -> bytes:
    encoded = run_id.encode()
    return struct.pack("<I", len(encoded)) + encoded + bytes((-4 - len(encoded)) % 8)


def _write_fixture(root: pathlib.Path, *, full: bool = False,
                   corrupt_join: bool = False) -> dict[str, Any]:
    run_id = "SYNTHETIC-RAW-DECODER"
    p_rows = []
    c_rows = []
    j_rows = []
    accepted = 0
    for logical in range(3):
        is_full = full and logical == 1
        p = (logical, logical % 2, logical * 100, 0, logical * 100 + 1, 0,
             logical * 100 + 2, 0, logical * 100 + 3,
             0 if is_full else 0, 0 if is_full else logical * 100 + 4,
             0, logical * 100 + 5, 0 if is_full else accepted,
             FULL_FLAGS if is_full else ACCEPTED_FLAGS)
        p_rows.append(_prefix(run_id) + struct.pack("<15Q", *p))
        if is_full:
            continue
        c = (accepted, logical % 2, 0, logical * 100 + 6, 0,
             logical * 100 + 7, 0, logical * 100 + 8, 0, logical * 100 + 9)
        c_rows.append(_prefix(run_id) + struct.pack("<10Q", *c))
        j = (accepted, logical, logical % 2, logical, accepted,
             logical * 100, logical * 100 + 1, logical * 100 + 2,
             logical * 100 + 3, logical * 100 + 4, logical * 100 + 5,
             logical * 100 + 6, logical * 100 + 7, logical * 100 + 8,
             logical * 100 + 9, 1, 1, 2, 4, 3, 2, 2, 1, 9)
        if corrupt_join and logical == 2:
            j = j[:-1] + (10,)
        j_rows.append(_prefix(run_id) + struct.pack("<24Q", *j))
        accepted += 1
    contract = {
        "schema_version": "cpu-prefetch-stage17-raw-stream-contract/1",
        "run_id": run_id, "physical_format": FORMAT_ID, "streams": {},
    }
    for name, rows in (("producer", p_rows), ("consumer", c_rows), ("joined", j_rows)):
        path = root / f"{name}.bin"
        path.write_bytes(b"".join(rows))
        contract["streams"][name] = {
            "path": path.name, "size_bytes": path.stat().st_size,
            "sha256": sha256_path(path), "row_count": len(rows),
        }
    return contract


def _write_streaming_fixture(root: pathlib.Path, row_count: int) -> dict[str, Any]:
    """Create a large exact fixture without materializing any stream in memory."""
    run_id = "SYNTHETIC-RAW-DECODER-LARGE"
    paths = {name: root / f"{name}.bin" for name in ("producer", "consumer", "joined")}
    prefix = _prefix(run_id)
    with (paths["producer"].open("wb") as producer,
          paths["consumer"].open("wb") as consumer,
          paths["joined"].open("wb") as joined):
        for logical in range(row_count):
            base = logical * 100
            producer.write(prefix + struct.pack(
                "<15Q", logical, logical % 2, base, 0, base + 1, 0,
                base + 2, 0, base + 3, 0, base + 4, 0, base + 5,
                logical, ACCEPTED_FLAGS,
            ))
            consumer.write(prefix + struct.pack(
                "<10Q", logical, logical % 2, 0, base + 6, 0,
                base + 7, 0, base + 8, 0, base + 9,
            ))
            joined.write(prefix + struct.pack(
                "<24Q", logical, logical, logical % 2, logical, logical,
                base, base + 1, base + 2, base + 3, base + 4, base + 5,
                base + 6, base + 7, base + 8, base + 9,
                1, 1, 2, 4, 3, 2, 2, 1, 9,
            ))
    return {
        "schema_version": "cpu-prefetch-stage17-raw-stream-contract/1",
        "run_id": run_id,
        "physical_format": FORMAT_ID,
        "streams": {
            name: {
                "path": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_path(path),
                "row_count": row_count,
            }
            for name, path in paths.items()
        },
    }


def self_test() -> tuple[int, int]:
    positives = 0
    negatives = 0
    with tempfile.TemporaryDirectory(prefix="stage17-raw-decoder-") as temporary:
        root = pathlib.Path(temporary)
        result = reconcile(root, _write_fixture(root))
        if result["zero_loss_status"] != "PASS" or result["accepted_count"] != 3:
            raise DecodeError("positive zero-loss fixture failed")
        positives += 1
    with tempfile.TemporaryDirectory(prefix="stage17-raw-full-") as temporary:
        root = pathlib.Path(temporary)
        result = reconcile(root, _write_fixture(root, full=True))
        if (result["run_validity"] != "VALID" or result["zero_loss_status"] != "FAIL"
                or result["full_count"] != 1):
            raise DecodeError("valid FULL fixture was misclassified")
        positives += 1
    with tempfile.TemporaryDirectory(prefix="stage17-raw-neff-200000-") as temporary:
        root = pathlib.Path(temporary)
        result = reconcile(root, _write_streaming_fixture(root, 200_000))
        if (result["accepted_count"] != 200_000
                or result["n_eff_claimed"] is not None):
            raise DecodeError("N_eff=200000 streaming boundary fixture failed")
        positives += 1
    for label, mutation in (
        ("one_byte", lambda root, value: (root / "producer.bin").write_bytes(b"x")),
        ("forged_join", lambda root, value: None),
        ("count", lambda root, value: value["streams"]["consumer"].__setitem__("row_count", 99)),
        ("hash", lambda root, value: value["streams"]["joined"].__setitem__("sha256", "a" * 64)),
    ):
        with tempfile.TemporaryDirectory(prefix="stage17-raw-negative-") as temporary:
            root = pathlib.Path(temporary)
            value = _write_fixture(root, corrupt_join=label == "forged_join")
            mutation(root, value)
            try:
                reconcile(root, value)
            except DecodeError:
                negatives += 1
            else:
                raise DecodeError(f"negative fixture admitted: {label}")
    return positives, negatives


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=pathlib.Path)
    parser.add_argument("--contract", type=pathlib.Path)
    arguments = parser.parse_args()
    if arguments.self_test:
        positives, negatives = self_test()
        print(f"stage17-raw-stream-decoder: PASS ({positives} positive, {negatives} negative)")
        return 0
    if arguments.root is None or arguments.contract is None:
        raise DecodeError("--root and --contract are required")
    document = json.loads(arguments.contract.read_bytes())
    print(canonical(reconcile(arguments.root, document)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, DecodeError) as error:
        print(f"stage17-raw-stream-decoder: FAIL: {error}", file=os.sys.stderr)
        raise SystemExit(1) from error
